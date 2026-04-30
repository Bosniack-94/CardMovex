import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from schemas.movements import CardMovementRaw, CardMovementFinal
from schemas.audit import AuditRequest, AuditResult
from processors.text_enricher import TextEnricher
from processors.visual_auditor import VisualAuditor
from processors.belvo_client import BelvoClient
from core.logging import configure_logging, get_logger
from core.database import engine, Base, SessionLocal
from schemas.db_models import MovementRecord


log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan de FastAPI: reemplaza los deprecated @app.on_event("startup").
    Todo lo que está ANTES del yield se ejecuta al arrancar el servidor.
    Todo lo que está DESPUÉS del yield se ejecuta al apagarlo.
    """
    # === STARTUP ===
    Base.metadata.create_all(bind=engine) # Crear tablas si no existen
    configure_logging(json_mode=False)  # Cambiar a True en producción (Docker/Cloud)
    log.info("cardmovex.startup", version=app.version, model="gpt-4o-mini", database="SQLite Active")
    yield
    # === SHUTDOWN ===
    log.info("cardmovex.shutdown")


app = FastAPI(
    title="CardMovex AI REST API",
    description="Motor Inteligente de Enriquecimiento Transaccional Fintech 2026.",
    version="1.0.0",
    lifespan=lifespan,
)

# Singletons: se crean una sola vez al iniciar el servidor
enricher = TextEnricher()
auditor  = VisualAuditor()



@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "CardMovex", "version": app.version}


@app.post(
    "/process-movements",
    response_model=list[CardMovementFinal],
    tags=["Movements"],
    summary="Enriquecer un batch de movimientos crudos",
)
async def process_movements(movements: list[CardMovementRaw]):
    """
    Recibe un batch de movimientos crudos (formato Belvo u otro agregador).
    Ejecuta el pipeline de enriquecimiento IA y devuelve la lista clasificada y auditada.
    """
    log.info("api.process_movements.request", batch_size=len(movements))
    try:
        results = await enricher.enrich_movements(movements)
        log.info("api.process_movements.response", returned=len(results))
        return results
    except Exception as e:
        log.error("api.process_movements.error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en el procesamiento: {str(e)}")


@app.post(
    "/audit-movement",
    response_model=AuditResult,
    tags=["Audit"],
    summary="Auditar un movimiento con imagen (GPT-4o Vision)",
)
async def audit_movement(request: AuditRequest):
    """
    Capa L3 — Auditoría Multimodal.
    Recibe la imagen de un recibo o estado de cuenta en base64
    y la cruza con los datos del movimiento para emitir un veredicto.
    Solo se activa bajo demanda (no corre en el pipeline normal).
    """
    log.info("api.audit_movement.request", movement_id=request.movement_id)
    try:
        result = await auditor.audit_movement(request)
        log.info(
            "api.audit_movement.response",
            movement_id=request.movement_id,
            verdict=result.verdict,
        )
        return result
    except Exception as e:
        log.error("api.audit_movement.error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en la auditoría: {str(e)}")


@app.post(
    "/belvo-sync",
    response_model=list[CardMovementFinal],
    tags=["Belvo"],
    summary="Sincronizar movimientos reales desde Belvo Sandbox y enriquecerlos con IA",
)
async def belvo_sync():
    """
    Paso 9 — Pipeline completo end-to-end con datos reales de Belvo.

    1. Crea un link al banco ficticio del sandbox (erebus_mx_retail).
    2. Extrae las transacciones de los últimos 30 días.
    3. Las pasa por el motor de IA (TextEnricher) para enriquecer y clasificar.
    4. Devuelve la lista completa con veredictos, categorías y métricas de confianza.

    Este es el flujo de DEMOSTRACIÓN para el pipeline de datos reales.
    """
    log.info("api.belvo_sync.start")
    try:
        async with BelvoClient() as client:
            link_id = await client.create_sandbox_link()
            raw_movements = await client.get_transactions(link_id)

        log.info("api.belvo_sync.extracted", count=len(raw_movements))

        if not raw_movements:
            return []

        enriched = await enricher.enrich_movements(raw_movements)
        log.info("api.belvo_sync.enriched", count=len(enriched))
        return enriched

    except Exception as e:
        log.error("api.belvo_sync.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error en la sincronización con Belvo: {str(e)}",
        )


# === RPA Web Scraper (Zero-Cost Alternative) ===

import asyncio
from processors.web_scraper import RpScraper
from pydantic import BaseModel
from enum import Enum

class BankOptions(str, Enum):
    DEMO = "Banco de Prueba (Demo Local Localhost)"
    BBVA = "BBVA México"
    SANTANDER = "Santander"
    BANAMEX = "Citibanamex"
    BANORTE = "Banorte"
    AMEX = "American Express"
    AZTECA = "Banco Azteca"
    BANREGIO = "Banregio"
    HSBC = "HSBC México"

class RpaRequest(BaseModel):
    banco: BankOptions
    audit_client: str = "Client-Alpha" # Identificador de la memoria (Fase 2)

_BANK_URLS = {
    BankOptions.DEMO: "http://127.0.0.1:8000/demo-bank",
    BankOptions.BBVA: "https://www.bbva.mx/personas/servicios-digitales/bbva-web.html",
    BankOptions.SANTANDER: "https://www.santander.com.mx/",
    BankOptions.BANAMEX: "https://bancanet.banamex.com/",
    BankOptions.BANORTE: "https://www.banorte.com/",
    BankOptions.AMEX: "https://www.americanexpress.com/es-mx/",
    BankOptions.AZTECA: "https://www.bancoazteca.com.mx/",
    BankOptions.BANREGIO: "https://www.banregio.com/",
    BankOptions.HSBC: "https://www.hsbc.com.mx/banca-en-linea/",
}

@app.post(
    "/rpa-sync",
    response_model=list[CardMovementFinal],
    tags=["Integraciones", "Pipeline RPA"],
    summary="[NUEVO] Extracción RPA 100% gratuita",
)
async def rpa_sync(req: RpaRequest):
    """
    Paso 10 — Automatización Robótica (RPA) de $0 dólares.
    
    1. Despliega la lista, elige un banco y dale a Execute.
    2. El robot abrirá la ventana lista para ti.
    3. Inicia sesión, busca tus compras y presiona el botón Extraer.
    """
    target_url = _BANK_URLS[req.banco]
    log.info("api.rpa_sync.start", url=target_url)
    
    scraper = RpScraper()
    try:
        raw_dump = await asyncio.to_thread(scraper.extract_raw_movements, target_url)
        if not raw_dump:
            raise HTTPException(status_code=400, detail="El bot no pudo extraer texto de la página.")
            
        enriched_data = await enricher.enrich_raw_text(raw_dump)
        
        # === FASE 2: MEMORIA DE AUDITORÍA (Guardar en DB) ===
        db = SessionLocal()
        try:
            db_records = []
            for mov in enriched_data:
                # Verificar duplicados por ID único
                if not db.query(MovementRecord).filter(MovementRecord.id == mov.id).first():
                    db_records.append(MovementRecord(
                        id=mov.id, client_id=req.audit_client, bank_name=req.banco,
                        amount=mov.amount, date=mov.date, description_raw=mov.description_raw,
                        description_clean=mov.description_clean, merchant_name=mov.merchant_name,
                        category=mov.category, is_commission=mov.is_commission,
                        is_interest=mov.is_interest, confidence_score=mov.confidence_score,
                        needs_review=mov.needs_review
                    ))
            if db_records:
                db.add_all(db_records)
                db.commit()
            log.info("rpa.persistence.saved", count=len(db_records), client=req.audit_client)
        except Exception as e_db:
            log.error("rpa.persistence.error", error=str(e_db))
        finally:
            db.close()
            
        return enriched_data

    except Exception as e:
        log.error("api.rpa_sync.error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error en la extracción RPA o LLM: {str(e)}",
        )

# === FASE 2: ENDPOINTS DE MEMORIA HISTÓRICA ===

@app.get("/history", tags=["Memoria de Auditoría"], summary="Listar clientes auditados")
async def get_history_clients():
    db = SessionLocal()
    try:
        clients = db.query(MovementRecord.client_id).distinct().all()
        return [c[0] for c in clients]
    finally:
        db.close()

@app.get("/history/{client_id}", tags=["Memoria de Auditoría"], summary="Ver movimientos históricos de un cliente")
async def get_client_history(client_id: str):
    db = SessionLocal()
    try:
        from sqlalchemy import desc
        results = db.query(MovementRecord).filter(MovementRecord.client_id == client_id).order_by(desc(MovementRecord.date)).all()
        return results
    finally:
        db.close()

# === Mock Bank Portal for Local Demo ===
from fastapi.responses import HTMLResponse

@app.get("/demo-bank", response_class=HTMLResponse, tags=["Demo"], summary="Portal Bancario de Prueba")
async def demo_bank():
    """
    Simula el dashboard web de un Neobanco. 
    Útil para probar el Scraper RPA y la detección de comisiones e intereses.
    """
    html_content = """
    <html>
        <head>
            <title>Mi Neobanco - Plata/Klar Simulator</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6; color: #1f2937; padding: 40px; }
                .card { background-color: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 800px; margin: 0 auto; }
                h1 { color: #2563eb; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { padding: 15px; text-align: left; border-bottom: 1px solid #e5e7eb; border-top: 1px solid #e5e7eb;}
                th { background-color: #f8fafc; color: #64748b; }
                .amount-out { color: #ef4444; font-weight: bold; }
                .amount-in { color: #10b981; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>💰 Mi Tablero Financiero</h1>
                <h2>Saldo Actual: $12,500.00 MXN</h2>
                <p>Bienvenido a tu portal web. Tienes 10 movimientos recientes (Abril y Marzo).</p>
                
                <table>
                    <thead>
                        <tr>
                            <th>Fecha</th>
                            <th>Descripción</th>
                            <th>Monto</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>Mar 02, 2026</td><td>Spotify Premium XXXXXXXXXXXX6947</td><td class="amount-out">-$75.00</td></tr>
                        <tr><td>Mar 06, 2026</td><td>Telmex XXXXXXXXXXXX5453</td><td class="amount-out">-$500.00</td></tr>
                        <tr><td>Mar 06, 2026</td><td>Pago de Línea de crédito</td><td class="amount-in">+$235.02</td></tr>
                        <tr><td>Mar 07, 2026</td><td>Costco XXXXXXXXXXXX6947</td><td class="amount-out">-$35.79</td></tr>
                        <tr><td>Mar 08, 2026</td><td>Pago de Línea de crédito</td><td class="amount-in">+$667.46</td></tr>
                        <tr><td>Mar 09, 2026</td><td>La Comer XXXXXXXXXXXX6947</td><td class="amount-out">-$102.65</td></tr>
                        <tr><td>Mar 09, 2026</td><td>Pago de Línea de crédito</td><td class="amount-in">+$525.79</td></tr>
                        <tr><td>Mar 10, 2026</td><td>Mercado Pago XXXXXXXXXXXX5453</td><td class="amount-out">-$965.03</td></tr>
                        <tr><td>Mar 10, 2026</td><td>Clip Mxrest Psquis A XXXXXXXXXXXX6947</td><td class="amount-out">-$271.00</td></tr>
                        <tr><td>Mar 19, 2026</td><td>App Tickets XXXXXXXXXXXX5453</td><td class="amount-out">-$96.00</td></tr>
                    </tbody>
                </table>
            </div>
        </body>
    </html>
    """
    return html_content

class ChatRequest(BaseModel):
    query: str
    movements: list[CardMovementFinal]

@app.post("/chat-movements", tags=["Killer Feature"], summary="RAG: Chat en tiempo real con los movimientos extraídos")
async def chat_movements(req: ChatRequest):
    """
    Toma la lista de movimientos extraídos y responde cualquier pregunta financiera del usuario
    usando Gemini 2.5 Flash en tiempo real.
    """
    log.info("api.chat_movements.start", query=req.query)
    try:
        from config.settings import settings
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Convertir movimientos a JSON string para contexto
        context_data = [mov.model_dump() for mov in req.movements]
        import json
        context_str = json.dumps(context_data, default=str)
        
        prompt = f"""
        Eres un Asistente de Contabilidad B2B y Agregador de Datos. Analiza estas transacciones en formato JSON: 
        {context_str}
        
        El usuario requiere agilizar su contabilidad y te ha pedido: "{req.query}"
        
        RESPONDE ÚNICA Y EXCLUSIVAMENTE CON CÓDIGO HTML 100% VÁLIDO UTILIZANDO CLASES DE TAILWINDCSS.
        Reglas de Negocio (B2B):
        - PROHIBIDO DAR CONSEJOS FINANCIEROS O DE AHORRO. Los usuarios son contadores corporativos enfocados en facturación y conciliación, no quieren saber cómo "optimizar su liquidez".
        - Tu único trabajo es FILTRAR, AGRUPAR, SUMAR y MOSTRAR EXACTAMENTE lo que piden de forma ultra organizada.
        - GLOSARIO VISUAL DE COLORES (MUY IMPORTANTE): Si el usuario te pide filtrar por un "color" (ej. "naranja", "morado", "verde"), debes filtrar por la categoría asociada a ese color en su pantalla:
            * "Verde" o "Esmeralda" = Ingresos, Abonos, Pagos de Tarjeta.
            * "Rojo" o "Rosa" = Penalizaciones, Intereses, Comisiones.
            * "Cyan" o "Celeste" = Suscripciones, Software, Entretenimiento.
            * "Naranja" = Comida, Restaurantes.
            * "Ámbar" o "Amarillo" = Transporte, Gasolina.
            * "Morado" o "Violeta" = Supermercados, Despensa, Compras en línea.
            * "Azul" = Servicios (Luz, Internet, Telefonía).
        - Si el usuario simplemente manda "servicios" o "comida", asume lo lógico. Si te manda "morado", evalúa las compras de despensa.
        
        Reglas Visuales Estrictas:
        - PROHIBIDO usar Markdown (no uses ```html ni asteriscos). Tu respuesta debe ser SOLO código HTML puro.
        - ATENCIÓN: La ventana del chat tiene fondo OSCURO (bg-slate-800). Todas tus tarjetas deben tener diseño "Dark Mode".
        - Agrupa las transacciones y pon cada una en: <div class='flex justify-between items-center p-3 mb-2 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-slate-100'>
        - Asegúrate que el Comercio tenga <span class='font-bold text-white'> y la Fecha/ID usen <span class='text-xs text-slate-400'>.
        - Asigna un color semántico POR GRUPO solo al encabezado principal de la suma. Ej: <div class='mb-4 p-4 bg-orange-500/20 text-orange-400 border border-orange-500/30 rounded-xl font-bold text-xl'>Total Comida: $1,500.00 MXN</div>
        - Usa: Naranja (orange-500) para comida, Ámbar (amber-500) para transporte, Azul (blue-400) para servicios, Cyan (cyan-400) para software, Esmeralda (emerald-400) para ingresos.
        - El Monto en cada fila debe ir a la derecha en color brillante acorde a la categoría o simplemente <span class='font-mono font-bold text-emerald-400'> para ingresos y <span class='font-mono font-bold text-white'> para egresos.
        
        Tu salida debe ser el HTML listo para inyectar mediante innerHTML.
        """
        response = await asyncio.to_thread(model.generate_content, prompt)
        return {"answer": response.text}
    except Exception as e:
        log.warning("api.chat_movements.quota_fallback", error=str(e))
        fallback_html = """
        <div class='mb-4 p-4 bg-slate-800 border border-slate-600 rounded-xl shadow-lg'>
            <div class='flex items-center mb-2'>
                <i class='fas fa-shield-alt text-indigo-400 text-xl mr-3'></i>
                <h4 class='text-white font-bold'>Modo de Protección Anti-Saturación</h4>
            </div>
            <p class='text-slate-300 text-sm'>
                El volumen de consultas analíticas RAG ha superado el tráfico de seguridad de su capa gratuita (Rate Limit 429). 
                Para integraciones en cadena de producción continua, por favor enlace su API Key corporativa.
            </p>
            <p class='text-slate-400 text-xs mt-3 font-mono border-t border-slate-700 pt-2'>
                Acción recomendada: Espere 60 segundos antes de ejecutar la siguiente auditoría.
            </p>
        </div>
        """
        return {"answer": fallback_html}
# === Frontend Visual (Dashboard) ===
import os
from fastapi.staticfiles import StaticFiles

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
os.makedirs(frontend_path, exist_ok=True)
app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")
