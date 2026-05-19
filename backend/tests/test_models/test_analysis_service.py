from unittest.mock import patch

from app.schemas.analysis import AnalyzeRequest, SourceMatch
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
    assert result.blockchain.network == "Stage 1 Local Proof"


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
