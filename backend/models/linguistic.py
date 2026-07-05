import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas.analysis import VerificationStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinguisticPrediction:
    """
    RoBERTa linguistic risk prediction.

    Attributes:
        status (VerificationStatus): Credibility verdict.
        confidence (float): Model confidence score from 0 to 1.
        explanation (str): Human-readable model explanation.
        attributions (list[dict] | None): SHAP-style token weights.
        summary (str | None): Gemini-generated news summary.
        source_comparison (list[dict] | None): Comparative source analysis matrix.
    """

    status: VerificationStatus
    confidence: float
    explanation: str
    attributions: list[dict[str, Any]] | None = None
    summary: str | None = None
    source_comparison: list[dict[str, Any]] | None = None


def predict_linguistic_risk(
    text: str,
    settings: Settings | None = None,
    search_context: list[dict[str, str]] | None = None,
    language: str = "en",
) -> LinguisticPrediction:
    """Runs sequence classification for fake news risk using OpenAI API, Gemini API, or RoBERTa.

    Args:
        text (str): News text to classify.
        settings (Settings | None): Optional runtime settings override.
        search_context (list[dict[str, str]] | None): Optional retrieved search context.
        language (str): BCP-47 language code of the text (e.g. 'en', 'zh', 'ms').

    Returns:
        LinguisticPrediction: Model verdict, confidence, and explanation.
    """
    active_settings = settings or get_settings()

    # 1. Try OpenAI API first if configured
    if active_settings.openai_api_key:
        try:
            return predict_with_openai(text, active_settings, search_context=search_context, language=language)
        except Exception:
            logger.exception("OpenAI API verification failed. Falling back to next provider.")

    # 2. Try Gemini API next if configured
    if active_settings.gemini_api_key:
        try:
            return predict_with_gemini(text, active_settings, search_context=search_context, language=language)
        except Exception:
            logger.exception("Gemini API verification failed. Falling back to RoBERTa.")

    # 3. Fall back to local RoBERTa model
    return predict_with_roberta(text, active_settings)


def predict_with_roberta(
    text: str,
    settings: Settings | None = None,
) -> LinguisticPrediction:
    """Classifies news text credibility using local RoBERTa sequence classifier.

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
        explanation=f"RoBERTa Model: {_build_model_explanation(status, confidence)}",
    )


def predict_with_openai(
    text: str,
    settings: Settings,
    search_context: list[dict[str, str]] | None = None,
    language: str = "en",
) -> LinguisticPrediction:
    """Classifies news text credibility using OpenAI Chat Completions API zero-shot reasoning.

    Args:
        text (str): News text to classify.
        settings (Settings): Runtime settings containing openai_api_key.
        search_context (list[dict[str, str]] | None): Authoritative search context matching topics in text.
        language (str): BCP-47 language code of the input text.

    Returns:
        LinguisticPrediction: Verdict, confidence, and explanation.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    context_str = _build_search_context_str(search_context)
    prompt = _build_factcheck_prompt(text, context_str, language=language)

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()

    result_json = response.json()
    choices = result_json.get("choices", [])
    if not choices:
        raise ValueError("OpenAI API returned no choices.")

    content_text = choices[0].get("message", {}).get("content", "")
    if not content_text:
        raise ValueError("OpenAI API candidate content was empty.")

    return _parse_llm_json_response(content_text, "OpenAI LLM")


def predict_with_gemini(
    text: str,
    settings: Settings,
    search_context: list[dict[str, str]] | None = None,
    language: str = "en",
) -> LinguisticPrediction:
    """Classifies news text credibility using Google Gemini API zero-shot reasoning or RAG.

    Args:
        text (str): News text to classify.
        settings (Settings): Runtime settings containing gemini_api_key.
        search_context (list[dict[str, str]] | None): Authoritative search context matching topics in text.
        language (str): BCP-47 language code of the input text.

    Returns:
        LinguisticPrediction: Verdict, confidence, and explanation.
    """
    model = "gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.gemini_api_key}"

    context_str = _build_search_context_str(search_context)
    prompt = _build_factcheck_prompt(text, context_str, language=language)

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    response = httpx.post(url, json=payload, timeout=30)
    response.raise_for_status()

    result_json = response.json()
    candidates = result_json.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini API returned no candidates.")

    content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    if not content_text:
        raise ValueError("Gemini API candidate content was empty.")

    return _parse_llm_json_response(content_text, "Gemini LLM")


