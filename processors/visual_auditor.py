"""
Capa L3 — Auditoría Visual de Movimientos con GPT-4o Vision.

Flujo de activación:
Este módulo NO corre en el pipeline normal. Se activa SOLO cuando:
1. Un movimiento tiene needs_review=True y el cliente quiere disputarlo, O
2. El cliente sube una imagen del recibo para validar un cargo específico.

Modelo: gpt-4o (modelo de visión — más caro que gpt-4o-mini pero solo se usa
        bajo demanda para auditorías específicas. Costo mínimo en producción).

Diseño de seguridad:
- Recibe la imagen en base64 desde el endpoint de FastAPI.
- El modelo ve la imagen y los datos del movimiento en texto.
- NUNCA modifica amount ni date: solo emite un veredicto (CONFIRMED/DISPUTED/INCONCLUSIVE).
"""
import json
from openai import AsyncOpenAI
from openai import RateLimitError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from schemas.audit import AuditRequest, AuditResult, AuditVerdict
from core.logging import get_logger

log = get_logger(__name__)

_RETRY_POLICY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    reraise=True,
)

# Modelo de visión — gpt-4o es el único que procesa imágenes de forma robusta
VISION_MODEL = "gpt-4o"


class VisualAuditor:
    """
    Motor de auditoría multimodal.
    Recibe una imagen del recibo/estado de cuenta y el movimiento en disputa,
    y devuelve un veredicto estructurado en JSON con el razonamiento completo.
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @retry(**_RETRY_POLICY)
    async def _call_vision_api(self, movement: AuditRequest) -> str:
        """
        Llamada aislada a GPT-4o Vision con la imagen y el contexto del movimiento.
        El modelo ve AMBAS cosas simultáneamente: texto + imagen.
        """
        system_prompt = (
            "Eres un auditor financiero experto en tarjetas de crédito mexicanas. "
            "Analizas imágenes de recibos o estados de cuenta bancarios para verificar "
            "si los datos del movimiento reportado coinciden con la evidencia visual. "
            "Siempre respondes en JSON puro, en español, sin texto adicional."
        )

        user_prompt = f"""
        Tengo el siguiente movimiento registrado en el sistema:
        - ID: {movement.movement_id}
        - Descripción: {movement.description_raw}
        - Monto registrado: ${movement.amount:.2f} MXN

        Por favor analiza la imagen adjunta (recibo, voucher o captura de pantalla) y determina:
        1. ¿Qué monto aparece en la imagen? (null si no es visible)
        2. ¿Qué nombre de comercio aparece?
        3. ¿El monto de la imagen coincide con el monto registrado (${movement.amount:.2f})?
        4. ¿Cuál es tu veredicto? (CONFIRMED, DISPUTED o INCONCLUSIVE)
        5. Explica brevemente tu razonamiento en español.
        6. Indica tu confidence_score del 0.0 al 1.0.

        Reglas absolutas:
        - Si la imagen es ilegible o no muestra un recibo/estado de cuenta → veredicto: INCONCLUSIVE
        - Si el monto visible difiere del registrado → veredicto: DISPUTED
        - Si coinciden → veredicto: CONFIRMED
        - NUNCA inventes montos que no puedas leer claramente en la imagen.

        Devuelve SOLO este JSON:
        {{
            "amount_in_image": null,
            "merchant_in_image": null,
            "amounts_match": null,
            "verdict": "INCONCLUSIVE",
            "reasoning": "",
            "confidence_score": 0.0
        }}
        """

        response = await self.client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": movement.image_base64,
                                "detail": "high",  # Alta resolución para leer montos con claridad
                            },
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=512,  # Los veredictos son cortos — limitar tokens reduce costo
        )
        return response.choices[0].message.content

    async def audit_movement(self, request: AuditRequest) -> AuditResult:
        """
        Método público principal.
        Recibe la solicitud de auditoría y devuelve el veredicto estructurado.
        """
        log.info(
            "visual_audit.start",
            movement_id=request.movement_id,
            amount=request.amount,
            model=VISION_MODEL,
        )

        try:
            raw_json = await self._call_vision_api(request)
            parsed = json.loads(raw_json)

            confidence = parsed.get("confidence_score", 0.0)

            # Mapeamos el string del JSON al Enum de Python
            verdict_str = parsed.get("verdict", "INCONCLUSIVE").upper()
            try:
                verdict = AuditVerdict(verdict_str)
            except ValueError:
                verdict = AuditVerdict.INCONCLUSIVE

            result = AuditResult(
                movement_id=request.movement_id,
                verdict=verdict,
                amount_in_image=parsed.get("amount_in_image"),
                merchant_in_image=parsed.get("merchant_in_image"),
                amounts_match=parsed.get("amounts_match"),
                reasoning=parsed.get("reasoning", ""),
                confidence_score=confidence,
                needs_human_review=confidence < 0.75 or verdict == AuditVerdict.INCONCLUSIVE,
            )

            log.info(
                "visual_audit.complete",
                movement_id=request.movement_id,
                verdict=result.verdict,
                amounts_match=result.amounts_match,
                confidence=confidence,
            )
            return result

        except Exception as e:
            log.error(
                "visual_audit.failed",
                movement_id=request.movement_id,
                error=str(e),
                exc_info=True,
            )
            return AuditResult(
                movement_id=request.movement_id,
                verdict=AuditVerdict.INCONCLUSIVE,
                reasoning="Error interno al procesar la imagen. Se requiere revisión manual.",
                confidence_score=0.0,
                needs_human_review=True,
            )
