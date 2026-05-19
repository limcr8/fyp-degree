import logging

from fastapi import APIRouter, HTTPException

from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from models.analysis_service import analyze_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_news(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyzes a news text snippet and returns a frontend-compatible report.

    Args:
        request (AnalyzeRequest): The validated analysis request.

    Returns:
        AnalyzeResponse: The aggregated verification report.
    """
    try:
        return analyze_text(request)
    except Exception as exc:
        logger.exception("Analysis failed for submitted text.")
        raise HTTPException(status_code=500, detail="Analysis failed.") from exc
