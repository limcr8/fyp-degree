from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import httpx

from app.core.config import Settings
from app.schemas.analysis import VerificationStatus
from models.linguistic import (
    LinguisticPrediction,
    _status_from_label,
    predict_linguistic_risk,
)


def test_status_from_label_maps_common_model_labels() -> None:
    """
    Verifies that common classifier labels map to frontend verdicts.
    """
    assert _status_from_label("FAKE") == VerificationStatus.FAKE
    assert _status_from_label("LABEL_1") == VerificationStatus.FAKE
    assert _status_from_label("REAL") == VerificationStatus.REAL
    assert _status_from_label("LABEL_0") == VerificationStatus.REAL
    assert _status_from_label("mixed") == VerificationStatus.UNCERTAIN


def test_predict_linguistic_risk_uses_mocked_transformer_outputs() -> None:
    """
    Verifies RoBERTa inference without loading a real Hugging Face model.
    """
    fake_inputs = {"input_ids": Mock(), "attention_mask": Mock()}
    fake_tokenizer = Mock(return_value=fake_inputs)
    fake_model = Mock()
    fake_model.config.id2label = {0: "REAL", 1: "FAKE"}
    fake_model.return_value = SimpleNamespace(logits=Mock())
    fake_torch = Mock()
    fake_torch.no_grad.return_value.__enter__ = Mock()
    fake_torch.no_grad.return_value.__exit__ = Mock(return_value=None)
    fake_torch.softmax.return_value = Mock()
    fake_torch.max.return_value = (SimpleNamespace(item=lambda: 0.87), SimpleNamespace(item=lambda: 1))

    with patch(
        "models.linguistic._load_linguistic_assets",
        return_value=(fake_tokenizer, fake_model),
    ), patch("models.linguistic._load_torch", return_value=fake_torch):
        prediction = predict_linguistic_risk(
            "Guaranteed 100x Bitcoin profit.",
            settings=Settings(
                roberta_model_name_or_path="local-model",
                openai_api_key="",
                gemini_api_key=""
            ),
        )

    assert isinstance(prediction, LinguisticPrediction)
    assert prediction.status == VerificationStatus.FAKE
    assert prediction.confidence > 0.8
    fake_model.eval.assert_called_once()


def test_predict_linguistic_risk_fails_without_model_path() -> None:
    """
    Verifies that missing both Gemini and RoBERTa configuration raises an explicit error.
    """
    with pytest.raises(RuntimeError, match="ROBERTA_MODEL_NAME_OR_PATH"):
        predict_linguistic_risk(
            "Bitcoin update.",
            settings=Settings(
                openai_api_key="",
                gemini_api_key="",
                roberta_model_name_or_path=""
            ),
        )


def test_predict_linguistic_risk_uses_gemini_api_when_configured() -> None:
    """
    Verifies that predict_linguistic_risk uses Gemini API when gemini_api_key is set.
    """
    settings = Settings(
        gemini_api_key="test-gemini-key",
        roberta_model_name_or_path="",
    )
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/..."),
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict": "REAL", "confidence": 0.95, "explanation": "The text contains a credible official statement."}'
                            }
                        ]
                    }
                }
            ]
        },
    )

    with patch("models.linguistic.httpx.post", return_value=response) as mock_post:
        prediction = predict_linguistic_risk("Bitcoin climbs.", settings=settings)

    assert mock_post.called
    assert prediction.status == VerificationStatus.REAL
    assert prediction.confidence == 0.95
    assert prediction.explanation == "Gemini LLM: The text contains a credible official statement."


def test_predict_linguistic_risk_falls_back_on_gemini_error() -> None:
    """
    Verifies that predict_linguistic_risk falls back to RoBERTa if Gemini API fails.
    """
    settings = Settings(
        gemini_api_key="test-gemini-key",
        roberta_model_name_or_path="local-model",
    )

    mock_post = Mock(side_effect=httpx.HTTPError("API error"))

    fake_inputs = {"input_ids": Mock(), "attention_mask": Mock()}
    fake_tokenizer = Mock(return_value=fake_inputs)
    fake_model = Mock()
    fake_model.config.id2label = {0: "REAL", 1: "FAKE"}
    fake_model.return_value = SimpleNamespace(logits=Mock())
    fake_torch = Mock()
    fake_torch.no_grad.return_value.__enter__ = Mock()
    fake_torch.no_grad.return_value.__exit__ = Mock(return_value=None)
    fake_torch.softmax.return_value = Mock()
    fake_torch.max.return_value = (SimpleNamespace(item=lambda: 0.88), SimpleNamespace(item=lambda: 0))

    with patch("models.linguistic.httpx.post", mock_post), \
         patch("models.linguistic._load_linguistic_assets", return_value=(fake_tokenizer, fake_model)), \
         patch("models.linguistic._load_torch", return_value=fake_torch):
        prediction = predict_linguistic_risk("Bitcoin climbs.", settings=settings)

    assert prediction.status == VerificationStatus.REAL
    assert prediction.confidence == 0.88
    fake_model.eval.assert_called_once()


