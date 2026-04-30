from sqlalchemy import Column, String, Float, Boolean, Date, DateTime, Text
from datetime import datetime
from core.database import Base

class MovementRecord(Base):
    """
    Representación persistente de un movimiento para la 'Memoria de Auditoría'.
    Permite consultar meses pasados sin entrar al banco.
    """
    __tablename__ = "movements"

    id = Column(String, primary_key=True, index=True) # UUID o Hash único
    client_id = Column(String, index=True)           # Correo o ID de cliente auditor
    bank_name = Column(String, index=True)           # BBVA, Banorte, etc.
    
    amount = Column(Float)
    date = Column(Date)
    description_raw = Column(Text)
    description_clean = Column(String)
    merchant_name = Column(String)
    category = Column(String)
    
    is_commission = Column(Boolean, default=False)
    is_interest = Column(Boolean, default=False)
    confidence_score = Column(Float)
    needs_review = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    extracted_at = Column(DateTime, default=datetime.utcnow)
