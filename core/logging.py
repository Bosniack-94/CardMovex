"""
Módulo centralizado de logging estructurado para CardMovex.

Por qué structlog y no el logging estándar de Python:
- El logging estándar produce strings planas difíciles de parsear en producción.
- structlog produce JSON estructurado: cada log es un objeto con campos tipados.
- Esto permite filtrar y buscar logs en sistemas como Datadog, CloudWatch, o Elasticsearch
  con queries como: filter(movement_id="abc123") o filter(confidence_score < 0.85).

Nivel de log por entorno:
- Desarrollo: ConsoleRenderer (legible en terminal con colores)
- Producción: JSONRenderer (parseable por cualquier sistema de observabilidad)
"""
import logging
import structlog


def configure_logging(json_mode: bool = False) -> None:
    """
    Configura el pipeline de logging de la aplicación.
    Debe llamarse UNA sola vez al inicio de la app (en el lifespan de FastAPI).

    Args:
        json_mode: True en producción (salida JSON). False en desarrollo (salida legible).
    """
    # Procesadores compartidos: enriquecen cada evento antes de renderizarlo
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,         # Permite añadir contexto global (ej. request_id)
        structlog.stdlib.add_logger_name,                # Añade el nombre del logger al log
        structlog.stdlib.add_log_level,                  # Añade el nivel (info, warning, error)
        structlog.processors.TimeStamper(fmt="iso"),     # Timestamp ISO 8601 en UTC
        structlog.stdlib.PositionalArgumentsFormatter(), # Soporta %s en mensajes
        structlog.processors.StackInfoRenderer(),        # Stack trace si se incluye
        structlog.processors.format_exc_info,            # Formatea excepciones automáticamente
    ]

    renderer = (
        structlog.processors.JSONRenderer()   # Producción: JSON puro
        if json_mode
        else structlog.dev.ConsoleRenderer()  # Desarrollo: legible con colores
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Silencia logs ruidosos de librerías externas en nivel WARNING o superior
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Factory de loggers con nombre. Uso:
        log = get_logger(__name__)
        log.info("movement_processed", id="abc", confidence=0.97)
    """
    return structlog.get_logger(name)
