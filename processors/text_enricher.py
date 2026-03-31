import json
import asyncio
from openai import AsyncOpenAI
from openai import RateLimitError, APIConnectionError, APIStatusError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from schemas.movements import CardMovementRaw, CardMovementFinal
from core.logging import get_logger

log = get_logger(__name__)

# Política de reintento: aplica solo a errores de red y saturación,
# no a errores de lógica (ej. JSON inválido).
_RETRY_POLICY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    reraise=True
)

# Máximo de llamadas simultáneas a OpenAI.
# Por encima de ~20, el tier gratuito/estándar de OpenAI devuelve RateLimitError masivo.
MAX_CONCURRENT_REQUESTS = 20

class TextEnricher:
    """
    Motor de enriquecimiento transaccional con concurrencia controlada.
    - asyncio.gather → paralelismo real de I/O
    - asyncio.Semaphore → guardia que previene saturación del rate limit de OpenAI
    - tenacity @retry → resiliencia ante fallas transitorias de red
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.DEFAULT_LLM_MODEL
        # Semáforo compartido por instancia: todas las corutinas de este enricher
        # compiten por el mismo pool de MAX_CONCURRENT_REQUESTS slots.
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def enrich_movements(self, movements: list[CardMovementRaw]) -> list[CardMovementFinal]:
        """
        Procesa un batch de movimientos en paralelo con concurrencia controlada.
        - Batch vacío: retorna lista vacía sin tocar la API (guard clause).
        - Tiempo de respuesta: O(ceil(N / MAX_CONCURRENT_REQUESTS)) en lugar de O(N).
        """
        if not movements:
            log.warning("enrich_movements.empty_batch")
            return []

        log.info("enrich_movements.start", batch_size=len(movements), model=self.model)
        results = list(await asyncio.gather(*[self._process_single_movement(mov) for mov in movements]))
        needs_review_count = sum(1 for r in results if r.needs_review)
        log.info(
            "enrich_movements.complete",
            batch_size=len(results),
            needs_review=needs_review_count,
        )
        return results

    @retry(**_RETRY_POLICY)
    async def _call_openai_api(self, prompt: str) -> str:
        """
        Llamada HTTP aislada a OpenAI, protegida por dos capas:
        1. asyncio.Semaphore (externo): máximo MAX_CONCURRENT_REQUESTS llamadas en vuelo.
        2. @retry (este decorador): reintenta hasta 3x con backoff en errores de red.
        La combinación hace al sistema resiliente tanto a picos de carga como a fallas externas.
        """
        async with self._semaphore:  # Adquiere un slot — bloquea si ya hay 20 en vuelo
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial parser system that outputs pure JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            return response.choices[0].message.content

    async def _process_single_movement(self, mov: CardMovementRaw) -> CardMovementFinal:
        # Prompt Few-Shot: Ejemplos reales de bancos MX para eliminar ambigüedad
        prompt = f"""
        Eres un sistema experto de análisis de tarjetas de crédito en México.
        Tu única función es clasificar transacciones bancarias y devolver JSON puro.

        ## Reglas Absolutas (no negociables)
        - NUNCA modifiques ni inventes los campos `amount` ni `date`. No están en este prompt.
        - `confidence_score` es tu autoevaluación honesta (0.0 = no sabes, 1.0 = certeza total).
        - Si la transacción es ambigua, baja el confidence_score a menos de 0.80.

        ## Catálogo de Categorías (usar SOLO estas)
        Comida | Transporte | Entretenimiento | Supermercado | Viajes |
        Salud | Comisiones | Intereses | Servicios | Retiro | Otros

        ## Patrones de Bancos Mexicanos (Few-Shot Examples)
        Estos son ejemplos REALES de cómo los bancos MX formatean sus textos:

        EJEMPLO 1:
        description_raw: "ANUALIDAD TRIB VISA BBVA"
        → {{"description_clean": "Anualidad Tarjeta Visa BBVA", "merchant_name": "BBVA", "category": "Comisiones", "is_commission": true, "is_interest": false, "confidence_score": 0.99}}

        EJEMPLO 2:
        description_raw: "IVA COMISION BBVA 2024"
        → {{"description_clean": "IVA sobre Comisión BBVA", "merchant_name": "BBVA", "category": "Comisiones", "is_commission": true, "is_interest": false, "confidence_score": 0.99}}

        EJEMPLO 3:
        description_raw: "INT MORATORIOS BANORTE ENE"
        → {{"description_clean": "Intereses Moratorios Banorte Enero", "merchant_name": "Banorte", "category": "Intereses", "is_commission": false, "is_interest": true, "confidence_score": 0.99}}

        EJEMPLO 4:
        description_raw: "INT ORDINARIOS SANTANDER"
        → {{"description_clean": "Intereses Ordinarios Santander", "merchant_name": "Santander", "category": "Intereses", "is_commission": false, "is_interest": true, "confidence_score": 0.99}}

        EJEMPLO 5:
        description_raw: "DISP EFECTIVO CAJERO HSBC"
        → {{"description_clean": "Disposición de Efectivo en Cajero HSBC", "merchant_name": "HSBC", "category": "Comisiones", "is_commission": true, "is_interest": false, "confidence_score": 0.97}}

        EJEMPLO 6:
        description_raw: "PAGO STARBUCKS SUC POLANCO CDMX"
        → {{"description_clean": "Starbucks Sucursal Polanco", "merchant_name": "Starbucks", "category": "Comida", "is_commission": false, "is_interest": false, "confidence_score": 0.98}}

        EJEMPLO 7:
        description_raw: "UBER *TRIP 5X8K2 MX"
        → {{"description_clean": "Uber - Viaje", "merchant_name": "Uber", "category": "Transporte", "is_commission": false, "is_interest": false, "confidence_score": 0.97}}

        EJEMPLO 8:
        description_raw: "MANEJO DE CUENTA CITIBANAMEX"
        → {{"description_clean": "Comisión por Manejo de Cuenta Citibanamex", "merchant_name": "Citibanamex", "category": "Comisiones", "is_commission": true, "is_interest": false, "confidence_score": 0.99}}

        ## Transacción a Clasificar AHORA
        description_raw: "{mov.description_raw}"

        Devuelve ÚNICAMENTE el JSON válido, sin texto adicional, sin markdown, sin explicaciones:
        {{"description_clean": "", "merchant_name": "", "category": "", "is_commission": false, "is_interest": false, "confidence_score": 0.0}}
        """
        
        try:
            result_text = await self._call_openai_api(prompt)
            parsed = json.loads(result_text)

            confidence = parsed.get("confidence_score", 0.0)
            needs_review = confidence < settings.CONFIDENCE_THRESHOLD

            log.info(
                "movement.enriched",
                movement_id=mov.id,
                merchant=parsed.get("merchant_name"),
                category=parsed.get("category"),
                confidence=confidence,
                needs_review=needs_review,
                is_commission=parsed.get("is_commission"),
                is_interest=parsed.get("is_interest"),
            )

            return CardMovementFinal(
                id=mov.id,
                amount=mov.amount,  # VERDAD BANCARIA PASADA DIRECTO
                date=mov.date,      # VERDAD BANCARIA PASADA DIRECTO
                description_raw=mov.description_raw,
                description_clean=parsed.get("description_clean", mov.description_raw),
                merchant_name=parsed.get("merchant_name", "Desconocido"),
                category=parsed.get("category", "Otros"),
                is_commission=parsed.get("is_commission", False),
                is_interest=parsed.get("is_interest", False),
                confidence_score=confidence,
                needs_review=needs_review,
            )

        except Exception as e:
            log.error(
                "movement.failed",
                movement_id=mov.id,
                description_raw=mov.description_raw,
                error=str(e),
                exc_info=True,  # Incluye el stack trace completo en el log
            )
            return CardMovementFinal(
                id=mov.id,
                amount=mov.amount,
                date=mov.date,
                description_raw=mov.description_raw,
                description_clean=mov.description_raw,
                merchant_name="Error Parseo",
                category="Error",
                is_commission=False,
                is_interest=False,
                confidence_score=0.0,
                needs_review=True,
            )
