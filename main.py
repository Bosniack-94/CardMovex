from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from schemas.movements import CardMovementRaw, CardMovementFinal
from processors.text_enricher import TextEnricher
from core.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan de FastAPI: reemplaza los deprecated @app.on_event("startup").
    Todo lo que está ANTES del yield se ejecuta al arrancar el servidor.
    Todo lo que está DESPUÉS del yield se ejecuta al apagarlo.
    """
    # === STARTUP ===
    configure_logging(json_mode=False)  # Cambiar a True en producción (Docker/Cloud)
    log.info("cardmovex.startup", version=app.version, model="gpt-4o-mini")
    yield
    # === SHUTDOWN ===
    log.info("cardmovex.shutdown")


app = FastAPI(
    title="CardMovex AI REST API",
    description="Motor Inteligente de Enriquecimiento Transaccional Fintech 2026.",
    version="1.0.0",
    lifespan=lifespan,
)

# Singleton del enricher: se crea una sola vez y se reutiliza en cada request
enricher = TextEnricher()


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