def test_predict_linguistic_risk_with_search_context() -> None:
    """
    Verifies that predict_linguistic_risk forwards search context to the Gemini API prompt payload.
    """
    settings = Settings(
        gemini_api_key="test-gemini-key",
        roberta_model_name_or_path="",
    )
    search_context = [
        {
            "title": "SEC Approves Bitcoin ETF",
            "snippet": "The SEC has officially approved spot Bitcoin exchange-traded funds...",
            "link": "https://sec.gov/news/press-release",
            "source": "SEC"
        }
    ]
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/..."),
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict": "REAL", "confidence": 0.99, "explanation": "SEC official press release confirms the approval."}'
                            }
                        ]
                    }
                }
            ]
        },
    )

    with patch("models.linguistic.httpx.post", return_value=response) as mock_post:
        prediction = predict_linguistic_risk(
            "SEC approved Bitcoin ETF today.",
            settings=settings,
            search_context=search_context
        )

    assert mock_post.called
    # Get the sent prompt text and verify the search context snippets are in it
    payload = mock_post.call_args.kwargs["json"]
    prompt_text = payload["contents"][0]["parts"][0]["text"]
    assert "Retrieved Authoritative Search Context:" in prompt_text
    assert "SEC Approves Bitcoin ETF" in prompt_text
    assert "sec.gov/news/press-release" in prompt_text
    
    assert prediction.status == VerificationStatus.REAL
    assert prediction.confidence == 0.99
    assert prediction.explanation == "Gemini LLM: SEC official press release confirms the approval."


def test_predict_linguistic_risk_parses_gemini_attributions() -> None:
    """
    Verifies that predict_linguistic_risk parses LLM attributions from the Gemini JSON response.
    """
    settings = Settings(
        gemini_api_key="test-gemini-key",
        roberta_model_name_or_path="",
    )
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/..."),
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict": "FAKE", "confidence": 0.92, "explanation": "sensational claim", "attributions": [{"word": "monolith", "weight": 0.78}]}'
                            }
                        ]
                    }
                }
            ]
        },
    )

    with patch("models.linguistic.httpx.post", return_value=response):
        prediction = predict_linguistic_risk("Bitcoin updates.", settings=settings)

    assert prediction.status == VerificationStatus.FAKE
    assert prediction.confidence == 0.92
    assert prediction.attributions == [{"word": "monolith", "weight": 0.78}]


def test_predict_linguistic_risk_uses_openai_api_when_configured() -> None:
    """
    Verifies that predict_linguistic_risk uses OpenAI API when openai_api_key is set.
    """
    settings = Settings(
        openai_api_key="test-openai-key",
        gemini_api_key="",
        roberta_model_name_or_path="",
    )
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"verdict": "REAL", "confidence": 0.96, "explanation": "OpenAI classification success."}'
                    }
                }
            ]
        },
    )

    with patch("models.linguistic.httpx.post", return_value=response) as mock_post:
        prediction = predict_linguistic_risk("Bitcoin is scaling.", settings=settings)

    assert mock_post.called
    assert prediction.status == VerificationStatus.REAL
    assert prediction.confidence == 0.96
    assert prediction.explanation == "OpenAI LLM: OpenAI classification success."


def test_predict_linguistic_risk_falls_back_to_gemini_on_openai_error() -> None:
    """
    Verifies that predict_linguistic_risk falls back to Gemini if OpenAI API fails.
    """
    settings = Settings(
        openai_api_key="test-openai-key",
        gemini_api_key="test-gemini-key",
        roberta_model_name_or_path="",
    )

    # First call (OpenAI) fails, second call (Gemini) succeeds
    openai_error_response = httpx.Response(status_code=500, request=httpx.Request("POST", "https://api.openai.com/..."))
    gemini_success_response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/..."),
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict": "FAKE", "confidence": 0.85, "explanation": "Fallback to Gemini succeeded."}'
                            }
                        ]
                    }
                }
            ]
        },
    )

    # Mock post returning side effects
    mock_post = Mock(side_effect=[openai_error_response, gemini_success_response])

    with patch("models.linguistic.httpx.post", mock_post):
        prediction = predict_linguistic_risk("Bitcoin reaches new ATH.", settings=settings)

    assert mock_post.call_count == 2
    assert prediction.status == VerificationStatus.FAKE
    assert prediction.confidence == 0.85
    assert prediction.explanation == "Gemini LLM: Fallback to Gemini succeeded."

