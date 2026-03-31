"""
Tests unitarios para schemas/movements.py
Validan que los contratos de datos Pydantic funcionen correctamente.
No requieren mocks ni contacto con APIs externas.
"""
import pytest
from datetime import date
from pydantic import ValidationError
from schemas.movements import CardMovementRaw, CardMovementFinal


class TestCardMovementRaw:
    """Tests del modelo de entrada (datos crudos de Belvo)."""

    def test_valid_movement(self):
        """Un movimiento válido debe instanciarse sin errores."""
        mov = CardMovementRaw(
            id="test-001",
            description_raw="PAGO UBER CDMX",
            amount=95.50,
            date=date(2026, 3, 31),
        )
        assert mov.id == "test-001"
        assert mov.amount == 95.50

    def test_optional_fields_default_none(self):
        """Los campos opcionales category_raw y merchant_raw deben ser None por defecto."""
        mov = CardMovementRaw(
            id="test-002",
            description_raw="STARBUCKS POLANCO",
            amount=85.0,
            date=date(2026, 3, 31),
        )
        assert mov.category_raw is None
        assert mov.merchant_raw is None

    def test_missing_required_field_raises_error(self):
        """Omitir un campo requerido debe lanzar ValidationError."""
        with pytest.raises(ValidationError):
            CardMovementRaw(
                id="test-003",
                # description_raw faltante — debe fallar
                amount=100.0,
                date=date(2026, 3, 31),
            )


class TestCardMovementFinal:
    """Tests del modelo de salida (datos enriquecidos)."""

    def test_verdad_bancaria_preserved(self):
        """amount y date deben mantenerse exactamente como vienen del banco."""
        original_amount = 1234.56
        original_date = date(2026, 1, 15)
        mov = CardMovementFinal(
            id="final-001",
            amount=original_amount,
            date=original_date,
            description_raw="ANUALIDAD BBVA",
            description_clean="Anualidad Tarjeta BBVA",
            merchant_name="BBVA",
            category="Comisiones",
            is_commission=True,
            is_interest=False,
            confidence_score=0.99,
            needs_review=False,
        )
        assert mov.amount == original_amount
        assert mov.date == original_date

    def test_confidence_score_upper_bound(self):
        """confidence_score mayor a 1.0 debe lanzar ValidationError."""
        with pytest.raises(ValidationError):
            CardMovementFinal(
                id="final-002",
                amount=500.0,
                date=date(2026, 3, 31),
                description_raw="TEST",
                description_clean="Test",
                merchant_name="Test",
                category="Otros",
                is_commission=False,
                is_interest=False,
                confidence_score=1.5,  # Inválido — fuera de rango
                needs_review=False,
            )

    def test_confidence_score_lower_bound(self):
        """confidence_score menor a 0.0 debe lanzar ValidationError."""
        with pytest.raises(ValidationError):
            CardMovementFinal(
                id="final-003",
                amount=500.0,
                date=date(2026, 3, 31),
                description_raw="TEST",
                description_clean="Test",
                merchant_name="Test",
                category="Otros",
                is_commission=False,
                is_interest=False,
                confidence_score=-0.1,  # Inválido — negativo
                needs_review=False,
            )

    def test_needs_review_defaults_false(self):
        """needs_review debe ser False por defecto."""
        mov = CardMovementFinal(
            id="final-004",
            amount=100.0,
            date=date(2026, 3, 31),
            description_raw="OXXO",
            description_clean="OXXO",
            merchant_name="OXXO",
            category="Comida",
            is_commission=False,
            is_interest=False,
            confidence_score=0.95,
        )
        assert mov.needs_review is False
