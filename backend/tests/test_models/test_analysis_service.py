from unittest.mock import patch

from app.schemas.analysis import AnalyzeRequest, BlockchainProof, SourceMatch, VerificationStatus
from models.linguistic import LinguisticPrediction
from models.analysis_service import analyze_text


def test_analyze_text_returns_stable_contract() -> None:
    """
    Verifies that the Stage 1 analysis service returns a complete response.
    """
    request = AnalyzeRequest(text="Ethereum price rises after market update.")

    result = analyze_text(request)

    assert result.text == request.text
    assert result.id
    assert result.status.value in {"REAL", "FAKE", "UNCERTAIN"}
    assert 0 <= result.confidence <= 1
    assert result.shap_data
    assert result.sources
    assert result.blockchain.network == "Local Integrity Proof"


def test_analyze_text_uses_topic_verification_sources() -> None:
    """
    Verifies that the analysis service delegates source matching to Stage 2.
    """
    request = AnalyzeRequest(text="Bitcoin rises after Reuters report.")

    def fake_verify_topics(text: str) -> list[SourceMatch]:
        assert text == request.text
        return [
            SourceMatch(
                name="Reuters",
                confirmed=True,
                url="https://www.reuters.com/markets/bitcoin",
            )
        ]

    with patch("models.analysis_service.verify_topics", side_effect=fake_verify_topics):
        result = analyze_text(request)

    assert result.sources[0].name == "Reuters"
    assert result.sources[0].confirmed is True
    assert result.sources[0].url == "https://www.reuters.com/markets/bitcoin"


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
    Verifies that the analysis service delegates verdicts to Stage 4.
    """
    request = AnalyzeRequest(text="Bitcoin rises after Reuters report.")
    prediction = LinguisticPrediction(
        status=VerificationStatus.REAL,
        confidence=0.91,
        explanation="RoBERTa classified the article as likely credible.",
    )

    with patch("models.analysis_service.predict_linguistic_risk", return_value=prediction):
        result = analyze_text(request)

    assert result.status == VerificationStatus.REAL
    assert result.confidence == 0.91
    assert result.explanation == prediction.explanation
