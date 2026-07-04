import json
import logging
import os
import time
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

logger = logging.getLogger(__name__)

from app.core.firebase_client import get_db
from app.core.config import get_settings

from app.schemas.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    ShapExplanation,
    VerificationStatus,
    ClassificationDetail,
    SourceMatch,
    ExplanationDetail,
    VerificationDetail,
    SourceComparison,
    FinalAssessment,
    BatchVerifyRequest,
    BatchVerifyResponse,
    SearchResultItem,
    SearchResponse,
    TrendingTopicItem,
    TrendingResponse,
)
from models.article_extraction import resolve_input_text, is_url
from models.explainer import generate_shap_explanations
from models.integrity_proof import create_integrity_proof
from models.linguistic import LinguisticPrediction, predict_linguistic_risk, predict_with_roberta
from models.verification import verify_topics, extract_entities, verify_topics_with_context


def analyze_text(request: AnalyzeRequest, access_token: str | None = None) -> AnalyzeResponse:
    """
    Builds the Stage 1 analysis response using deterministic local logic.

    Args:
        request (AnalyzeRequest): The validated analysis request.

    Returns:
        AnalyzeResponse: A complete frontend-compatible verification report.
    """
    start_time = time.perf_counter()

    analysis_text = resolve_input_text(request.text)
    language_val_early = (request.language or "en").lower().strip()
    fast_mode_val = getattr(request, "fast_mode", False)
    sources, search_context = verify_topics_with_context(analysis_text, language=language_val_early)

    # Self-heal: if the search returned articles but the deduplicated sources
    # list is empty (e.g. none matched the authoritative whitelist), build
    # SourceMatch entries directly from the retrieved articles so the frontend
    # always receives the sources it needs.
    if not sources and search_context:
        logger.info(
            "[ANALYZE] sources empty but %d articles found; building sources from articles.",
            len(search_context),
        )
        seen_names: set[str] = set()
        for item in search_context:
            name = item.get("source") or "Unknown"
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            sources.append(SourceMatch(
                name=name,
                confirmed=False,
                url=item.get("link"),
            ))
    logger.info(
        "[ANALYZE] verify_topics_with_context -> sources=%d search_context=%d",
        len(sources), len(search_context),
    )
    prediction = _predict_with_fallback(
        analysis_text,
        search_context=search_context,
        language=language_val_early,
        fast_mode=fast_mode_val,
    )
    status = prediction.status
    confidence = prediction.confidence
    report_id = str(uuid4())

    # Generate risk level based on classification confidence/status
    if status == VerificationStatus.FAKE:
        risk_level = "high" if confidence >= 0.75 else "medium"
    elif status == VerificationStatus.REAL:
        risk_level = "low"
    else:
        risk_level = "medium"

    classification_detail = ClassificationDetail(
        verdict=status.value,
        confidence=confidence,
        riskLevel=risk_level,
        explanation=prediction.explanation,
    )

    # Verification Score: improved scoring based on article coverage and source quality.
    #
    # New logic:
    #   - 0 articles found → 0% (no coverage of the claim at all)
    #   - 1-2 articles found → 40% base (some coverage)
    #   - 3-5 articles found → 55% base (good coverage)
    #   - 6+ articles found → 70% base (strong coverage)
    #   - Each confirmed authoritative source → +10% bonus (up to +30%)
    #   - Capped at 100%
    #
    # NOTE: This must be calculated BEFORE _calculate_signals() below.
    has_matching_articles = len(search_context) > 0
    confirmed_count = sum(1 for s in sources if s.confirmed)
    article_count = len(search_context)

    if not has_matching_articles:
        verification_score = 0.0
    else:
        if article_count <= 2:
            base_score = 0.40
        elif article_count <= 5:
            base_score = 0.55
        else:
            base_score = 0.70
        authority_bonus = min(confirmed_count * 0.10, 0.30)
        verification_score = round(min(base_score + authority_bonus, 1.0), 2)

    if prediction.attributions:
        raw_shap = [
            ShapExplanation(word=item["word"], weight=item["weight"])
            for item in prediction.attributions
        ]
        # Guard 1: if Gemini returned all near-zero weights (indecisive on neutral text),
        # discard them and fall through to the linguistic keyword fallback instead.
        max_abs_weight = max((abs(s.weight) for s in raw_shap), default=0.0)

        # Guard 2: detect uniform extreme weights (all identical -1.0 or 1.0).
        # When all weights are the same extreme value, the LLM failed to differentiate
        # tokens, so the attributions are meaningless. Fall back to linguistic logic.
        unique_weights = set(round(s.weight, 2) for s in raw_shap)
        is_uniform_extreme = (
            len(raw_shap) >= 3
            and len(unique_weights) <= 2
            and max_abs_weight >= 0.9
        )

        if is_uniform_extreme:
            logger.info(
                "Gemini attributions are uniform extreme weights (unique=%s); using linguistic fallback.",
                unique_weights,
            )
            shap_data = _generate_shap_with_fallback(analysis_text)
        elif max_abs_weight >= 0.05:
            shap_data = raw_shap
        else:
            logger.info(
                "Gemini attributions all near-zero (max=%.4f); using linguistic fallback.",
                max_abs_weight,
            )
            shap_data = _generate_shap_with_fallback(analysis_text)
    else:
        shap_data = _generate_shap_with_fallback(analysis_text)

    # Calculate top factors and summary
    top_factors = [item.word for item in shap_data if item.weight > 0][:3]
    if not top_factors:
        top_factors = [item.word for item in shap_data][:2]

    summary = f"Token attribution highlights key words: {', '.join(top_factors)}" if top_factors else "No significant keywords detected."

    # Calculate dynamic factual and bias signals based on analysis
    factual_signal, bias_signal = _calculate_signals(
        shap_data, status, confidence, verification_score, confirmed_count
    )

    explanation_detail = ExplanationDetail(
        shapData=shap_data,
        summary=summary,
        topFactors=top_factors,
        factualSignal=factual_signal,
        biasSignal=bias_signal,
    )

    explanation_verification = f"{int(verification_score * 100)}% of claims verified in authoritative sources"

    # Parse source_comparison from Gemini prediction if available
    parsed_source_comparison: list[SourceComparison] = []
    if prediction.source_comparison:
        for item in prediction.source_comparison:
            try:
                parsed_source_comparison.append(SourceComparison(
                    source_name=item["source_name"],
                    article_title=item["article_title"],
                    relationship=item["relationship"],
                    key_finding=item["key_finding"],
                ))
            except (KeyError, TypeError):
                logger.warning("Skipped malformed source_comparison entry: %s", item)

    verification_detail = VerificationDetail(
        sources=sources,
        verificationScore=verification_score,
        explanation=explanation_verification,
        matchingArticles=[
            {
                "title": item["title"],
                "link": item["link"],
                "source": item["source"],
                "snippet": item["snippet"]
            }
            for item in search_context
        ],
        summary=prediction.summary,
        sourceComparison=parsed_source_comparison,
    )

    # Final combined assessment
    # Classification risk (probability of FAKE)
    if status == VerificationStatus.FAKE:
        classification_risk = confidence
    elif status == VerificationStatus.REAL:
        classification_risk = 1.0 - confidence
    else:
        classification_risk = 0.5

    # Verification risk (lack of source backing)
    verification_risk = 1.0 - verification_score

    # Weighted Risk Score (0.6 classification + 0.4 verification)
    final_risk_score = round(0.6 * classification_risk + 0.4 * verification_risk, 2)

    # Determine final assessment label
    if final_risk_score >= 0.65:
        final_label = "fake"
        label_desc = "fake"
    elif final_risk_score <= 0.35:
        final_label = "real"
        label_desc = "real"
    else:
        final_label = "uncertain"
        label_desc = "uncertain"

    # Build final combined reasoning
    engine_name = "Gemini" if "Gemini" in prediction.explanation else "RoBERTa"
    total_sources = len(sources)
    if confirmed_count == 0:
        confirm_desc = "do not confirm"
    elif confirmed_count >= total_sources:
        confirm_desc = "strongly confirm"
    else:
        confirm_desc = "partially confirm"
    reasoning = f"{engine_name} says {confidence*100:.0f}% {status.value.lower()}, but sources {confirm_desc}. Overall: {label_desc}."

    final_assessment = FinalAssessment(
        score=final_risk_score,
        label=final_label,
        reasoning=reasoning,
    )

    # Sync classification.verdict with the authoritative final verdict so the
    # value stored in Firestore (articles + user history) matches what the UI
    # displays. finalAssessment.label is the combined authoritative verdict;
    # without this override Firestore keeps the raw RoBERTa/Gemini verdict
    # (e.g. "UNCERTAIN") while Portal/History show the final verdict (e.g.
    # "FAKE"), causing Firebase and the UI to disagree.
    if final_assessment and final_assessment.label:
        classification_detail = classification_detail.model_copy(
            update={"verdict": final_assessment.label.upper()}
        )

    # Stage 3 payload logic (serialize full response before blockchain anchoring)
    report_payload = {
        "id": report_id,
        "text": analysis_text,
        "classification": classification_detail.model_dump(by_alias=True),
        "explanation": explanation_detail.model_dump(by_alias=True),
        "verification": verification_detail.model_dump(by_alias=True),
        "finalAssessment": final_assessment.model_dump(),
    }

    blockchain_proof = create_integrity_proof(report_id, report_payload)
    processing_time = int((time.perf_counter() - start_time) * 1000)

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    platform_val = getattr(request, "platform", "website") or "website"
    language_val = getattr(request, "language", "en") or "en"

    # Automatically derive platform domain if request is a URL
    if is_url(request.text):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(request.text.strip())
            hostname = parsed.hostname or ""
            platform_val = hostname.removeprefix("www.").lower() or "website"
        except Exception:
            pass

    # Extract a clean headline from the article text for display purposes.
    article_title = _extract_headline(analysis_text, request.text)

    response = AnalyzeResponse(
        id=report_id,
        text=analysis_text,
        title=article_title,
        classification=classification_detail,
        explanation=explanation_detail,
        verification=verification_detail,
        finalAssessment=final_assessment,
        blockchain=blockchain_proof,
        processingTimeMs=processing_time,
        createdAt=created_at,
        platform=platform_val,
        language=language_val,
    )
    _save_report_locally(response)

    # NOTE: User history (users/{uid}/history) is written by the frontend via
    # saveVerificationResult(), keyed by the Firebase Auth UID. The previous
    # backend write to users/{email_hash}/history was removed because it used
    # sha256(email) as the document ID, which created a duplicate user row
    # distinct from the Firebase Auth UID and caused the users/ collection to
    # contain two documents per human user.

    return response


