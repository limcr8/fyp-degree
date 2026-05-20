from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.analysis import VerificationStatus


@dataclass(frozen=True)
class LinguisticPrediction:
    """
    RoBERTa linguistic risk prediction.

    Attributes:
        status (VerificationStatus): Credibility verdict.
        confidence (float): Model confidence score from 0 to 1.
        explanation (str): Human-readable model explanation.
    """

    status: VerificationStatus
    confidence: float
    explanation: str


def predict_linguistic_risk(
    text: str,
    settings: Settings | None = None,
) -> LinguisticPrediction:
    """
    Runs RoBERTa sequence classification for fake news risk.

    Args:
        text (str): News text to classify.
        settings (Settings | None): Optional runtime settings override.

    Returns:
        LinguisticPrediction: Model verdict, confidence, and explanation.
    """
    active_settings = settings or get_settings()
    model_name_or_path = active_settings.roberta_model_name_or_path

    if not model_name_or_path:
        raise RuntimeError(
            "ROBERTA_MODEL_NAME_OR_PATH must be configured before RoBERTa inference."
        )

    torch = _load_torch()
    tokenizer, model = _load_linguistic_assets(model_name_or_path)
    model.eval()

    encoded_inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    )

    with torch.no_grad():
        outputs = model(**encoded_inputs)

    probabilities = torch.softmax(outputs.logits, dim=-1)
    confidence_tensor, predicted_index_tensor = torch.max(probabilities, dim=-1)
    predicted_index = int(_tensor_item(predicted_index_tensor))
    confidence = round(float(_tensor_item(confidence_tensor)), 4)
    label = _label_from_model(model, predicted_index)
    status = _status_from_label(label)

    return LinguisticPrediction(
        status=status,
        confidence=confidence,
        explanation=_build_model_explanation(status, confidence),
    )


def _status_from_label(label: str) -> VerificationStatus:
    """
    Maps model labels to frontend verdicts.

    Args:
        label (str): Raw classifier label.

    Returns:
        VerificationStatus: Normalized frontend verdict.
    """
    normalized = label.strip().upper()

    fake_labels = {"FAKE", "FALSE", "MISINFORMATION", "UNRELIABLE", "LABEL_1"}
    real_labels = {"REAL", "TRUE", "RELIABLE", "CREDIBLE", "LABEL_0"}

    if normalized in fake_labels:
        return VerificationStatus.FAKE
    if normalized in real_labels:
        return VerificationStatus.REAL
    return VerificationStatus.UNCERTAIN


def _build_model_explanation(
    status: VerificationStatus,
    confidence: float,
) -> str:
    """
    Builds a concise explanation from the RoBERTa verdict.

    Args:
        status (VerificationStatus): Model verdict.
        confidence (float): Model confidence score.

    Returns:
        str: Human-readable explanation.
    """
    percentage = f"{confidence * 100:.1f}%"
    explanations = {
        VerificationStatus.REAL: (
            f"RoBERTa classified the text as likely credible with {percentage} "
            "confidence based on its learned linguistic patterns."
        ),
        VerificationStatus.FAKE: (
            f"RoBERTa classified the text as likely misinformation with "
            f"{percentage} confidence based on its learned linguistic patterns."
        ),
        VerificationStatus.UNCERTAIN: (
            f"RoBERTa produced an uncertain classification with {percentage} "
            "confidence. Source verification should carry more weight."
        ),
    }
    return explanations[status]


def _label_from_model(model: Any, predicted_index: int) -> str:
    """
    Reads a classifier label from model config.

    Args:
        model (Any): Hugging Face model.
        predicted_index (int): Predicted class index.

    Returns:
        str: Raw label.
    """
    id_to_label = getattr(model.config, "id2label", {})
    return str(id_to_label.get(predicted_index, f"LABEL_{predicted_index}"))


def _tensor_item(value: Any) -> Any:
    """
    Extracts a scalar from tensor-like values.

    Args:
        value (Any): Tensor-like value.

    Returns:
        Any: Scalar value.
    """
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (list, tuple)):
        return _tensor_item(value[0])
    return value


def _load_torch() -> Any:
    """
    Imports torch lazily so tests can mock model loading cheaply.

    Returns:
        Any: Imported torch module.
    """
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for RoBERTa inference.") from exc

    return torch


@lru_cache
def _load_linguistic_assets(model_name_or_path: str) -> tuple[Any, Any]:
    """
    Loads Hugging Face tokenizer and RoBERTa classifier lazily.

    Args:
        model_name_or_path (str): Local path or Hugging Face model ID.

    Returns:
        tuple[Any, Any]: Tokenizer and sequence classification model.
    """
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "transformers is required for RoBERTa inference."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_name_or_path)
    return tokenizer, model
