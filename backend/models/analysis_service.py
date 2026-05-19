from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from app.schemas.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    BlockchainProof,
    ShapExplanation,
    VerificationStatus,
)
from models.verification import verify_topics


def analyze_text(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Builds the Stage 1 analysis response using deterministic local logic.

    Args:
        request (AnalyzeRequest): The validated analysis request.

    Returns:
        AnalyzeResponse: A complete frontend-compatible verification report.
    """
    status = _estimate_status(request.text)
    confidence = _estimate_confidence(request.text, status)
    report_id = str(uuid4())

    return AnalyzeResponse(
        id=report_id,
        text=request.text,
        status=status,
        confidence=confidence,
        explanation=_build_explanation(status),
        shapData=_build_initial_attributions(request.text),
        sources=verify_topics(request.text),
        blockchain=_build_local_proof(report_id, request.text),
    )


def _estimate_status(text: str) -> VerificationStatus:
    """
    Produces a lightweight Stage 1 verdict before real model integration.

    Args:
        text (str): The analyzed text.

    Returns:
        VerificationStatus: Estimated credibility verdict.
    """
    lowered = text.lower()
    high_risk_terms = ("guaranteed", "secret", "100x", "risk-free", "breaking")
    authority_terms = ("sec", "reuters", "bloomberg", "federal reserve", "regulator")

    risk_hits = sum(term in lowered for term in high_risk_terms)
    authority_hits = sum(term in lowered for term in authority_terms)

    if risk_hits >= 2 and authority_hits == 0:
        return VerificationStatus.FAKE
    if authority_hits > 0 and risk_hits == 0:
        return VerificationStatus.REAL
    return VerificationStatus.UNCERTAIN


def _estimate_confidence(text: str, status: VerificationStatus) -> float:
    """
    Produces a bounded Stage 1 confidence score.

    Args:
        text (str): The analyzed text.
        status (VerificationStatus): The estimated verdict.

    Returns:
        float: Confidence score between 0 and 1.
    """
    length_bonus = min(len(text) / 500, 0.2)
    base_scores = {
        VerificationStatus.REAL: 0.68,
        VerificationStatus.FAKE: 0.66,
        VerificationStatus.UNCERTAIN: 0.52,
    }
    return round(min(base_scores[status] + length_bonus, 0.9), 3)


def _build_explanation(status: VerificationStatus) -> str:
    """
    Builds a concise Stage 1 explanation.

    Args:
        status (VerificationStatus): The estimated verdict.

    Returns:
        str: Human-readable explanation.
    """
    explanations = {
        VerificationStatus.REAL: (
            "The text contains authority-oriented language and does not show "
            "strong sensational risk markers in the Stage 1 backend."
        ),
        VerificationStatus.FAKE: (
            "The text contains multiple high-risk linguistic markers commonly "
            "seen in sensational financial misinformation."
        ),
        VerificationStatus.UNCERTAIN: (
            "The Stage 1 backend found mixed or insufficient signals. Real "
            "RoBERTa, SHAP, and source verification will refine this verdict."
        ),
    }
    return explanations[status]


def _build_initial_attributions(text: str) -> list[ShapExplanation]:
    """
    Creates deterministic token attribution data for the React chart.

    Args:
        text (str): The analyzed text.

    Returns:
        list[ShapExplanation]: Initial token attribution values.
    """
    words = [word.strip(".,!?;:()[]{}\"'") for word in text.split()]
    unique_words = [word for index, word in enumerate(words) if word and word not in words[:index]]
    selected_words = unique_words[:5] or ["text"]

    return [
        ShapExplanation(word=word, weight=_token_weight(word))
        for word in selected_words
    ]


def _token_weight(word: str) -> float:
    """
    Calculates a stable pseudo-attribution for Stage 1 tests and UI rendering.

    Args:
        word (str): Token text.

    Returns:
        float: Attribution-like weight.
    """
    digest = sha256(word.lower().encode("utf-8")).hexdigest()
    raw_value = int(digest[:4], 16) / 65535
    return round((raw_value - 0.5) * 0.8, 3)


def _build_local_proof(report_id: str, text: str) -> BlockchainProof:
    """
    Builds deterministic local integrity metadata for Stage 1.

    Args:
        report_id (str): Generated report identifier.
        text (str): The analyzed text.

    Returns:
        BlockchainProof: Local proof metadata matching the production shape.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    digest = sha256(f"{report_id}:{text}".encode("utf-8")).hexdigest()

    return BlockchainProof(
        transactionHash=f"0x{digest[:64]}",
        blockNumber=0,
        timestamp=timestamp,
        ipfsHash=f"local-{digest[:46]}",
        network="Stage 1 Local Proof",
    )