_USERS_DIR = os.path.join("data", "users")


def _is_mock_db() -> bool:
    """Returns True when the backend is using an in-memory MockFirestoreDb."""
    from app.core.firebase_client import MockFirestoreDb
    return isinstance(get_db(), MockFirestoreDb)


_ARTICLES_DIR = os.path.join("data", "articles")


def _save_report_locally(report: AnalyzeResponse) -> None:
    """
    Saves a report directly to the top-level articles collection in the DB.
    This leverages Firestore in production or LocalFileFirestoreDb in dev/offline mode.

    Args:
        report (AnalyzeResponse): The verified report.
    """
    try:
        db = get_db()
        payload = {
            "article_id": report.id,
            "text": report.text,
            "classification": report.classification.model_dump(by_alias=True) if report.classification else None,
            "explanation": report.explanation.model_dump(by_alias=True) if report.explanation else None,
            "verification": report.verification.model_dump(by_alias=True) if report.verification else None,
            "finalAssessment": report.final_assessment.model_dump() if report.final_assessment else None,
            "blockchain": report.blockchain.model_dump(by_alias=True) if report.blockchain else None,
            "processingTimeMs": report.processing_time_ms,
            "platform": report.platform,
            "language": report.language,
            "verified_at": report.created_at,
        }
        db.collection("articles").document(report.id).set(payload)
    except Exception:
        logger.exception("Failed to save report to database collection.")


