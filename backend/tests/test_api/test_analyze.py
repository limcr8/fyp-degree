from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_empty_settings() -> None:
    import httpx
    mock_settings = Settings(
        roberta_model_name_or_path="",
        google_api_key="",
        google_cse_id="",
        gemini_api_key="",
        openai_api_key="",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )
    # Stub Google News RSS to return empty results (no live HTTP during tests)
    mock_rss_response = ([], [])
    # Stub Gemini POST to prevent live API calls from hitting quota limits
    mock_gemini_response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/..."),
        json={
            "candidates": [{
                "content": {"parts": [{"text": '{"verdict":"REAL","confidence":0.72,"explanation":"Test stub.","attributions":[{"word":"Bitcoin","weight":-0.45},{"word":"regulatory","weight":-0.38}]}'}]}
            }]
        },
    )
    with patch("models.verification.get_settings", return_value=mock_settings), \
         patch("models.integrity_proof.get_settings", return_value=mock_settings), \
         patch("models.linguistic.get_settings", return_value=mock_settings), \
         patch("models.explainer.get_settings", return_value=mock_settings), \
         patch("models.analysis_service.get_settings", return_value=mock_settings), \
         patch("models.verification.search_google_news_rss", return_value=mock_rss_response), \
         patch("models.linguistic.httpx.post", return_value=mock_gemini_response):
        yield


