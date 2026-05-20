from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

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
            settings=Settings(roberta_model_name_or_path="local-model"),
        )

    assert isinstance(prediction, LinguisticPrediction)
    assert prediction.status == VerificationStatus.FAKE
    assert prediction.confidence > 0.8
    fake_model.eval.assert_called_once()


def test_predict_linguistic_risk_fails_without_model_path() -> None:
    """
    Verifies that missing RoBERTa configuration is explicit.
    """
    with pytest.raises(RuntimeError, match="ROBERTA_MODEL_NAME_OR_PATH"):
        predict_linguistic_risk("Bitcoin update.", settings=Settings())