def _build_search_context_str(search_context: list[dict[str, str]] | None) -> str:
    """Formats retrieved search context into a readable string block for LLM prompts.

    Args:
        search_context (list[dict[str, str]] | None): Search context snippets and titles.

    Returns:
        str: Formatted text block.
    """
    if search_context:
        context_str = "\nRetrieved Authoritative Search Context:\n"
        for i, item in enumerate(search_context, 1):
            context_str += (
                f"Source {i}: {item.get('source', 'Unknown')}\n"
                f"  Title: {item.get('title', '')}\n"
                f"  Link: {item.get('link', '')}\n"
                f"  Snippet: {item.get('snippet', '')}\n\n"
            )
        return context_str
    return "\nNo authoritative search results found matching this claim.\n"


_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "zh": "Chinese (Mandarin/中文)",
    "ms": "Malay (Bahasa Melayu)",
    "ar": "Arabic",
    "id": "Indonesian (Bahasa Indonesia)",
}


def _build_factcheck_prompt(text: str, context_str: str, language: str = "en") -> str:
    """Builds the complete fact-checking prompt string.

    Args:
        text (str): Snippet content to check.
        context_str (str): Formatted search context string.
        language (str): BCP-47 language code of the input text.

    Returns:
        str: Prompt string.
    """
    lang_name = _LANGUAGE_NAMES.get(language, language.upper())
    lang_note = (
        f"IMPORTANT: The news text below is written in {lang_name}. "
        "You can read and understand this language. "
        "You MUST still respond with a JSON object where the summary, explanation, and key_finding fields are written in ENGLISH regardless of the input language. "
        "However, for the 'attributions' field, each 'word' MUST be the exact word/phrase extracted from the original input text in its original language (do NOT translate or transliterate it to English).\n\n"
    ) if language != "en" else ""

    return (
        "You are an expert investigative fact-checker and senior analyst specializing in cryptocurrency, financial, and general news.\n"
        "Your task is to perform a multi-stage structured audit of the following news snippet.\n\n"
        f"{lang_note}"
        f"News Text to Analyze: \"{text}\"\n"
        f"{context_str}"
        "Instructions:\n"
        "1. SUMMARY: Write a 2-3 sentence neutral summary IN ENGLISH of what the news snippet claims, as if briefing an editor.\n"
        "2. FACTUAL AUDIT: Compare each claim in the snippet against the retrieved search context. Identify supporting or refuting evidence for each retrieved source.\n"
        "3. SOURCE COMPARISON: For each retrieved source, determine if it SUPPORTS, REFUTES, or is UNRELATED to the news snippet claim. Extract one key finding quote or insight IN ENGLISH.\n"
        "4. VERDICT: Assign one of: 'REAL' (strongly verified), 'FAKE' (refuted / scam / misinformation), 'UNCERTAIN' (insufficient evidence).\n"
        "5. CONFIDENCE: A score 0.0-1.0 representing your certainty.\n"
        "6. EXPLANATION: A single sentence IN ENGLISH citing specific sources from context.\n"
        "7. ATTRIBUTIONS: Top 5 most influential individual words or short terms (2 words maximum, do NOT extract full sentences, clauses, or long phrases) from the text. Use the exact words as they appear in the original input text (in its original language). Do NOT translate them to English. Negative weight = supports REAL. Positive weight = supports FAKE.\n\n"
        "You MUST respond ONLY with a valid JSON object. If no search context is available, still fill all fields with your best analysis.\n"
        "{\n"
        "  \"verdict\": \"REAL\" | \"FAKE\" | \"UNCERTAIN\",\n"
        "  \"confidence\": 0.0-1.0,\n"
        "  \"summary\": \"2-3 sentence neutral briefing of the news claim (in English)\",\n"
        "  \"explanation\": \"one-sentence verdict explanation citing sources (in English)\",\n"
        "  \"source_comparison\": [\n"
        "    {\n"
        "      \"source_name\": \"Reuters\",\n"
        "      \"article_title\": \"Article headline\",\n"
        "      \"relationship\": \"SUPPORTS\" | \"REFUTES\" | \"UNRELATED\",\n"
        "      \"key_finding\": \"one-sentence key quote or insight from this source (in English)\"\n"
        "    }\n"
        "  ],\n"
        "  \"attributions\": [\n"
        "    {\n"
        "      \"word\": \"exact individual word or very short 2-word term from the original input text (in its original language)\",\n"
        "      \"weight\": -1.0 to 1.0\n"
        "    }\n"
        "  ]\n"
        "}"
    )


