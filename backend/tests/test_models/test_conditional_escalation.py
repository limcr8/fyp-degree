from unittest.mock import MagicMock, patch
import pytest

from app.core.config import Settings
from app.schemas.analysis import VerificationStatus
from models.linguistic import LinguisticPrediction
from models.analysis_service import _predict_with_fallback


@pytest.fixture
def mock_settings_with_llm():
    return Settings(
        roberta_model_name_or_path="mock/roberta",
        google_api_key="google_key",
        google_cse_id="google_cse",
        gemini_api_key="gemini_key",
        openai_api_key="",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )


@pytest.fixture
def mock_settings_no_llm():
    return Settings(
        roberta_model_name_or_path="mock/roberta",
        google_api_key="",
        google_cse_id="",
        gemini_api_key="",
        openai_api_key="",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )


def test_predict_with_fallback_bypasses_llm_in_fast_mode(mock_settings_with_llm) -> None:
    """
    Verifies that _predict_with_fallback bypasses LLM escalation when fast_mode is True,
    even if the confidence is in the uncertain range (0.4 - 0.7) and LLM is configured.
    """
    roberta_pred = LinguisticPrediction(
        status=VerificationStatus.FAKE,
        confidence=0.55,
        explanation="RoBERTa result",
    )

    with patch("models.analysis_service.get_settings", return_value=mock_settings_with_llm), \
         patch("models.analysis_service.predict_with_roberta", return_value=roberta_pred) as mock_roberta, \
         patch("models.analysis_service.predict_linguistic_risk") as mock_llm:

        result = _predict_with_fallback("Some text", fast_mode=True)

        mock_roberta.assert_called_once_with("Some text", mock_settings_with_llm)
        mock_llm.assert_not_called()
        assert result == roberta_pred


def test_predict_with_fallback_bypasses_llm_on_high_confidence(mock_settings_with_llm) -> None:
    """
    Verifies that _predict_with_fallback bypasses LLM escalation when local prediction confidence
    is high (>= 0.7), outside of the uncertain range.
    """
    roberta_pred = LinguisticPrediction(
        status=VerificationStatus.REAL,
        confidence=0.85,
        explanation="RoBERTa high confidence result",
    )

    with patch("models.analysis_service.get_settings", return_value=mock_settings_with_llm), \
         patch("models.analysis_service.predict_with_roberta", return_value=roberta_pred) as mock_roberta, \
         patch("models.analysis_service.predict_linguistic_risk") as mock_llm:

        result = _predict_with_fallback("Some text", fast_mode=False)

        mock_roberta.assert_called_once_with("Some text", mock_settings_with_llm)
        mock_llm.assert_not_called()
        assert result == roberta_pred


def test_predict_with_fallback_bypasses_llm_on_low_confidence(mock_settings_with_llm) -> None:
    """
    Verifies that _predict_with_fallback bypasses LLM escalation when local prediction confidence
    is low (<= 0.4), outside of the uncertain range.
    """
    roberta_pred = LinguisticPrediction(
        status=VerificationStatus.UNCERTAIN,
        confidence=0.35,
        explanation="RoBERTa low confidence result",
    )

    with patch("models.analysis_service.get_settings", return_value=mock_settings_with_llm), \
         patch("models.analysis_service.predict_with_roberta", return_value=roberta_pred) as mock_roberta, \
         patch("models.analysis_service.predict_linguistic_risk") as mock_llm:

        result = _predict_with_fallback("Some text", fast_mode=False)

        mock_roberta.assert_called_once_with("Some text", mock_settings_with_llm)
        mock_llm.assert_not_called()
        assert result == roberta_pred


def test_predict_with_fallback_escalates_on_uncertainty(mock_settings_with_llm) -> None:
    """
    Verifies that _predict_with_fallback escalates to LLM when confidence is uncertain (0.4 - 0.7)
    and LLM credentials are configured.
    """
    roberta_pred = LinguisticPrediction(
        status=VerificationStatus.FAKE,
        confidence=0.55,
        explanation="RoBERTa uncertain result",
    )
    llm_pred = LinguisticPrediction(
        status=VerificationStatus.FAKE,
        confidence=0.95,
        explanation="Gemini LLM RAG verified result",
    )

    with patch("models.analysis_service.get_settings", return_value=mock_settings_with_llm), \
         patch("models.analysis_service.predict_with_roberta", return_value=roberta_pred) as mock_roberta, \
         patch("models.analysis_service.predict_linguistic_risk", return_value=llm_pred) as mock_llm:

        result = _predict_with_fallback("Some text", fast_mode=False)

        mock_roberta.assert_called_once_with("Some text", mock_settings_with_llm)
        mock_llm.assert_called_once_with("Some text", settings=mock_settings_with_llm, search_context=None, language="en")
        assert result == llm_pred


def test_predict_with_fallback_handles_llm_failure_gracefully(mock_settings_with_llm) -> None:
    """
    Verifies that if LLM escalation fails/raises exception, it gracefully falls back to the
    initial RoBERTa prediction instead of crashing.
    """
    roberta_pred = LinguisticPrediction(
        status=VerificationStatus.REAL,
        confidence=0.60,
        explanation="RoBERTa uncertain result",
    )

    with patch("models.analysis_service.get_settings", return_value=mock_settings_with_llm), \
         patch("models.analysis_service.predict_with_roberta", return_value=roberta_pred) as mock_roberta, \
         patch("models.analysis_service.predict_linguistic_risk", side_effect=Exception("API limit exceeded")) as mock_llm:

        result = _predict_with_fallback("Some text", fast_mode=False)

        mock_roberta.assert_called_once_with("Some text", mock_settings_with_llm)
        mock_llm.assert_called_once()
        # Should return roberta_pred despite LLM error
        assert result == roberta_pred
