import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _elevate_to_admin(email: str) -> None:
    """Promotes a registered user to the admin role inside the mock Firestore."""
    from app.core.firebase_client import get_db

    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    record = user_ref.get().to_dict()
    record["role"] = "admin"
    user_ref.set(record)


def _seed_article(verified_at: str) -> None:
    """Inserts a minimal article record with a timestamp into the mock Firestore."""
    from app.core.firebase_client import get_db

    db = get_db()
    doc_id = uuid4().hex
    db.collection("articles").document(doc_id).set(
        {"article_id": doc_id, "verified_at": verified_at}
    )


def test_admin_trend_enforces_role_and_admin_token() -> None:
    """
    Verifies that GET /api/v1/admin/trend rejects non-admins and invalid
    X-Admin-Token headers before returning trend data.
    """
    username = f"trend_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": password},
        ).status_code
        == 201
    )

    user_token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]

    forbidden = client.get(
        "/api/v1/admin/trend",
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert forbidden.status_code == 403
    assert "Admin privileges required" in forbidden.json()["detail"]

    _elevate_to_admin(email)
    admin_token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]

    bad_header = client.get(
        "/api/v1/admin/trend",
        headers={"Authorization": f"Bearer {admin_token}", "X-Admin-Token": "wrong"},
    )
    assert bad_header.status_code == 403
    assert "Invalid admin token" in bad_header.json()["detail"]


def test_admin_trend_returns_daily_buckets_counting_articles() -> None:
    """
    Verifies that GET /api/v1/admin/trend returns one bucket per day and that
    articles verified today are reflected in the current day's count.
    """
    import datetime

    username = f"trend_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": password},
        ).status_code
        == 201
    )
    _elevate_to_admin(email)
    admin_token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    today_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    _seed_article(today_iso)
    _seed_article(today_iso)

    response = client.get(
        "/api/v1/admin/trend?days=7",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["days"] == 7
    assert len(data["trend"]) == 7
    assert {point["date"] for point in data["trend"]}.issuperset(
        {point["date"] for point in data["trend"]}
    )

    today_key = now_utc.date().isoformat()
    today_point = next(p for p in data["trend"] if p["date"] == today_key)
    assert today_point["count"] == 2