def _parse_llm_json_response(content_text: str, provider_name: str) -> LinguisticPrediction:
    """Parses and sanitizes the JSON response returned from the LLM prompt.

    Args:
        content_text (str): Raw response text.
        provider_name (str): Label prefix for the explanation field (e.g. "Gemini LLM").

    Returns:
        LinguisticPrediction: structured prediction output.
    """
    data = json.loads(content_text.strip())

    verdict_str = str(data.get("verdict", "UNCERTAIN")).strip().upper()
    confidence = float(data.get("confidence", 0.5))
    summary = str(data.get("summary", ""))
    explanation = str(data.get("explanation", ""))
    attributions = data.get("attributions", [])
    raw_source_comparison = data.get("source_comparison", [])

    parsed_attributions = []
    if isinstance(attributions, list):
        for attr in attributions:
            if isinstance(attr, dict) and "word" in attr and "weight" in attr:
                try:
                    raw_weight = float(attr["weight"])
                    # Normalize extreme weights: clamp to [-0.85, 0.85] and add variance
                    # This prevents all weights being exactly -1.0 or 1.0
                    if abs(raw_weight) >= 0.95:
                        # Add small variance based on word hash for differentiation
                        word_hash = abs(hash(attr["word"])) % 100 / 100.0
                        normalized = 0.7 + (word_hash * 0.15)
                        if raw_weight < 0:
                            normalized = -normalized
                    else:
                        normalized = max(-0.85, min(0.85, raw_weight))
                    
                    parsed_attributions.append({
                        "word": str(attr["word"]),
                        "weight": round(normalized, 3)
                    })
                except (ValueError, TypeError):
                    pass

    parsed_source_comparison = []
    valid_relationships = {"SUPPORTS", "REFUTES", "UNRELATED"}
    if isinstance(raw_source_comparison, list):
        for item in raw_source_comparison:
            if isinstance(item, dict):
                relationship = str(item.get("relationship", "UNRELATED")).strip().upper()
                if relationship not in valid_relationships:
                    relationship = "UNRELATED"
                parsed_source_comparison.append({
                    "source_name": str(item.get("source_name", "Unknown")),
                    "article_title": str(item.get("article_title", "")),
                    "relationship": relationship,
                    "key_finding": str(item.get("key_finding", "")),
                })

    if verdict_str == "REAL":
        status = VerificationStatus.REAL
    elif verdict_str == "FAKE":
        status = VerificationStatus.FAKE
    else:
        status = VerificationStatus.UNCERTAIN

    return LinguisticPrediction(
        status=status,
        confidence=round(confidence, 4),
        explanation=f"{provider_name}: {explanation}",
        attributions=parsed_attributions,
        summary=summary or None,
        source_comparison=parsed_source_comparison or None,
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
