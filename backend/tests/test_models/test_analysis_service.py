from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.schemas.analysis import (
    AnalyzeRequest,
    BlockchainProof,
    ShapExplanation,
    SourceMatch,
    VerificationStatus,
)
from models.linguistic import LinguisticPrediction
from models.analysis_service import analyze_text


@pytest.fixture(autouse=True)
def mock_empty_settings() -> None:
    mock_settings = Settings(
        roberta_model_name_or_path="",
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
    with patch("models.verification.get_settings", return_value=mock_settings), \
         patch("models.integrity_proof.get_settings", return_value=mock_settings), \
         patch("models.linguistic.get_settings", return_value=mock_settings), \
         patch("models.explainer.get_settings", return_value=mock_settings), \
         patch("models.analysis_service.get_settings", return_value=mock_settings):
        yield


def test_analyze_text_returns_stable_contract() -> None:
    """
    Verifies that the Stage 1 analysis service returns a complete response.
    """
    request = AnalyzeRequest(text="Ethereum price rises after market update.")

    result = analyze_text(request)

    assert result.text == request.text
    assert result.id
    assert result.classification.verdict in {"REAL", "FAKE", "UNCERTAIN"}
    assert 0 <= result.classification.confidence <= 1
    assert result.explanation.shap_data
    assert result.verification.sources
    assert result.blockchain.network == "Local Integrity Proof"


def test_analyze_text_uses_topic_verification_sources() -> None:
    """
    Verifies that the analysis service delegates source matching to Stage 2.
    """
    request = AnalyzeRequest(text="Bitcoin rises after Reuters report.")

    def fake_verify_topics_with_context(text: str, *args, **kwargs) -> tuple[list[SourceMatch], list[dict[str, str]]]:
        assert text == request.text
        return [
            SourceMatch(
                name="Reuters",
                confirmed=True,
                url="https://www.reuters.com/markets/bitcoin",
            )
        ], []

    with patch("models.analysis_service.verify_topics_with_context", side_effect=fake_verify_topics_with_context):
        result = analyze_text(request)

    assert result.verification.sources[0].name == "Reuters"
    assert result.verification.sources[0].confirmed is True
    assert result.verification.sources[0].url == "https://www.reuters.com/markets/bitcoin"


def test_analyze_text_uses_integrity_proof_service() -> None:
    """
    Verifies that the analysis service delegates proof creation to Stage 3.
    """
    request = AnalyzeRequest(text="Bitcoin rises after Reuters report.")
    proof = BlockchainProof(
        transactionHash="0xabc",
        blockNumber=10,
        timestamp="2026-05-19 00:00:00 UTC",
        ipfsHash="QmTestCid",
        network="EVM Testnet",
    )

    with patch("models.analysis_service.create_integrity_proof", return_value=proof):
        result = analyze_text(request)

    assert result.blockchain == proof


def test_analyze_text_uses_linguistic_prediction_service() -> None:
    """
    Verifies that the analysis service delegates verdicts to Stage 4 (predict_linguistic_risk)
    under uncertain conditions.
    """
    request = AnalyzeRequest(text="Bitcoin rises after positive market sentiment update.")
    prediction = LinguisticPrediction(
        status=VerificationStatus.REAL,
        confidence=0.91,
        explanation="RoBERTa classified the article as likely credible.",
    )

    mock_settings_with_llm = Settings(
        roberta_model_name_or_path="",
        google_api_key="",
        google_cse_id="",
        gemini_api_key="mock_gemini_key",
        openai_api_key="",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )

    with patch("models.analysis_service.get_settings", return_value=mock_settings_with_llm), \
         patch("models.analysis_service.predict_linguistic_risk", return_value=prediction):
        result = analyze_text(request)

    assert result.classification.verdict == VerificationStatus.REAL.value
    assert result.classification.confidence == 0.91
    assert result.classification.explanation == prediction.explanation


def test_analyze_text_uses_shap_explanation_service() -> None:
    """
    Verifies that the analysis service delegates attribution to Stage 5.
    """
    request = AnalyzeRequest(text="Bitcoin rises after Reuters report.")
    shap_data = [ShapExplanation(word="Bitcoin", weight=0.42)]

    with patch("models.analysis_service.generate_shap_explanations", return_value=shap_data):
        result = analyze_text(request)

    assert result.explanation.shap_data == shap_data


def test_analyze_text_uses_resolved_article_text() -> None:
    """
    Verifies URL/article extraction runs before analysis subsystems.
    """
    request = AnalyzeRequest(text="https://example.com/news")

    with patch(
        "models.analysis_service.resolve_input_text",
        return_value="Extracted article text about Ethereum.",
    ):
        result = analyze_text(request)

    assert result.text == "Extracted article text about Ethereum."
