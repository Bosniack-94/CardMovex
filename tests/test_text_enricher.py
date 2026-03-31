"""
Tests del TextEnricher con mocks de OpenAI.

Por qué mockeamos OpenAI:
- Los tests no deben hacer llamadas HTTP reales: son lentos, cuestan dinero y fallan sin red.
- Mockeamos AsyncOpenAI para controlar exactamente qué devuelve la "IA" en cada escenario.
- Esto nos permite probar nuestra lógica de negocio (parseo, thresholds, fallback) en aislamiento.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from processors.text_enricher import TextEnricher
from schemas.movements import CardMovementRaw, CardMovementFinal


# === Respuestas mock que simula OpenAI ===

def _make_openai_response(payload: dict) -> MagicMock:
    """Construye un objeto mock con la misma estructura que el response de OpenAI."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(payload)
    return mock_response


MOCK_OXXO_RESPONSE = {
    "description_clean": "OXXO Gas Insurgentes",
    "merchant_name": "OXXO",
    "category": "Comida",
    "is_commission": False,
    "is_interest": False,
    "confidence_score": 0.97,
}

MOCK_COMMISSION_RESPONSE = {
    "description_clean": "Anualidad Tarjeta Visa BBVA",
    "merchant_name": "BBVA",
    "category": "Comisiones",
    "is_commission": True,
    "is_interest": False,
    "confidence_score": 0.99,
}

MOCK_INTEREST_RESPONSE = {
    "description_clean": "Intereses Moratorios Banorte Enero",
    "merchant_name": "Banorte",
    "category": "Intereses",
    "is_commission": False,
    "is_interest": True,
    "confidence_score": 0.99,
}

MOCK_LOW_CONFIDENCE_RESPONSE = {
    "description_clean": "Transacción Desconocida",
    "merchant_name": "Desconocido",
    "category": "Otros",
    "is_commission": False,
    "is_interest": False,
    "confidence_score": 0.60,  # Debajo del threshold → needs_review = True
}


class TestTextEnricher:

    @pytest.fixture
    def enricher(self) -> TextEnricher:
        """Instancia del TextEnricher con cliente OpenAI mockeado."""
        with patch("processors.text_enricher.AsyncOpenAI"):
            instance = TextEnricher()
        return instance

    @pytest.fixture
    def raw_oxxo(self) -> CardMovementRaw:
        return CardMovementRaw(
            id="mov-001", description_raw="OXXO GAS INSURGENTES CDMX",
            amount=250.50, date=date(2026, 3, 15)
        )

    @pytest.fixture
    def raw_commission(self) -> CardMovementRaw:
        return CardMovementRaw(
            id="mov-002", description_raw="ANUALIDAD TRIB VISA BBVA",
            amount=899.00, date=date(2026, 1, 1)
        )

    @pytest.fixture
    def raw_interest(self) -> CardMovementRaw:
        return CardMovementRaw(
            id="mov-003", description_raw="INT MORATORIOS BANORTE ENE",
            amount=312.75, date=date(2026, 2, 1)
        )

    async def test_empty_batch_returns_empty_list(self, enricher: TextEnricher):
        """Un batch vacío debe retornar [] sin llamar a la API."""
        result = await enricher.enrich_movements([])
        assert result == []

    async def test_verdad_bancaria_amount_is_never_modified(self, enricher: TextEnricher, raw_oxxo: CardMovementRaw):
        """El amount del banco debe pasar intacto. La IA no lo toca."""
        enricher.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(MOCK_OXXO_RESPONSE)
        )
        results = await enricher.enrich_movements([raw_oxxo])
        assert results[0].amount == raw_oxxo.amount  # Verdad Bancaria intacta

    async def test_verdad_bancaria_date_is_never_modified(self, enricher: TextEnricher, raw_oxxo: CardMovementRaw):
        """La fecha del banco debe pasar intacta. La IA no la toca."""
        enricher.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(MOCK_OXXO_RESPONSE)
        )
        results = await enricher.enrich_movements([raw_oxxo])
        assert results[0].date == raw_oxxo.date  # Verdad Bancaria intacta

    async def test_commission_detection(self, enricher: TextEnricher, raw_commission: CardMovementRaw):
        """Una anualidad BBVA debe marcarse como is_commission=True."""
        enricher.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(MOCK_COMMISSION_RESPONSE)
        )
        results = await enricher.enrich_movements([raw_commission])
        assert results[0].is_commission is True
        assert results[0].is_interest is False
        assert results[0].category == "Comisiones"

    async def test_interest_detection(self, enricher: TextEnricher, raw_interest: CardMovementRaw):
        """Intereses moratorios deben marcarse como is_interest=True."""
        enricher.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(MOCK_INTEREST_RESPONSE)
        )
        results = await enricher.enrich_movements([raw_interest])
        assert results[0].is_interest is True
        assert results[0].is_commission is False
        assert results[0].category == "Intereses"

    async def test_low_confidence_triggers_needs_review(self, enricher: TextEnricher, raw_oxxo: CardMovementRaw):
        """confidence_score < 0.85 debe disparar needs_review = True."""
        enricher.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(MOCK_LOW_CONFIDENCE_RESPONSE)
        )
        results = await enricher.enrich_movements([raw_oxxo])
        assert results[0].needs_review is True
        assert results[0].confidence_score == 0.60

    async def test_api_failure_returns_fallback(self, enricher: TextEnricher, raw_oxxo: CardMovementRaw):
        """Si la API de OpenAI falla, debe retornar un fallback con needs_review=True."""
        enricher.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Simulated API failure")
        )
        results = await enricher.enrich_movements([raw_oxxo])
        assert len(results) == 1
        assert results[0].needs_review is True
        assert results[0].confidence_score == 0.0
        assert results[0].amount == raw_oxxo.amount   # Verdad Bancaria sobrevive al error

    async def test_batch_preserves_order(
        self, enricher: TextEnricher,
        raw_oxxo: CardMovementRaw,
        raw_commission: CardMovementRaw,
        raw_interest: CardMovementRaw,
    ):
        """
        asyncio.gather puede retornar resultados en cualquier orden interno,
        pero gather mantiene el orden de las tareas. Verificamos que
        el id del resultado corresponde al movimiento correcto.
        """
        responses = [MOCK_OXXO_RESPONSE, MOCK_COMMISSION_RESPONSE, MOCK_INTEREST_RESPONSE]
        enricher.client.chat.completions.create = AsyncMock(
            side_effect=[_make_openai_response(r) for r in responses]
        )
        batch = [raw_oxxo, raw_commission, raw_interest]
        results = await enricher.enrich_movements(batch)
        assert results[0].id == "mov-001"
        assert results[1].id == "mov-002"
        assert results[2].id == "mov-003"