def test_health_endpoint_returns_ok() -> None:
    """
    Verifies that the backend exposes a lightweight health check.
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_detailed_health_endpoint_returns_metrics() -> None:
    """
    Verifies that GET /api/v1/health returns detailed health check payload.
    """
    # 1. Test when model is configured and exists
    mock_settings_loaded = Settings(
        roberta_model_name_or_path="./checkpoints/roberta-fake-news",
        google_api_key="",
        google_cse_id="",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )
    with patch("app.main.get_settings", return_value=mock_settings_loaded):
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"
        assert isinstance(data["uptime_seconds"], int)
        assert data["services"] == {
            "api": "running",
            "database": "running",
            "bert_model": "loaded",
            "cache": "running",
        }

    # 2. Test when model is not configured / not loaded
    mock_settings_unloaded = Settings(
        roberta_model_name_or_path="",
        google_api_key="",
        google_cse_id="",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )
    with patch("app.main.get_settings", return_value=mock_settings_unloaded):
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["bert_model"] == "not_loaded"


def test_detailed_status_endpoint_returns_metrics() -> None:
    """
    Verifies that GET /api/v1/status returns detailed system metrics.
    """
    # 1. Test when model and external search API are configured
    mock_settings_operational = Settings(
        roberta_model_name_or_path="./checkpoints/roberta-fake-news",
        google_api_key="mock_key",
        google_cse_id="mock_cse",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )
    with patch("app.main.get_settings", return_value=mock_settings_operational):
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "operational"
        assert "last_checked" in data

        components = data["components"]
        assert components["api_server"]["status"] == "operational"
        assert isinstance(components["api_server"]["response_time_ms"], int)

        assert components["database"] == {
            "status": "operational",
            "connection_pool": "healthy",
        }

        assert components["ml_models"]["status"] == "operational"
        assert components["ml_models"]["bert_loaded"] is True
        assert isinstance(components["ml_models"]["average_inference_time_ms"], int)

        assert components["external_apis"] == {
            "google_search": "operational",
            "twitter": "operational",
            "redis": "operational",
        }

    # 2. Test fallback when model and search are unconfigured
    mock_settings_degraded = Settings(
        roberta_model_name_or_path="",
        google_api_key="",
        google_cse_id="",
        ipfs_api_key="",
        ipfs_api_url="",
        web3_provider_url="",
        web3_private_key="",
        web3_chain_id=0,
    )
    with patch("app.main.get_settings", return_value=mock_settings_degraded):
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "degraded"

        components = data["components"]
        assert components["ml_models"]["status"] == "degraded"
        assert components["ml_models"]["bert_loaded"] is False
        assert components["external_apis"]["google_search"] == "unconfigured"




def test_analyze_endpoint_returns_frontend_compatible_shape() -> None:
    """
    Verifies that /analyze returns the existing React VerificationResult shape.
    """
    payload = {
        "text": (
            "Bitcoin ETF approval sends BTC higher after confirmation from "
            "multiple financial regulators."
        )
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == payload["text"]
    assert "classification" in body
    assert body["classification"]["verdict"] in {"REAL", "FAKE", "UNCERTAIN"}
    assert 0 <= body["classification"]["confidence"] <= 1
    assert "explanation" in body
    assert isinstance(body["explanation"]["shapData"], list)
    assert "verification" in body
    assert isinstance(body["verification"]["sources"], list)
    assert "finalAssessment" in body
    assert 0 <= body["finalAssessment"]["score"] <= 1
    assert "blockchain" in body
    assert isinstance(body["blockchain"], dict)
    assert set(body["blockchain"]) == {
        "transactionHash",
        "blockNumber",
        "timestamp",
        "ipfsHash",
        "network",
    }


def test_analyze_endpoint_rejects_empty_text() -> None:
    """
    Verifies that empty text fails request validation.
    """
    response = client.post("/analyze", json={"text": "   "})

    assert response.status_code == 400


def test_get_article_endpoint_returns_saved_report() -> None:
    """
    Verifies that GET /api/v1/article/{id} retrieves the saved report successfully.
    """
    payload = {"text": "Bitcoin rises after positive market sentiment update."}
    post_response = client.post("/analyze", json=payload)
    assert post_response.status_code == 200
    report_id = post_response.json()["id"]

    get_response = client.get(f"/api/v1/article/{report_id}")
    assert get_response.status_code == 200
    
    body = get_response.json()
    assert body["id"] == report_id
    assert body["text"] == payload["text"]
    assert "classification" in body
    assert "verification" in body


def test_get_article_endpoint_returns_404_on_missing() -> None:
    """
    Verifies that GET /api/v1/article/{id} returns 404 for missing IDs.
    """
    response = client.get("/api/v1/article/nonexistent-id-123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Article not found."


def test_verify_batch_endpoint_success() -> None:
    """
    Verifies that POST /api/v1/verify-batch successfully processes a list of articles.
    """
    payload = {
        "articles": [
            {"text": "Breaking: major regulatory update regarding BTC ETF.", "language": "en"},
            {"text": "Ethereum gas fees hit all-time lows in recent gas optimize upgrade.", "language": "en"}
        ]
    }
    response = client.post("/api/v1/verify-batch", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "batch_id" in body
    assert body["status"] == "completed"
    assert "total_time_ms" in body
    assert isinstance(body["results"], list)
    assert len(body["results"]) == 2

    # Check that each article response is valid
    for idx, result in enumerate(body["results"]):
        assert "id" in result
        assert result["text"] == payload["articles"][idx]["text"]
        assert "classification" in result
        assert "verification" in result
        assert "finalAssessment" in result
        assert "blockchain" in result


def test_verify_batch_endpoint_validation() -> None:
    """
    Verifies that POST /api/v1/verify-batch fails validation on invalid article texts.
    """
    payload = {
        "articles": [
            {"text": "  ", "language": "en"}
        ]
    }
    response = client.post("/api/v1/verify-batch", json=payload)
    assert response.status_code == 400


def test_search_endpoint_returns_filtered_results() -> None:
    """
    Verifies that GET /api/v1/search queries and filters stored reports.
    """
    p1 = {"text": "Federal reserve updates interest rate policies for cryptocurrency.", "language": "en", "platform": "twitter"}
    p2 = {"text": "Guaranteed 100x return secret pump scheme detected on Reddit.", "language": "zh", "platform": "reddit"}

    r1 = client.post("/analyze", json=p1)
    r2 = client.post("/analyze", json=p2)
    assert r1.status_code == 200
    assert r2.status_code == 200

    # Search by keyword
    search_q = client.get("/api/v1/search?q=reserve")
    assert search_q.status_code == 200
    res_q = search_q.json()
    assert res_q["total_count"] >= 1
    assert any("Federal reserve" in item["text"] for item in res_q["results"])

    # Search by language
    search_lang = client.get("/api/v1/search?language=zh")
    assert search_lang.status_code == 200
    res_lang = search_lang.json()
    assert any(item["language"] == "zh" for item in res_lang["results"])

    # Search by platform
    search_plat = client.get("/api/v1/search?platform=reddit")
    assert search_plat.status_code == 200
    res_plat = search_plat.json()
    assert any(item["platform"] == "reddit" for item in res_plat["results"])

    # Search by status
    search_status = client.get("/api/v1/search?status=fake")
    assert search_status.status_code == 200
    res_status = search_status.json()
    assert any("pump" in item["text"] for item in res_status["results"])


def test_trending_endpoint_success() -> None:
    """
    Verifies that GET /api/v1/trending retrieves grouped trending topics.
    """
    p1 = {"text": "Bitcoin faces severe regulatory considerations globally.", "language": "en", "platform": "twitter"}
    p2 = {"text": "Ethereum fees are lowering according to some validators.", "language": "en", "platform": "twitter"}

    r1 = client.post("/analyze", json=p1)
    r2 = client.post("/analyze", json=p2)
    assert r1.status_code == 200
    assert r2.status_code == 200

    res = client.get("/api/v1/trending?language=en&limit=15")
    assert res.status_code == 200
    body = res.json()
    assert "trending" in body
    assert isinstance(body["trending"], list)
    assert len(body["trending"]) >= 2

    topics = [item["topic"].lower() for item in body["trending"]]
    assert "bitcoin" in topics
    assert "ethereum" in topics

    for item in body["trending"]:
        if item["topic"].lower() == "bitcoin":
            assert item["mentions"] >= 1
            assert isinstance(item["articles"], list)
            assert item["fake_count"] >= 0


def test_export_pdf_endpoint_success_and_failures() -> None:
    """
    Verifies that GET /api/v1/export/pdf/{article_id} validates Bearer token,
    handles missing articles, and outputs a valid binary PDF stream.
    """
    # 1. Register and login to get access token
    from uuid import uuid4
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    reg_resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    assert reg_resp.status_code == 201

    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    # 2. Analyze a text to generate a report ID
    analyze_resp = client.post("/analyze", json={
        "text": "Solana networks process transactions very fast."
    })
    assert analyze_resp.status_code == 200
    article_id = analyze_resp.json()["id"]

    # 3. Request PDF without token -> 400 Bad Request
    res_no_auth = client.get(f"/api/v1/export/pdf/{article_id}")
    assert res_no_auth.status_code == 400

    # 4. Request PDF with bad header format -> 401 Unauthorized
    res_bad_format = client.get(f"/api/v1/export/pdf/{article_id}", headers={"Authorization": "bad_token"})
    assert res_bad_format.status_code == 401

    # 5. Request PDF with invalid token -> 401 Unauthorized
    res_invalid_token = client.get(f"/api/v1/export/pdf/{article_id}", headers={"Authorization": "Bearer invalid_token"})
    assert res_invalid_token.status_code == 401

    # 6. Request PDF with non-existent article_id -> 404 Not Found
    res_404 = client.get("/api/v1/export/pdf/nonexistent_id", headers={"Authorization": f"Bearer {access_token}"})
    assert res_404.status_code == 404

    # 7. Request PDF successfully -> 200 OK
    res_success = client.get(f"/api/v1/export/pdf/{article_id}", headers={"Authorization": f"Bearer {access_token}"})
    assert res_success.status_code == 200
    assert res_success.headers["content-type"] == "application/pdf"
    assert "attachment" in res_success.headers["content-disposition"]
    assert f"verification_report_{article_id}.pdf" in res_success.headers["content-disposition"]

    # Verify PDF magic bytes
    pdf_content = res_success.content
    assert pdf_content.startswith(b"%PDF-")


def test_export_csv_endpoint_success_and_failures() -> None:
    """
    Verifies that GET /api/v1/export/csv validates Bearer token,
    and returns search results formatted in RFC 4180 CSV schema.
    """
    # 1. Register and login to get access token
    from uuid import uuid4
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    reg_resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    assert reg_resp.status_code == 201

    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    # 2. Analyze a text to generate a report
    text_snippet = "Bitcoin regulation is updated by the SEC."
    analyze_resp = client.post("/analyze", json={"text": text_snippet})
    assert analyze_resp.status_code == 200
    article_id = analyze_resp.json()["id"]

    # 3. Request CSV without token -> 400 Bad Request (missing header converts to validation error 400)
    res_no_auth = client.get("/api/v1/export/csv")
    assert res_no_auth.status_code == 400
    err_body = res_no_auth.json()
    assert "error" in err_body
    assert "message" in err_body
    assert "code" in err_body

    # 4. Request CSV with invalid token -> 401 Unauthorized
    res_invalid_token = client.get("/api/v1/export/csv", headers={"Authorization": "Bearer invalid_token"})
    assert res_invalid_token.status_code == 401
    err_body = res_invalid_token.json()
    assert err_body == {
        "error": "unauthorized",
        "message": "Invalid access token: Invalid token format.",
        "code": "AUTH_REQUIRED",
        "detail": "Invalid access token: Invalid token format."
    }

    # 5. Request CSV successfully -> 200 OK
    res_success = client.get(
        f"/api/v1/export/csv?q=Bitcoin&limit=10",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert res_success.status_code == 200
    assert res_success.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in res_success.headers["content-disposition"]
    assert "verification_search_results.csv" in res_success.headers["content-disposition"]

    # Parse and verify CSV payload content
    import csv
    import io
    csv_file = io.StringIO(res_success.text)
    reader = csv.reader(csv_file)
    rows = list(reader)

    # Verify header row
    assert rows[0] == ["article_id", "text", "classification", "confidence", "date"]

    # Verify data row exists
    assert len(rows) >= 2
    matched_row = None
    for row in rows[1:]:
        if row[0] == article_id:
            matched_row = row
            break

    assert matched_row is not None
    assert matched_row[1] == text_snippet
    assert matched_row[2] in {"REAL", "FAKE", "UNCERTAIN"}
    assert float(matched_row[3]) >= 0.0


def test_standardized_error_responses() -> None:
    """
    Verifies that standard routes return the requested error response payloads.
    """
    # 1. 404 Not Found error shape
    res_404 = client.get("/api/v1/article/missing_article_id_999")
    assert res_404.status_code == 404
    body_404 = res_404.json()
    assert body_404 == {
        "error": "not_found",
        "message": "Article not found.",
        "code": "RESOURCE_NOT_FOUND",
        "detail": "Article not found."
    }

    # 2. 400 Bad Request error shape (validation converts to 400 with Text field is required)
    res_400 = client.post("/analyze", json={"text": ""})
    assert res_400.status_code == 400
    body_400 = res_400.json()
    assert body_400 == {
        "error": "invalid_input",
        "message": "Text field is required",
        "code": "INVALID_INPUT",
        "detail": "Text field is required"
    }


def test_url_input_auto_detects_platform_domain() -> None:
    """
    Verifies that passing a URL as input automatically sets the platform field
    to the domain of the website.
    """
    url = "https://reuters.com/business/finance/sec-etf-approval"
    with patch("models.analysis_service.resolve_input_text", return_value="This is some news body extracted from the article."):
        response = client.post("/analyze", json={"text": url})
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "reuters.com"


def test_analyze_endpoint_supports_fast_mode() -> None:
    """
    Verifies that /analyze endpoint accepts fast_mode in the request body
    and passes it down correctly to the service.
    """
    from app.schemas.analysis import (
        AnalyzeResponse,
        ClassificationDetail,
        ExplanationDetail,
        VerificationDetail,
        FinalAssessment,
        BlockchainProof,
    )
    payload = {
        "text": "Bitcoin reaches new heights on exchange volume surge.",
        "fast_mode": True
    }
    
    mock_response = AnalyzeResponse(
        id="test-id",
        text=payload["text"],
        classification=ClassificationDetail(
            verdict="REAL",
            confidence=0.99,
            riskLevel="low",
            explanation="Test explanation"
        ),
        explanation=ExplanationDetail(
            shapData=[],
            summary="Test summary",
            topFactors=[]
        ),
        verification=VerificationDetail(
            sources=[],
            verificationScore=1.0,
            explanation="Test explanation",
            matchingArticles=[],
            summary="Test summary",
            sourceComparison=[]
        ),
        finalAssessment=FinalAssessment(
            score=0.9,
            label="likely_real",
            reasoning="Test reasoning"
        ),
        blockchain=BlockchainProof(
            transactionHash="0xabc",
            blockNumber=100,
            timestamp="2026-06-18T00:00:00Z",
            ipfsHash="QmTestHash",
            network="Local Integrity Proof"
        ),
        processingTimeMs=10,
        createdAt="2026-06-18T00:00:00Z",
        platform="website",
        language="en"
    )
    
    with patch("app.api.analyze.analyze_text") as mock_analyze:
        mock_analyze.return_value = mock_response
        response = client.post("/analyze", json=payload)
        assert response.status_code == 200
        
        # Verify it was called with AnalyzeRequest containing fast_mode=True
        mock_analyze.assert_called_once()
        called_arg = mock_analyze.call_args[0][0]
        assert called_arg.text == payload["text"]
        assert called_arg.fast_mode is True






