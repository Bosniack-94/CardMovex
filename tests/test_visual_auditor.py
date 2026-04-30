"""
Tests del VisualAuditor con mocks de GPT-4o Vision.

Principio: Mockeamos la capa de red (OpenAI) para probar nuestra lógica de:
- Mapeo de respuesta JSON al Enum AuditVerdict
- Cálculo de needs_human_review según confidence_score
- Fallback correcto cuando la API Vision falla
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from processors.visual_auditor import VisualAuditor
from schemas.audit import AuditRequest, AuditVerdict


def _make_vision_response(payload: dict) -> MagicMock:
    """Construye un mock con la misma forma que el response de GPT-4o."""
    mock = MagicMock()
    mock.choices[0].message.content = json.dumps(payload)
    return mock


MOCK_CONFIRMED = {
    "amount_in_image": 899.00,
    "merchant_in_image": "BBVA BANCOMER",
    "amounts_match": True,
    "verdict": "CONFIRMED",
    "reasoning": "El recibo muestra un cargo de $899.00 MXN que coincide exactamente con el registrado.",
    "confidence_score": 0.97,
}

MOCK_DISPUTED = {
    "amount_in_image": 450.00,
    "merchant_in_image": "BBVA BANCOMER",
    "amounts_match": False,
    "verdict": "DISPUTED",
    "reasoning": "La imagen muestra $450.00 MXN pero el sistema registró $899.00. Discrepancia de $449.00.",
    "confidence_score": 0.95,
}

MOCK_INCONCLUSIVE = {
    "amount_in_image": None,
    "merchant_in_image": None,
    "amounts_match": None,
    "verdict": "INCONCLUSIVE",
    "reasoning": "La imagen es ilegible o no muestra un recibo reconocible.",
    "confidence_score": 0.30,
}


@pytest.fixture
def audit_request() -> AuditRequest:
    return AuditRequest(
        movement_id="mov-001",
        description_raw="ANUALIDAD TRIB VISA BBVA",
        amount=899.00,
        image_base64="data:image/jpeg;base64,/9j/fakeimagedatafortest==",
    )


@pytest.fixture
def auditor() -> VisualAuditor:
    with patch("processors.visual_auditor.AsyncOpenAI"):
        instance = VisualAuditor()
    return instance


class TestVisualAuditor:

    async def test_confirmed_verdict(self, auditor: VisualAuditor, audit_request: AuditRequest):
        """Cuando la imagen confirma el monto, el veredicto es CONFIRMED."""
        auditor.client.chat.completions.create = AsyncMock(
            return_value=_make_vision_response(MOCK_CONFIRMED)
        )
        result = await auditor.audit_movement(audit_request)
        assert result.verdict == AuditVerdict.CONFIRMED
        assert result.amounts_match is True
        assert result.needs_human_review is False

    async def test_disputed_verdict(self, auditor: VisualAuditor, audit_request: AuditRequest):
        """Cuando el monto de la imagen difiere, el veredicto es DISPUTED."""
        auditor.client.chat.completions.create = AsyncMock(
            return_value=_make_vision_response(MOCK_DISPUTED)
        )
        result = await auditor.audit_movement(audit_request)
        assert result.verdict == AuditVerdict.DISPUTED
        assert result.amounts_match is False
        assert result.amount_in_image == 450.00

    async def test_inconclusive_triggers_human_review(self, auditor: VisualAuditor, audit_request: AuditRequest):
        """INCONCLUSIVE siempre debe disparar needs_human_review=True."""
        auditor.client.chat.completions.create = AsyncMock(
            return_value=_make_vision_response(MOCK_INCONCLUSIVE)
        )
        result = await auditor.audit_movement(audit_request)
        assert result.verdict == AuditVerdict.INCONCLUSIVE
        assert result.needs_human_review is True

    async def test_low_confidence_triggers_human_review(self, auditor: VisualAuditor, audit_request: AuditRequest):
        """confidence_score < 0.75 debe forzar needs_human_review=True."""
        low_conf = {**MOCK_CONFIRMED, "confidence_score": 0.60}
        auditor.client.chat.completions.create = AsyncMock(
            return_value=_make_vision_response(low_conf)
        )
        result = await auditor.audit_movement(audit_request)
        assert result.needs_human_review is True

    async def test_api_failure_returns_inconclusive_fallback(self, auditor: VisualAuditor, audit_request: AuditRequest):
        """Si Vision API falla, el fallback debe ser INCONCLUSIVE + needs_human_review=True."""
        auditor.client.chat.completions.create = AsyncMock(
            side_effect=Exception("GPT-4o Vision timeout")
        )
        result = await auditor.audit_movement(audit_request)
        assert result.verdict == AuditVerdict.INCONCLUSIVE
        assert result.needs_human_review is True
        assert result.confidence_score == 0.0
        assert result.movement_id == "mov-001"  # ID siempre preservado

    async def test_invalid_verdict_string_defaults_to_inconclusive(self, auditor: VisualAuditor, audit_request: AuditRequest):
        """Si la IA devuelve un verdict string inválido, debe defaultear a INCONCLUSIVE."""
        bad_verdict = {**MOCK_CONFIRMED, "verdict": "MAYBE"}
        auditor.client.chat.completions.create = AsyncMock(
            return_value=_make_vision_response(bad_verdict)
        )
        result = await auditor.audit_movement(audit_request)
        assert result.verdict == AuditVerdict.INCONCLUSIVE