def _load_all_from_user_history() -> list[dict]:
    """
    Aggregates all verification history items from every user record.

    The primary data source is the local data/users/ JSON file store.
    When real Firestore credentials are configured the Firestore users
    collection is merged in as well.

    Each returned dict has the same shape as HistoryItem:
      article_id, text, classification, verified_at,
      explanation, verification, finalAssessment, blockchain,
      processingTimeMs, platform, language.

    Returns:
        list[dict]: De-duplicated history items sorted newest-first.
    """
    all_items: list[dict] = []
    seen_ids: set[str] = set()

    # ── Local file store (primary) ──────────────────────────────────────────
    if os.path.isdir(_USERS_DIR):
        for filename in os.listdir(_USERS_DIR):
            if not filename.endswith(".json"):
                continue
            file_path = os.path.join(_USERS_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    user_record = json.load(fh)
                for item in user_record.get("history", []):
                    aid = item.get("article_id")
                    if aid and aid not in seen_ids:
                        all_items.append(item)
                        seen_ids.add(aid)
            except Exception:
                logger.warning("Skipping malformed user file: %s", filename)

    # ── Firestore (secondary, when real credentials are configured) ─────────
    if not _is_mock_db():
        try:
            db = get_db()
            for doc in db.collection("users").stream():
                try:
                    user_record = doc.to_dict()
                    for item in user_record.get("history", []):
                        aid = item.get("article_id")
                        if aid and aid not in seen_ids:
                            all_items.append(item)
                            seen_ids.add(aid)
                except Exception:
                    logger.exception("Failed to parse Firestore user history: %s", doc.id)
        except Exception:
            logger.exception("Failed to query Firestore users collection.")

    return all_items


def _history_item_to_analyze_response(item: dict) -> AnalyzeResponse | None:
    """
    Converts a raw user history dict into an AnalyzeResponse model.

    History items have a slightly different shape than AnalyzeResponse
    (e.g. 'verified_at' vs 'createdAt'), so this function bridges the gap.

    Args:
        item (dict): Raw history dict from a user record.

    Returns:
        AnalyzeResponse | None: The parsed model, or None if validation fails.
    """
    from app.schemas.analysis import (
        ClassificationDetail, ExplanationDetail, VerificationDetail,
        FinalAssessment, BlockchainProof,
    )
    try:
        classification = ClassificationDetail.model_validate(item["classification"])
        created_at = item.get("verified_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        explanation = None
        if item.get("explanation"):
            try:
                explanation = ExplanationDetail.model_validate(item["explanation"])
            except Exception:
                pass

        verification = None
        if item.get("verification"):
            try:
                verification = VerificationDetail.model_validate(item["verification"])
                if verification.sources:
                    verification.sources = [
                        s for s in verification.sources
                        if not (not s.confirmed and s.name in {"Reuters", "Bloomberg", "CoinDesk", "SEC"})
                    ]
            except Exception:
                pass

        final_assessment = None
        if item.get("finalAssessment"):
            try:
                final_assessment = FinalAssessment.model_validate(item["finalAssessment"])
            except Exception:
                pass

        blockchain = None
        if item.get("blockchain"):
            try:
                blockchain = BlockchainProof.model_validate(item["blockchain"])
            except Exception:
                pass

        return AnalyzeResponse(
            id=item["article_id"],
            text=item.get("text", ""),
            classification=classification,
            explanation=explanation,
            verification=verification,
            final_assessment=final_assessment,
            blockchain=blockchain,
            processing_time_ms=item.get("processingTimeMs"),
            created_at=created_at,
            platform=item.get("platform") or "twitter",
            language=item.get("language") or "en",
        )
    except Exception:
        logger.exception("Could not convert history item to AnalyzeResponse: %s", item.get("article_id"))
        return None


def get_report_by_id(report_id: str) -> AnalyzeResponse | None:
    """
    Retrieves a previously generated report by searching all user history and local files.

    Args:
        report_id (str): The report identifier (article_id).

    Returns:
        AnalyzeResponse | None: The report model, or None if not found.
    """
    for report in _load_all_reports():
        if report.id == report_id:
            return report
    return None



def analyze_batch(request: BatchVerifyRequest) -> BatchVerifyResponse:
    """
    Analyzes a batch of articles and returns the aggregated results.

    Args:
        request (BatchVerifyRequest): The bulk verification request.

    Returns:
        BatchVerifyResponse: The batch analysis results.
    """
    start_time = time.perf_counter()
    batch_id = f"batch_{uuid4()}"
    results = []

    for item in request.articles:
        single_req = AnalyzeRequest(text=item.text, language=item.language, platform="twitter")
        single_res = analyze_text(single_req)
        results.append(single_res)

    total_time = int((time.perf_counter() - start_time) * 1000)

    return BatchVerifyResponse(
        batch_id=batch_id,
        results=results,
        status="completed",
        total_time_ms=total_time,
    )


def _load_all_reports() -> list[AnalyzeResponse]:
    """
    Loads all verified reports by streaming from Firestore articles collection,
    with fallback to user histories and local files for backward compatibility/dev mode.

    Returns:
        list[AnalyzeResponse]: Deduplicated list of all report models.
    """
    reports: list[AnalyzeResponse] = []
    seen_ids: set[str] = set()

    # 1. Load from db collection "articles" (either Firestore or LocalFileFirestoreDb)
    try:
        db = get_db()
        for doc in db.collection("articles").stream():
            try:
                item = doc.to_dict()
                if "article_id" not in item:
                    item["article_id"] = doc.id
                report = _history_item_to_analyze_response(item)
                if report is not None and report.id not in seen_ids:
                    reports.append(report)
                    seen_ids.add(report.id)
            except Exception:
                logger.exception("Failed to parse article document: %s", doc.id)
    except Exception:
        logger.exception("Failed to stream articles from DB.")

    return reports



def search_reports(
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
    Queries and filters verified news reports.

    Reads from the local JSON file store (authoritative for local/dev
    environments) and additionally from Firestore when real credentials
    are configured.

    Args:
        q (str | None): Optional search keyword.
        language (str): Language filter ('en', 'zh', 'ms', 'all').
        status (str): Verdict status filter ('fake', 'real', 'uncertain', 'all').
        date_from (str | None): Optional ISO8601 start date.
        date_to (str | None): Optional ISO8601 end date.
        platform (str): Platform filter ('twitter', 'reddit', 'telegram', 'all').
        limit (int): Pagination result limit.
        offset (int): Pagination result offset.

    Returns:
        SearchResponse: The paginated filtered search results.
    """
    # Load from users' history (the authoritative data store).
    reports = _load_all_reports()

    filtered = []
    for report in reports:
        # Keyword filtering — use word-boundary matching to avoid false
        # positives (e.g. 'SEC' should NOT match 'security').
        if q:
            keyword = q.lower().strip()
            text_lower = report.text.lower()
            # Split into individual words; ALL must be present as whole words
            words = [w for w in keyword.split() if w]
            matched = True
            for w in words:
                try:
                    import re as _re
                    # Word-boundary match: the keyword must be a standalone word
                    if not _re.search(r'\b' + _re.escape(w) + r'\b', text_lower):
                        matched = False
                        break
                except Exception:
                    # Fallback to substring match if regex fails
                    if w not in text_lower:
                        matched = False
                        break
            if not matched:
                continue

        # Language filtering
        report_lang = (report.language or "en").lower().strip()
        filter_lang = language.lower().strip()
        if filter_lang != "all" and report_lang != filter_lang:
            continue

        # Platform filtering
        report_plat = (report.platform or "website").lower().strip()
        filter_plat = platform.lower().strip()
        if filter_plat != "all" and report_plat != filter_plat:
            continue

        # Status filtering
        filter_status = status.lower().strip()
        if filter_status != "all":
            verdict = report.classification.verdict.lower()
            final_label = (report.final_assessment.label or "").lower() if report.final_assessment else ""

            is_match = False
            if filter_status == "fake":
                is_match = (verdict == "fake" or "fake" in final_label)
            elif filter_status == "real":
                is_match = (verdict == "real" or "real" in final_label)
            elif filter_status == "uncertain":
                is_match = (verdict == "uncertain" or "uncertain" in final_label)

            if not is_match:
                continue

        # Date filtering — use verified_at (stored in created_at after conversion)
        timestamp_str = report.created_at
        if timestamp_str:
            ts = timestamp_str.strip()
            if date_from and ts < date_from.strip():
                continue
            if date_to and ts > date_to.strip():
                continue

        filtered.append(report)

    # Sort by verified_at (newest first)
    filtered.sort(key=lambda r: r.created_at or "", reverse=True)

    total_count = len(filtered)

    # Paginate
    paginated = filtered[offset : offset + limit]

    # Map to SearchResultItem
    results = [
        SearchResultItem(
            article_id=rep.id,
            text=rep.text,
            title=getattr(rep, "title", None) or _extract_headline(rep.text),
            classification=ClassificationDetail(
                verdict=_resolve_displayed_verdict(rep),
                confidence=_resolve_display_confidence(rep),
                risk_level=rep.classification.risk_level if rep.classification else "medium",
                explanation=rep.classification.explanation if rep.classification else "",
            ) if rep.classification else rep.classification,
            created_at=rep.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            platform=rep.platform or "twitter",
            language=rep.language or "en",
        )
        for rep in paginated
    ]

    # Calculate current page
    page = (offset // limit) + 1 if limit > 0 else 1

    return SearchResponse(
        results=results,
        total_count=total_count,
        page=page,
        per_page=limit,
    )


def _extract_headline(article_text: str, original_input: str = "") -> str:
    """
    Extracts a clean headline/title from scraped article text.

    Args:
        article_text (str): The full scraped article text.
        original_input (str): The original user input (may be a URL).

    Returns:
        str: A clean headline suitable for display.
    """
    if not article_text:
        return "Untitled Article"
    lines = [ln.strip() for ln in article_text.split("\n") if ln.strip()]
    # The first non-empty line is usually the headline/title
    headline = lines[0] if lines else article_text.strip()
    # Truncate to a reasonable title length
    if len(headline) > 100:
        headline = headline[:97] + "..."
    return headline


def _resolve_displayed_verdict(report) -> str:
    """
    Resolves the single normalized verdict to display for a report.

    Prefers final_assessment.label (the authoritative final verdict) and
    falls back to classification.verdict. Normalizes to uppercase with spaces.
    This ensures trending, search, and UI badges all agree on the verdict.

    Args:
        report: An AnalyzeResponse / report object.

    Returns:
        str: Normalized verdict (e.g. 'LIKELY REAL', 'LIKELY FAKE', 'UNCERTAIN').
    """
    if report.final_assessment and report.final_assessment.label:
        return report.final_assessment.label.upper().replace("_", " ")
    if report.classification and report.classification.verdict:
        return report.classification.verdict.upper().replace("_", " ")
    return "UNCERTAIN"


def _resolve_display_confidence(report) -> float:
    """
    Resolves a user-facing confidence percentage for a report.

    final_assessment.score is a RISK score (0=safe, 1=risky), not a
    confidence score. To show meaningful confidence we invert it for
    non-fake verdicts so that a low-risk REAL article displays high
    confidence (e.g. risk 0.06 -> 94% confident it is real).

    Args:
        report: An AnalyzeResponse / report object.

    Returns:
        float: Verdict-aware confidence in the range 0.0 to 1.0.
    """
    if report.final_assessment and report.final_assessment.score is not None:
        verdict = _resolve_displayed_verdict(report)
        risk = float(report.final_assessment.score)
        if "FAKE" in verdict:
            return round(min(max(risk, 0.0), 1.0), 4)
        return round(min(max(1.0 - risk, 0.0), 1.0), 4)
    if report.classification and report.classification.confidence is not None:
        return float(report.classification.confidence)
    return 0.5


def get_trending_topics(
    language: str = "all",
    limit: int = 10,
) -> TrendingResponse:
    """
    Computes and ranks trending news topics from verified articles.

    Args:
        language (str): Language filter (en, zh, ms, all).
        limit (int): Max number of trending items to return.

    Returns:
        TrendingResponse: List of trending topics and matched articles.
    """
    # Load from users' history (authoritative data store).
    reports = _load_all_reports()


    if language.lower() != "all":
        target_lang = language.lower().strip()
        reports = [r for r in reports if (r.language or "en").lower().strip() == target_lang]

    # Only use curated crypto keywords for trending topics.
    # NER entities are too noisy (random names) and produce unrelated results
    # when clicked. Sticking to well-known crypto terms keeps trending relevant.
    CRYPTO_TOPICS = [
        "Bitcoin", "Ethereum", "SEC", "Binance", "FTX",
        "Solana", "Ripple", "Tether", "Coinbase", "Crypto",
    ]
    topic_map = {}

    for report in reports:
        detected_topics = set()
        lowered_text = report.text.lower()

        # Only curated crypto keywords
        for crypto in CRYPTO_TOPICS:
            if crypto.lower() in lowered_text:
                detected_topics.add(crypto)

        search_item = SearchResultItem(
            article_id=report.id,
            text=report.text,
            title=getattr(report, "title", None) or _extract_headline(report.text),
            classification=report.classification,
            created_at=report.created_at or report.blockchain.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            platform=report.platform or "twitter",
            language=report.language or "en",
        )

        # Use a consistent verdict resolution that matches what the UI displays.
        # The card badge shows classification.verdict, but final_assessment.label
        # is the authoritative final verdict. Resolve to a single normalized value
        # so trending fake counts always match the visible verdict badges.
        displayed_verdict = _resolve_displayed_verdict(report)
        is_fake = "FAKE" in displayed_verdict

        for topic in detected_topics:
            topic_key = topic.lower().strip()
            if topic_key not in topic_map:
                topic_map[topic_key] = {
                    "topic": topic,
                    "articles": [],
                    "mentions": 0,
                    "fake_count": 0,
                }

            if not any(item.article_id == search_item.article_id for item in topic_map[topic_key]["articles"]):
                topic_map[topic_key]["articles"].append(search_item)
                topic_map[topic_key]["mentions"] += 1
                if is_fake:
                    topic_map[topic_key]["fake_count"] += 1

    trending_items = []
    for key, data in topic_map.items():
        trending_items.append(
            TrendingTopicItem(
                topic=data["topic"],
                mentions=data["mentions"],
                fake_count=data["fake_count"],
                articles=data["articles"],
            )
        )

    trending_items.sort(key=lambda x: (x.mentions, x.fake_count), reverse=True)

    # Return real data only (no fake placeholders). An empty list hides the
    # trending bar in the frontend until real articles create real trends.
    return TrendingResponse(trending=trending_items[:limit])


def _predict_with_fallback(
    text: str,
    search_context: list[dict[str, str]] | None = None,
    language: str = "en",
    fast_mode: bool = False,
) -> LinguisticPrediction:
    """
    Uses RoBERTa when configured, otherwise falls back to local heuristics.
    Implements fast_mode and conditional LLM escalation (0.4 < confidence < 0.7).

    Args:
        text (str): The analyzed text.
        search_context (list[dict[str, str]] | None): Search context for Gemini RAG.
        language (str): BCP-47 language code of the input text.
        fast_mode (bool): If True, bypass LLM escalation entirely.

    Returns:
        LinguisticPrediction: Linguistic verdict and explanation.
    """
    active_settings = get_settings()

    # 1. Run local fast classifier first (RoBERTa sequence classifier if configured, else heuristics)
    try:
        fast_pred = predict_with_roberta(text, active_settings)
    except Exception as exc:
        logger.info("Local RoBERTa model not configured or failed: %s. Using heuristics.", str(exc))
        status = _estimate_status(text)
        confidence = _estimate_confidence(text, status)
        fast_pred = LinguisticPrediction(
            status=status,
            confidence=confidence,
            explanation=f"Linguistic Heuristic (Fallback): {_build_fallback_explanation(status)}",
        )

    # 2. Check if we need to escalate to LLM (OpenAI/Gemini)
    # LLM escalation is active ONLY IF fast_mode is False, LLM keys are configured,
    # and fast prediction confidence is within the uncertain range (0.4 to 0.7)
    has_llm = bool(active_settings.openai_api_key or active_settings.gemini_api_key)
    if not fast_mode and has_llm and 0.4 < fast_pred.confidence < 0.7:
        try:
            logger.info("Confidence %.4f is in uncertain range (0.4 - 0.7); escalating to LLM.", fast_pred.confidence)
            # predict_linguistic_risk will automatically try OpenAI first, then Gemini
            return predict_linguistic_risk(text, settings=active_settings, search_context=search_context, language=language)
        except Exception:
            logger.exception("LLM escalation failed. Falling back to fast prediction.")
            return fast_pred

    logger.info("Using fast prediction (fast_mode=%s, confidence=%.4f).", fast_mode, fast_pred.confidence)
    return fast_pred


def _generate_shap_with_fallback(text: str) -> list[ShapExplanation]:
    """
    Uses SHAP when configured, otherwise falls back to deterministic tokens.

    Args:
        text (str): The analyzed text.

    Returns:
        list[ShapExplanation]: Frontend-compatible attribution data.
    """
    try:
        return generate_shap_explanations(text)
    except RuntimeError:
        return _build_initial_attributions(text)


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


def _build_fallback_explanation(status: VerificationStatus) -> str:
    """
    Builds a concise Stage 1 explanation.

    Args:
        status (VerificationStatus): The estimated verdict.

    Returns:
        str: Human-readable explanation.
    """
    explanations = {
        VerificationStatus.REAL: (
            "RoBERTa is not configured yet. The fallback linguistic scanner "
            "found authority-oriented language and limited risk markers."
        ),
        VerificationStatus.FAKE: (
            "RoBERTa is not configured yet. The fallback linguistic scanner "
            "found multiple high-risk sensational markers."
        ),
        VerificationStatus.UNCERTAIN: (
            "RoBERTa is not configured yet. The fallback linguistic scanner "
            "found mixed or insufficient signals."
        ),
    }
    return explanations[status]


def _build_initial_attributions(text: str) -> list[ShapExplanation]:
    """
    Creates linguistically-informed token attribution data for the React chart.

    Uses a keyword sensitivity dictionary to assign weights based on known
    fake-news indicators (positive weights = FAKE signals) and credibility
    anchors (negative weights = REAL signals). Handles both Latin and Chinese
    character tokenisation.

    Args:
        text (str): The analyzed text.

    Returns:
        list[ShapExplanation]: Token attribution values with semantic meaning.
    """
    import re
    # For Chinese text (no spaces between characters), extract CJK runs as tokens;
    # for Latin text split on whitespace as usual.
    cjk_runs = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]+', text)
    if cjk_runs:
        # Treat each CJK run (e.g. a noun compound) as a single word token
        words = [run for run in cjk_runs if len(run) >= 2]
    else:
        words = [word.strip(".,!?;:()[]{}\"'") for word in text.split()]
    unique_words = list(dict.fromkeys(w for w in words if w))
    selected_words = unique_words[:8]

    return [
        ShapExplanation(word=word, weight=_token_weight(word))
        for word in selected_words
    ]


# Keyword sensitivity dictionary for linguistically-informed fallback attributions.
# Positive weights indicate FAKE signals; negative weights indicate REAL/credible signals.
_FAKE_SIGNAL_KEYWORDS: dict[str, float] = {
    # Sensational / clickbait
    "BREAKING": 0.72, "SHOCKING": 0.68, "EXPOSED": 0.65, "SECRET": 0.63,
    "EXCLUSIVE": 0.55, "BOMBSHELL": 0.70, "UNBELIEVABLE": 0.66, "ALERT": 0.58,
    "URGENT": 0.54, "LEAKED": 0.61, "BANNED": 0.50, "CENSORED": 0.52,
    # Pump-and-dump / crypto scam signals
    "100x": 0.85, "1000x": 0.88, "guaranteed": 0.80, "airdrop": 0.62,
    "free": 0.48, "giveaway": 0.71, "presale": 0.64, "moon": 0.55,
    "lambo": 0.70, "pump": 0.65, "whale": 0.45, "whale-backed": 0.68,
    "rug": 0.75, "scam": 0.72, "phishing": 0.80, "hack": 0.55,
    # Misinformation linguistic patterns
    "they\'re": 0.35, "they\'ll": 0.30, "never": 0.35, "always": 0.32,
    "literally": 0.28, "obviously": 0.30, "everyone": 0.25, "nobody": 0.28,
    # Authority-backing / credibility anchors (negative = supports REAL)
    "Reuters": -0.72, "Bloomberg": -0.70, "SEC": -0.65, "CoinDesk": -0.55,
    "official": -0.50, "confirmed": -0.58, "statement": -0.45, "report": -0.40,
    "announced": -0.48, "regulation": -0.55, "compliance": -0.52, "audit": -0.60,
    "approved": -0.55, "filed": -0.50, "court": -0.48, "government": -0.52,
    "research": -0.45, "study": -0.40, "data": -0.38, "analysis": -0.42,
}


def _calculate_signals(
    shap_data: list[ShapExplanation],
    status: VerificationStatus,
    confidence: float,
    verification_score: float,
    confirmed_count: int,
) -> tuple[str, str]:
    """
    Calculates dynamic factual and bias signals based on analysis results.

    Args:
        shap_data: Token attributions.
        status: Classification verdict.
        confidence: Model confidence score.
        verification_score: Source verification score.
        confirmed_count: Number of confirmed authoritative sources.

    Returns:
        tuple[str, str]: (factual_signal, bias_signal) - each being "Low", "Medium", or "High".
    """
    # Factual Signal: based on verification score and confirmed sources
    if verification_score >= 0.6 and confirmed_count >= 2:
        factual_signal = "High"
    elif verification_score >= 0.4 or confirmed_count >= 1:
        factual_signal = "Medium"
    else:
        factual_signal = "Low"

    # Bias Signal: based on SHAP weights and classification
    if not shap_data:
        bias_signal = "Medium"
    else:
        # Count tokens with positive weights (fake indicators)
        fake_indicators = sum(1 for item in shap_data if item.weight > 0.3)
        total_tokens = len(shap_data)
        fake_ratio = fake_indicators / total_tokens if total_tokens > 0 else 0

        # Also consider the classification
        if status == VerificationStatus.FAKE and confidence >= 0.7:
            bias_signal = "Critical"
        elif fake_ratio >= 0.5 or (status == VerificationStatus.FAKE and confidence >= 0.5):
            bias_signal = "High"
        elif fake_ratio >= 0.3 or status == VerificationStatus.UNCERTAIN:
            bias_signal = "Medium"
        else:
            bias_signal = "Low"

    return factual_signal, bias_signal


def _token_weight(word: str) -> float:
    """
    Calculates a linguistically-informed attribution weight for a token.

    Checks against a keyword sensitivity dictionary first, then falls
    back to a stable SHA-256-based pseudo-weight as a baseline.

    Args:
        word (str): Token text.

    Returns:
        float: Attribution-like weight between -0.9 and +0.9.
    """
    # Check exact case match first (for proper nouns like Reuters)
    if word in _FAKE_SIGNAL_KEYWORDS:
        return _FAKE_SIGNAL_KEYWORDS[word]
    # Check case-insensitive match
    lower = word.lower()
    for key, val in _FAKE_SIGNAL_KEYWORDS.items():
        if key.lower() == lower:
            return val
    # Stable SHA-256-based fallback for unknown words (centered near 0)
    digest = sha256(lower.encode("utf-8")).hexdigest()
    # Use 6 hex chars (24 bits) for better distribution; scale to ±0.45 so bars are visible
    raw_value = int(digest[:6], 16) / 16777215
    return round((raw_value - 0.5) * 0.9, 3)  # Bounded to ±0.45 for unknown words
