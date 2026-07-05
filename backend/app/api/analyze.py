import logging

from fastapi import APIRouter, HTTPException, Header, Response, Depends

from app.core.security import require_api_key

from app.schemas.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    BatchVerifyRequest,
    BatchVerifyResponse,
    SearchResponse,
    TrendingResponse,
)
from models.analysis_service import analyze_text, get_report_by_id, analyze_batch, search_reports, get_trending_topics
from models.auth_service import get_user_profile
from models.pdf_service import generate_verification_pdf

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_news(
    request: AnalyzeRequest,
    authorization: str | None = Header(None, description="Optional Bearer token"),
    api_access_token: str | None = Depends(require_api_key),
) -> AnalyzeResponse:
    """
    Analyzes a news text snippet and returns a frontend-compatible report.

    Accepts either a per-user X-API-Key header (subject to daily quota) or an
    optional Bearer session token for authenticated web clients.

    Args:
        request (AnalyzeRequest): The validated analysis request.
        authorization (str | None): Optional Bearer token header.
        api_access_token (str | None): Access token resolved from X-API-Key.

    Returns:
        AnalyzeResponse: The aggregated verification report.
    """
    try:
        access_token = api_access_token
        if not access_token and authorization and authorization.startswith("Bearer "):
            access_token = authorization.split(" ")[1]
        response = analyze_text(request, access_token=access_token)
        logger.info(
            "[ANALYZE DIAG] sources=%d matchingArticles=%d verificationScore=%s sourceComparison=%d",
            len(response.verification.sources) if response.verification else -1,
            len(response.verification.matching_articles) if response.verification else -1,
            response.verification.verification_score if response.verification else "None",
            len(response.verification.source_comparison) if response.verification else -1,
        )
        return response
    except Exception as exc:
        logger.exception("Analysis failed for submitted text.")
        raise HTTPException(status_code=500, detail="Analysis failed.") from exc


@router.get("/api/v1/article/{article_id}", response_model=AnalyzeResponse)
def get_article(article_id: str) -> AnalyzeResponse:
    """
    Retrieves a previously analyzed news report by its ID.

    Args:
        article_id (str): The report identifier.

    Returns:
        AnalyzeResponse: The verification report.
    """
    report = get_report_by_id(article_id)
    if not report:
        raise HTTPException(status_code=404, detail="Article not found.")
    return report


@router.post("/api/v1/verify-batch", response_model=BatchVerifyResponse)
def verify_news_batch(request: BatchVerifyRequest) -> BatchVerifyResponse:
    """
    Verifies a batch of news articles and returns the aggregated results.

    Args:
        request (BatchVerifyRequest): The bulk verification request.

    Returns:
        BatchVerifyResponse: The batch analysis results.
    """
    try:
        return analyze_batch(request)
    except Exception as exc:
        logger.exception("Batch analysis failed.")
        raise HTTPException(status_code=500, detail="Batch analysis failed.") from exc


@router.get("/api/v1/search", response_model=SearchResponse)
def search_articles(
    q: str | None = None,
    language: str = "all",
    status: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
    platform: str = "all",
    limit: int = 20,
    offset: int = 0,
) -> SearchResponse:
    """
    Search and filter previously verified articles across all users.

    Query Parameters:
        - q: Search keyword.
        - language: Filter by language (en, zh, ms, all).
        - status: Filter by verdict (fake, real, uncertain, all).
        - date_from: Optional start date (ISO8601 string).
        - date_to: Optional end date (ISO8601 string).
        - platform: Filter by platform (twitter, reddit, telegram, all).
        - limit: Results limit per page (1-100, default 20).
        - offset: Result pagination offset.
    """
    try:
        validated_limit = max(1, min(100, limit))
        return search_reports(
            q=q,
            language=language,
            status=status,
            date_from=date_from,
            date_to=date_to,
            platform=platform,
            limit=validated_limit,
            offset=offset,
        )
    except Exception as exc:
        logger.exception("Search query failed.")
        raise HTTPException(status_code=500, detail="Search query failed.") from exc


@router.get("/api/v1/trending", response_model=TrendingResponse)
def get_trending(
    language: str = "all",
    limit: int = 10,
) -> TrendingResponse:
    """
    Retrieves trending fake news topics and their associated verified articles.

    Query Parameters:
        - language: Filter by language (en, zh, ms, all).
        - limit: Max number of topics to return.
    """
    try:
        validated_limit = max(1, min(100, limit))
        return get_trending_topics(language=language, limit=validated_limit)
    except Exception as exc:
        logger.exception("Trending query failed.")
        raise HTTPException(status_code=500, detail="Trending query failed.") from exc


@router.get("/api/v1/export/pdf/{article_id}")
def export_verification_pdf(
    article_id: str,
    authorization: str = Header(..., description="Bearer token"),
) -> Response:
    """
    Exports a previously generated news verification report as a PDF certificate.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    report = get_report_by_id(article_id)
    if not report:
        raise HTTPException(status_code=404, detail="Article not found.")

    try:
        pdf_data = generate_verification_pdf(report)
        headers = {
            "Content-Disposition": f"attachment; filename=verification_report_{article_id}.pdf"
        }
        return Response(content=pdf_data, media_type="application/pdf", headers=headers)
    except Exception as exc:
        logger.exception("Failed to generate PDF report.")
        raise HTTPException(status_code=500, detail="Failed to generate PDF report.") from exc


@router.get("/api/v1/export/csv")
def export_search_csv(
    q: str | None = None,
    status: str = "all",
    language: str = "all",
    platform: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 1000,
    authorization: str = Header(..., description="Bearer token"),
) -> Response:
    """
    Exports verification search results as a CSV file.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        results_data = search_reports(
            q=q,
            language=language,
            status=status,
            date_from=date_from,
            date_to=date_to,
            platform=platform,
            limit=limit,
            offset=0
        )
        
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        # Write header
        writer.writerow(["article_id", "text", "classification", "confidence", "date"])
        
        for item in results_data.results:
            writer.writerow([
                item.article_id,
                item.text,
                item.classification.verdict,
                item.classification.confidence,
                item.created_at
            ])
            
        csv_data = output.getvalue()
        output.close()
        
        headers = {
            "Content-Disposition": "attachment; filename=verification_search_results.csv"
        }
        return Response(content=csv_data, media_type="text/csv", headers=headers)
    except Exception as exc:
        logger.exception("Failed to export search results to CSV.")
        raise HTTPException(status_code=500, detail="Failed to export CSV.") from exc





