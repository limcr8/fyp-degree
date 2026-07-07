import datetime
import hashlib
import pytest
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient

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
    mock_rss_response = ([], [])
    mock_gemini_response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/..."),
        json={
            "candidates": [{
                "content": {"parts": [{"text": '{"verdict":"REAL","confidence":0.72,"explanation":"Test stub.","attributions":[]}'}]}
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


def _register_and_get_api_key() -> tuple[str, str]:
    username = f"apikey_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == 201
    return email, resp.json()["api_key"]


def _login_token(email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    return resp.json()["access_token"]


def test_analyze_accepts_valid_api_key_and_increments_quota() -> None:
    """A valid X-API-Key authenticates POST /analyze and bumps the caller's used_today."""
    email, api_key = _register_and_get_api_key()

    resp = client.post("/analyze", json={"text": "hello world"}, headers={"X-API-Key": api_key})
    assert resp.status_code == 200

    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {_login_token(email)}"})
    assert me.json()["api_quota"]["used_today"] == 1


def test_analyze_rejects_invalid_api_key() -> None:
    """An unrecognised X-API-Key yields 401."""
    resp = client.post("/analyze", json={"text": "hello"}, headers={"X-API-Key": "sk_live_bogus"})
    assert resp.status_code == 401


def test_analyze_enforces_daily_quota() -> None:
    """Exhausting the daily quota returns 429 on the next API-key request."""
    email, api_key = _register_and_get_api_key()

    from app.core.firebase_client import get_db
    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    record = user_ref.get().to_dict()
    record["api_quota"]["used_today"] = record["api_quota"]["daily_limit"]
    user_ref.set(record)

    resp = client.post("/analyze", json={"text": "hello"}, headers={"X-API-Key": api_key})
    assert resp.status_code == 429


def test_quota_auto_resets_after_reset_at() -> None:
    """A stale reset_at causes the quota to reset, allowing the request through."""
    email, api_key = _register_and_get_api_key()

    from app.core.firebase_client import get_db
    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    record = user_ref.get().to_dict()
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["api_quota"]["reset_at"] = past
    record["api_quota"]["used_today"] = 999
    user_ref.set(record)

    resp = client.post("/analyze", json={"text": "hello"}, headers={"X-API-Key": api_key})
    assert resp.status_code == 200