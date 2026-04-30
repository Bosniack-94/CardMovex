"""
Schemas para la Capa L3 — Auditoría Multimodal de movimientos.

Caso de uso:
El cliente recibe un movimiento con needs_review=True (o uno que simplemente
no reconoce) y sube una foto del recibo o del estado de cuenta bancario.
El sistema usa GPT-4o Vision para cruzar la imagen con los datos del movimiento
y devolver un veredicto estructurado: si el monto coincide, si el nombre del
comercio es reconocible y si hay evidencia de disputa.

Por qué un schema separado y no reusar CardMovementFinal:
El contrato de ENTRADA de una auditoría es distinto al de enriquecimiento:
requiere una imagen en base64 y el movimiento ya enriquecido como referencia.
El contrato de SALIDA es un veredicto, no un movimiento enriquecido.
Separar responsabilidades es la marca del diseño Senior.
"""
from pydantic import BaseModel, Field
from typing import Annotated, Optional
from enum import Enum


class AuditVerdict(str, Enum):
    """
    Resultado posible de la auditoría visual.
    Usamos Enum (no str libre) para forzar valores controlados en toda la app.
    """
    CONFIRMED = "CONFIRMED"        # La imagen confirma el movimiento
    DISPUTED  = "DISPUTED"         # La imagen contradice el movimiento
    INCONCLUSIVE = "INCONCLUSIVE"  # La imagen no es suficiente para decidir


class AuditRequest(BaseModel):
    """
    Payload de entrada para el endpoint de auditoría.
    El cliente envía la imagen en base64 junto con la referencia del movimiento.
    """
    movement_id: str
    description_raw: str
    amount: float
    # Imagen del recibo/estado de cuenta en formato base64 (JPEG o PNG)
    # El prefijo data:image/jpeg;base64, debe incluirse si es Data URL.
    image_base64: str = Field(
        ...,
        description="Imagen en base64. Incluir prefijo data:image/jpeg;base64, o data:image/png;base64,"
    )


class AuditResult(BaseModel):
    """
    Respuesta estructurada de la auditoría visual.
    """
    movement_id: str
    verdict: AuditVerdict

    # Evidencia extraída de la imagen
    amount_in_image: Optional[float] = None       # Monto que aparece en el recibo
    merchant_in_image: Optional[str] = None       # Nombre del comercio en la imagen
    amounts_match: Optional[bool] = None          # ¿El monto de la imagen == amount del banco?

    # Razonamiento del modelo (útil para el equipo de soporte)
    reasoning: str = Field(default="", description="Explicación del veredicto en español")

    # Confianza del modelo de visión (0.0 - 1.0)
    confidence_score: Annotated[float, Field(default=0.0, ge=0.0, le=1.0)]
    needs_human_review: bool = False
