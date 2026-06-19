from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.core.config import Settings
from models.explainer import _extract_token_attributions, generate_shap_explanations


def test_extract_token_attributions_from_shap_like_values() -> None:
    """
    Verifies conversion from SHAP-like values into frontend attribution rows.
    """
    shap_values = SimpleNamespace(
        data=[["Bitcoin", "surges", "after", "SEC"]],
        values=[[[0.1, -0.2], [0.6, 0.1], [0.02, 0.01], [-0.4, 0.3]]],
    )

    explanations = _extract_token_attributions(shap_values, max_items=3)

    assert [item.word for item in explanations] == ["surges", "SEC", "Bitcoin"]
    assert explanations[0].weight == 0.6
    assert explanations[1].weight == -0.4


def test_extract_token_attributions_flattens_nested_batch_tokens() -> None:
    """
    Verifies nested SHAP token batches do not render as one giant string.
    """
    shap_values = SimpleNamespace(
        data=[[["Trump ", "walks ", "out ", "interview ", "claims"]]],
        values=[[[[0.1, -0.2], [0.7, 0.1], [0.05, 0.02], [-0.5, 0.1], [0.3, -0.1]]]],
    )

    explanations = _extract_token_attributions(shap_values, max_items=5)

    assert [item.word for item in explanations] == [
        "walks",
        "interview",
        "claims",
        "Trump",
        "out",
    ]
    assert all("[" not in item.word for item in explanations)
    assert all(isinstance(item.weight, float) for item in explanations)


def test_generate_shap_explanations_uses_mocked_explainer() -> None:
    """
    Verifies SHAP explanation flow without loading a real model.
    """
    fake_shap_values = SimpleNamespace(
        data=[["Guaranteed", "profit"]],
        values=[[[0.7, 0.2], [-0.1, 0.05]]],
    )
    fake_explainer = Mock(return_value=fake_shap_values)

    with patch("models.explainer._load_shap_explainer", return_value=fake_explainer):
        explanations = generate_shap_explanations(
            "Guaranteed profit",
            settings=Settings(roberta_model_name_or_path="local-model"),
        )

    assert explanations[0].word == "Guaranteed"
    assert explanations[0].weight == 0.7
    fake_explainer.assert_called_once_with(["Guaranteed profit"])


def test_generate_shap_explanations_fails_without_model_path() -> None:
    """
    Verifies that missing RoBERTa configuration is explicit for SHAP.
    """
    with pytest.raises(RuntimeError, match="ROBERTA_MODEL_NAME_OR_PATH"):
        generate_shap_explanations(
            "Bitcoin update.",
            settings=Settings(roberta_model_name_or_path=""),
        )
