from functools import lru_cache
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.analysis import ShapExplanation
from models.linguistic import _load_linguistic_assets


def generate_shap_explanations(
    text: str,
    settings: Settings | None = None,
    max_items: int = 8,
) -> list[ShapExplanation]:
    """
    Generates SHAP token attributions for the configured RoBERTa model.

    Args:
        text (str): News text to explain.
        settings (Settings | None): Optional runtime settings override.
        max_items (int): Maximum number of attribution rows to return.

    Returns:
        list[ShapExplanation]: Frontend-compatible token attributions.
    """
    active_settings = settings or get_settings()
    model_name_or_path = active_settings.roberta_model_name_or_path

    if not model_name_or_path:
        raise RuntimeError(
            "ROBERTA_MODEL_NAME_OR_PATH must be configured before SHAP explanation."
        )

    explainer = _load_shap_explainer(model_name_or_path)
    shap_values = explainer([text])
    explanations = _extract_token_attributions(shap_values, max_items=max_items)

    if not explanations:
        raise RuntimeError("SHAP did not return token attributions.")

    return explanations


def _extract_token_attributions(
    shap_values: Any,
    max_items: int = 8,
) -> list[ShapExplanation]:
    """
    Converts SHAP output into frontend attribution rows.

    Args:
        shap_values (Any): SHAP explanation object.
        max_items (int): Maximum number of rows to return.

    Returns:
        list[ShapExplanation]: Sorted token attributions.
    """
    tokens = _first_sample(getattr(shap_values, "data", []))
    values = _first_sample(getattr(shap_values, "values", []))
    explanations: list[ShapExplanation] = []

    for token, token_values in zip(tokens, values):
        word = _clean_token(str(token))
        if not word:
            continue
        explanations.append(
            ShapExplanation(word=word, weight=_token_score(token_values))
        )

    explanations.sort(key=lambda item: abs(item.weight), reverse=True)
    return explanations[:max_items]


def _first_sample(value: Any) -> list[Any]:
    """
    Extracts the first sample from SHAP batch output.

    Args:
        value (Any): SHAP data or values field.

    Returns:
        list[Any]: First sample sequence.
    """
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list) and value and isinstance(value[0], (list, tuple)):
        return list(value[0])
    if isinstance(value, list):
        return value
    return []


def _token_score(token_values: Any) -> float:
    """
    Collapses per-class SHAP scores into one signed token score.

    Args:
        token_values (Any): SHAP value for one token.

    Returns:
        float: Signed score with largest absolute class contribution.
    """
    if hasattr(token_values, "tolist"):
        token_values = token_values.tolist()
    if isinstance(token_values, tuple):
        token_values = list(token_values)
    if isinstance(token_values, list):
        numeric_values = [float(value) for value in token_values]
        return round(max(numeric_values, key=abs), 4)
    return round(float(token_values), 4)


def _clean_token(token: str) -> str:
    """
    Removes common tokenizer artifacts from display tokens.

    Args:
        token (str): Raw SHAP token.

    Returns:
        str: Clean display token.
    """
    cleaned = token.replace("Ġ", "").replace("Ċ", "").strip()
    return cleaned.strip(".,!?;:()[]{}\"'")


@lru_cache
def _load_shap_explainer(model_name_or_path: str) -> Any:
    """
    Loads a SHAP explainer for the configured RoBERTa classifier.

    Args:
        model_name_or_path (str): Local path or Hugging Face model ID.

    Returns:
        Any: SHAP explainer.
    """
    try:
        import shap
    except ImportError as exc:
        raise RuntimeError("shap is required for model explanations.") from exc

    classifier = _build_text_classifier_pipeline(model_name_or_path)
    return shap.Explainer(classifier)


def _build_text_classifier_pipeline(model_name_or_path: str) -> Any:
    """
    Builds a Hugging Face text-classification pipeline for SHAP.

    Args:
        model_name_or_path (str): Local path or Hugging Face model ID.

    Returns:
        Any: Text classification pipeline.
    """
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError("transformers is required for SHAP explanations.") from exc

    tokenizer, model = _load_linguistic_assets(model_name_or_path)
    return pipeline(
        "text-classification",
        model=model,
        tokenizer=tokenizer,
        top_k=None,
        truncation=True,
    )
