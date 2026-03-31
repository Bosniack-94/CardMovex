from pydantic import BaseModel, Field
from typing import Annotated, Optional
from datetime import date

class CardMovementRaw(BaseModel):
    """
    Modelo de entrada que simula los datos crudos extraídos de un agregador como Belvo.
    """
    id: str
    description_raw: str
    amount: float
    date: date
    # Datos adicionales que a veces proveen los agregadores
    category_raw: Optional[str] = None
    merchant_raw: Optional[str] = None

class CardMovementFinal(BaseModel):
    """
    Modelo de salida enriquecido. Mantiene la Verdad Bancaria intacta.
    """
    id: str
    amount: float  # Intocable (Verdad Bancaria)
    date: date     # Intocable (Verdad Bancaria)
    
    # Datos enriquecidos por IA
    description_raw: str
    description_clean: str
    merchant_name: str
    category: str
    
    # Detecciones específicas de tarjetas de crédito
    is_commission: bool
    is_interest: bool
    
    # Sistema de Confianza — rango estrictamente validado [0.0, 1.0]
    # Si la IA devuelve un valor fuera de rango, Pydantic lanza ValidationError.
    confidence_score: Annotated[float, Field(default=0.0, ge=0.0, le=1.0)]
    needs_review: bool = False
