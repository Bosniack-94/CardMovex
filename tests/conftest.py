"""
conftest.py — Fixtures compartidas para todos los tests de CardMovex.

Por qué conftest.py:
Pytest lo carga automáticamente: cualquier fixture definida aquí
está disponible en todos los archivos test_*.py sin necesidad de importarla.
"""
import pytest
from datetime import date
from schemas.movements import CardMovementRaw


@pytest.fixture
def raw_movement_oxxo() -> CardMovementRaw:
    """Movimiento típico de consumo en comercio (happy path)."""
    return CardMovementRaw(
        id="mov-001",
        description_raw="OXXO GAS INSURGENTES CDMX",
        amount=250.50,
        date=date(2026, 3, 15),
    )


@pytest.fixture
def raw_movement_commission() -> CardMovementRaw:
    """Movimiento de anualidad — debe detectarse como comisión."""
    return CardMovementRaw(
        id="mov-002",
        description_raw="ANUALIDAD TRIB VISA BBVA",
        amount=899.00,
        date=date(2026, 1, 1),
    )


@pytest.fixture
def raw_movement_interest() -> CardMovementRaw:
    """Movimiento de intereses moratorios — debe detectarse como interés."""
    return CardMovementRaw(
        id="mov-003",
        description_raw="INT MORATORIOS BANORTE ENE",
        amount=312.75,
        date=date(2026, 2, 1),
    )


@pytest.fixture
def raw_batch_mixed(
    raw_movement_oxxo, raw_movement_commission, raw_movement_interest
) -> list[CardMovementRaw]:
    """Batch mixto de 3 movimientos para probar procesamiento paralelo."""
    return [raw_movement_oxxo, raw_movement_commission, raw_movement_interest]
