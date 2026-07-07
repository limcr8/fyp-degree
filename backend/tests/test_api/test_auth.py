import os
import json
import pytest
import hashlib
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_empty_settings() -> None:
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
    with patch("models.verification.get_settings", return_value=mock_settings), \
         patch("models.integrity_proof.get_settings", return_value=mock_settings), \
         patch("models.linguistic.get_settings", return_value=mock_settings), \
         patch("models.explainer.get_settings", return_value=mock_settings):
        yield


def test_auth_registration_success() -> None:
    """
    Verifies that a new user can successfully register.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    payload = {
        "username": username,
        "email": email,
        "password": "SecurePassword123!"
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["username"] == username
    assert body["email"] == email
    assert "user_id" in body
    assert body["role"] == "user"
    assert "api_key" in body
    assert body["api_key"].startswith("sk_live_")
    assert body["message"] == "Account created successfully"


def test_auth_registration_duplicate_email() -> None:
    """
    Verifies that registering with an existing email fails.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    payload = {
        "username": username,
        "email": email,
        "password": "SecurePassword123!"
    }

    # First registration
    response1 = client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == 201

    # Second registration with same email, different username
    payload2 = {
        "username": f"diff_{username}",
        "email": email,
        "password": "SecurePassword123!"
    }
    response2 = client.post("/api/v1/auth/register", json=payload2)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "Email address already registered."


def test_auth_registration_duplicate_username() -> None:
    """
    Verifies that registering with an existing username fails.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    payload = {
        "username": username,
        "email": email,
        "password": "SecurePassword123!"
    }

    # First registration
    response1 = client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == 201

    # Second registration with same username, different email
    payload2 = {
        "username": username,
        "email": f"diff_{email}",
        "password": "SecurePassword123!"
    }
    response2 = client.post("/api/v1/auth/register", json=payload2)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "Username already taken."


def test_auth_registration_validation() -> None:
    """
    Verifies that password and inputs validation constraints are enforced.
    """
    # Short password
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "123"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400


def test_auth_login_success() -> None:
    """
    Verifies that a registered user can successfully authenticate.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register first
    register_payload = {
        "username": username,
        "email": email,
        "password": password
    }
    register_response = client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 201
    user_id = register_response.json()["user_id"]

    # 2. Login
    login_payload = {
        "email": email,
        "password": password
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200

    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["user"]["user_id"] == user_id
    assert body["user"]["username"] == username
    assert body["user"]["role"] == "user"


def test_auth_login_invalid_password() -> None:
    """
    Verifies that logging in with an incorrect password fails.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register first
    register_payload = {
        "username": username,
        "email": email,
        "password": password
    }
    assert client.post("/api/v1/auth/register", json=register_payload).status_code == 201

    # 2. Login with bad password
    login_payload = {
        "email": email,
        "password": "WrongPassword123!"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid email or password."


def test_auth_login_nonexistent_email() -> None:
    """
    Verifies that logging in with a non-existent email fails.
    """
    login_payload = {
        "email": "doesnotexist@example.com",
        "password": "SecurePassword123!"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid email or password."


def test_auth_login_validation() -> None:
    """
    Verifies that login inputs validation rules are enforced.
    """
    # Short password
    login_payload = {
        "email": "test@example.com",
        "password": "123"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 400


def test_auth_refresh_success() -> None:
    """
    Verifies that a valid refresh token yields a new access token.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register user
    register_payload = {
        "username": username,
        "email": email,
        "password": password
    }
    assert client.post("/api/v1/auth/register", json=register_payload).status_code == 201

    # 2. Login to get refresh token
    login_payload = {
        "email": email,
        "password": password
    }
    login_response = client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    # 3. Refresh access token
    headers = {"Authorization": f"Bearer {refresh_token}"}
    response = client.post("/api/v1/auth/refresh", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["expires_in"] == 3600


def test_auth_refresh_invalid_token() -> None:
    """
    Verifies that refreshing with an invalid refresh token fails.
    """
    headers = {"Authorization": "Bearer invalid_refresh_token"}
    response = client.post("/api/v1/auth/refresh", headers=headers)
    assert response.status_code == 401
    assert "Invalid refresh token" in response.json()["detail"] or "format" in response.json()["detail"]


def test_auth_refresh_bad_header() -> None:
    """
    Verifies that refreshing with a malformed authorization header fails.
    """
    headers = {"Authorization": "invalid_header_format"}
    response = client.post("/api/v1/auth/refresh", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authorization format."


def test_auth_logout_success() -> None:
    """
    Verifies that a valid session token can successfully log out.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register user
    register_payload = {
        "username": username,
        "email": email,
        "password": password
    }
    assert client.post("/api/v1/auth/register", json=register_payload).status_code == 201

    # 2. Login to get access token
    login_payload = {
        "email": email,
        "password": password
    }
    login_response = client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # 3. Logout
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


def test_auth_logout_invalid_token() -> None:
    """
    Verifies that logging out with an invalid access token fails.
    """
    headers = {"Authorization": "Bearer invalid_access_token"}
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 401
    assert "Invalid access token" in response.json()["detail"] or "format" in response.json()["detail"]


def test_auth_logout_bad_header() -> None:
    """
    Verifies that logging out with a malformed authorization header fails.
    """
    headers = {"Authorization": "invalid_header_format"}
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authorization format."


def test_auth_get_me_success() -> None:
    """
    Verifies that a valid session token yields the user's detailed profile.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register user
    register_payload = {
        "username": username,
        "email": email,
        "password": password
    }
    assert client.post("/api/v1/auth/register", json=register_payload).status_code == 201

    # 2. Login to get access token
    login_payload = {
        "email": email,
        "password": password
    }
    login_response = client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # 3. Get profile details
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    
    body = response.json()
    assert body["username"] == username
    assert body["email"] == email
    assert "user_id" in body
    assert body["role"] == "user"
    assert "api_key" in body
    assert "created_at" in body
    assert "last_login" in body
    assert body["api_quota"]["daily_limit"] == 100
    assert body["api_quota"]["used_today"] == 0
    assert "reset_at" in body["api_quota"]


def test_auth_get_me_invalid_token() -> None:
    """
    Verifies that retrieving profile details with an invalid token fails.
    """
    headers = {"Authorization": "Bearer invalid_access_token"}
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401
    assert "Invalid access token" in response.json()["detail"] or "format" in response.json()["detail"]


def test_auth_get_me_bad_header() -> None:
    """
    Verifies that retrieving profile details with a malformed header fails.
    """
    headers = {"Authorization": "invalid_header_format"}
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authorization format."


def test_auth_update_profile_success() -> None:
    """
    Verifies that a user can successfully update their profile.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register user
    register_payload = {
        "username": username,
        "email": email,
        "password": password
    }
    assert client.post("/api/v1/auth/register", json=register_payload).status_code == 201

    # 2. Login to get access token
    login_payload = {
        "email": email,
        "password": password
    }
    login_response = client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # 3. Update profile
    new_username = f"new_{username}"
    new_email = f"new_{email}"
    update_payload = {
        "username": new_username,
        "email": new_email,
        "preferences": {
            "language": "zh",
            "notifications": False
        }
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.put("/api/v1/users/me", json=update_payload, headers=headers)
    assert response.status_code == 200
    
    body = response.json()
    assert body["message"] == "Profile updated successfully"
    assert body["user"]["username"] == new_username
    assert body["user"]["email"] == new_email
    assert body["user"]["preferences"]["language"] == "zh"
    assert body["user"]["preferences"]["notifications"] is False

    # 4. Verify that logging in with the new email works
    new_login_payload = {
        "email": new_email,
        "password": password
    }
    new_login_response = client.post("/api/v1/auth/login", json=new_login_payload)
    assert new_login_response.status_code == 200


def test_auth_update_profile_duplicates() -> None:
    """
    Verifies duplicate username and email constraints are enforced on update.
    """
    u1 = f"u1_{uuid4().hex[:8]}"
    u2 = f"u2_{uuid4().hex[:8]}"
    e1 = f"{u1}@example.com"
    e2 = f"{u2}@example.com"
    password = "SecurePassword123!"

    # 1. Register both users
    assert client.post("/api/v1/auth/register", json={"username": u1, "email": e1, "password": password}).status_code == 201
    assert client.post("/api/v1/auth/register", json={"username": u2, "email": e2, "password": password}).status_code == 201

    # 2. Login as u1
    login_response = client.post("/api/v1/auth/login", json={"email": e1, "password": password})
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Try updating u1's username to u2's username (should fail)
    response_dup_username = client.put("/api/v1/users/me", json={
        "username": u2,
        "email": e1,
        "preferences": {"language": "en", "notifications": True}
    }, headers=headers)
    assert response_dup_username.status_code == 400
    assert "Username already taken." in response_dup_username.json()["detail"]

    # 4. Try updating u1's email to u2's email (should fail)
    response_dup_email = client.put("/api/v1/users/me", json={
        "username": u1,
        "email": e2,
        "preferences": {"language": "en", "notifications": True}
    }, headers=headers)
    assert response_dup_email.status_code == 400
    assert "Email address already registered." in response_dup_email.json()["detail"]


def test_auth_change_password_success() -> None:
    """
    Verifies that a user can successfully change their password.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    new_password = "NewSecurePassword456!"

    # 1. Register and login
    assert client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Change password
    payload = {
        "old_password": password,
        "new_password": new_password
    }
    response = client.post("/api/v1/users/change-password", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successfully"

    # 3. Verify logging in with old password fails
    login_old_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_old_resp.status_code == 400

    # 4. Verify logging in with new password succeeds
    login_new_resp = client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
    assert login_new_resp.status_code == 200


def test_auth_change_password_invalid() -> None:
    """
    Verifies validation and authorization rules for password change.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register and login
    assert client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Incorrect old password (should return 400)
    response_wrong = client.post("/api/v1/users/change-password", json={
        "old_password": "WrongPassword123!",
        "new_password": "NewSecurePassword456!"
    }, headers=headers)
    assert response_wrong.status_code == 400
    assert "Invalid old password" in response_wrong.json()["detail"]

    # 3. Missing fields (should return 400)
    response_missing = client.post("/api/v1/users/change-password", json={
        "new_password": "NewSecurePassword456!"
    }, headers=headers)
    assert response_missing.status_code == 400

    # 4. Short password (should return 400)
    response_short = client.post("/api/v1/users/change-password", json={
        "old_password": password,
        "new_password": "123"
    }, headers=headers)
    assert response_short.status_code == 400


def test_auth_get_history_success() -> None:
    """
    Verifies that user can perform analyses and retrieve their history paginated.
    """
    username = f"user_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register and login
    assert client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Perform some analyses using the bearer token
    text_1 = "This is a real statement regarding crypto markets."
    text_2 = "This is a fake statement regarding crypto regulations."

    resp_1 = client.post("/analyze", json={"text": text_1}, headers=headers)
    assert resp_1.status_code == 200
    resp_2 = client.post("/analyze", json={"text": text_2}, headers=headers)
    assert resp_2.status_code == 200

    # 3. Retrieve history (should contain 2 items)
    history_resp = client.get("/api/v1/users/history?limit=10&offset=0", headers=headers)
    assert history_resp.status_code == 200
    data = history_resp.json()
    assert "history" in data
    assert data["total_count"] == 2
    assert len(data["history"]) == 2
    assert data["history"][0]["text"] == text_2
    assert data["history"][1]["text"] == text_1

    # 4. Verify pagination offset and limit
    history_paginated = client.get("/api/v1/users/history?limit=1&offset=1", headers=headers)
    assert history_paginated.status_code == 200
    pdata = history_paginated.json()
    assert pdata["total_count"] == 2
    assert len(pdata["history"]) == 1
    assert pdata["history"][0]["text"] == text_1


def test_admin_dashboard_endpoint_success_and_failures() -> None:
    """
    Verifies that GET /api/v1/admin/dashboard enforces role and custom header validations,
    and returns valid summary metrics.
    """
    # 1. Register a user
    username = f"admin_t_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    assert client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201

    # Get user token (role is "user" initially)
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    user_token = login_resp.json()["access_token"]

    # Request dashboard as regular user -> 403 Forbidden
    response_forbidden = client.get(
        "/api/v1/admin/dashboard",
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_forbidden.status_code == 403
    assert "Admin privileges required" in response_forbidden.json()["detail"]

    # 2. Change user role to "admin" in MockFirestoreDb
    from app.core.firebase_client import get_db
    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    record = user_ref.get().to_dict()
    record["role"] = "admin"
    user_ref.set(record)

    # Login to get admin access token
    login_resp_admin = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    admin_token = login_resp_admin.json()["access_token"]

    # Request dashboard with invalid admin token header -> 403 Forbidden
    response_bad_header = client.get(
        "/api/v1/admin/dashboard",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "wrong_token",
        },
    )
    assert response_bad_header.status_code == 403
    assert "Invalid admin token" in response_bad_header.json()["detail"]

    # Request dashboard with valid tokens -> 200 OK
    response_success = client.get(
        "/api/v1/admin/dashboard",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_success.status_code == 200
    data = response_success.json()
    assert isinstance(data["total_verifications"], int)
    assert isinstance(data["daily_verifications"], int)
    assert data["model_accuracy"] == 0.843
    assert data["api_health"] == "healthy"
    assert isinstance(data["active_users"], int)
    assert data["pending_reviews"] == 0
    assert data["system_uptime_percent"] == 100.0


def test_admin_train_status_endpoint_success_and_failures() -> None:
    """
    Verifies that GET /api/v1/admin/train/{job_id} enforces role controls,
    X-Admin-Token validation, and returns correct training progress metrics.
    """
    # 1. Register a user
    username = f"admin_train_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    assert client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201

    # Login to get session token
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    user_token = login_resp.json()["access_token"]

    # Request train status as regular user -> 403 Forbidden
    response_forbidden = client.get(
        "/api/v1/admin/train/job_123abc",
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_forbidden.status_code == 403
    assert "Admin privileges required" in response_forbidden.json()["detail"]

    # 2. Elevate role to admin in MockFirestoreDb
    from app.core.firebase_client import get_db
    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    record = user_ref.get().to_dict()
    record["role"] = "admin"
    user_ref.set(record)

    # Login to get admin access token
    login_resp_admin = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    admin_token = login_resp_admin.json()["access_token"]

    # Request train status with invalid admin override header -> 403 Forbidden
    response_bad_header = client.get(
        "/api/v1/admin/train/job_123abc",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "wrong_token",
        },
    )
    assert response_bad_header.status_code == 403
    assert "Invalid admin token" in response_bad_header.json()["detail"]

    # Request non-existent job ID -> 404 Not Found
    response_missing = client.get(
        "/api/v1/admin/train/non_existent_job_id",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_missing.status_code == 404
    assert "Training job not found" in response_missing.json()["detail"]

    # Request valid training job status -> 200 OK
    response_success = client.get(
        "/api/v1/admin/train/job_123abc",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_success.status_code == 200
    data = response_success.json()
    assert data == {
        "job_id": "job_123abc",
        "status": "in_progress",
        "progress_percent": 65,
        "current_epoch": 3,
        "total_epochs": 5,
        "current_loss": 0.234,
        "elapsed_time_minutes": 23,
        "estimated_remaining_minutes": 12,
    }


def test_admin_dataset_upload_endpoint_success_and_failures() -> None:
    """
    Verifies that POST /api/v1/admin/dataset/upload checks roles, X-Admin-Token headers,
    validates CSV column properties, and persists the dataset file to disk.
    """
    # 1. Register a user
    username = f"admin_upload_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    assert client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201

    # Login to get session token
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    user_token = login_resp.json()["access_token"]

    # Upload files payload
    good_csv_content = (
        "text,label,language,source\n"
        "\"Bitcoin rises.\",\"REAL\",\"en\",\"Reuters\"\n"
        "\"Solana crashed.\",\"FAKE\",\"zh\",\"WeChat\"\n"
    )
    bad_csv_content = "some_random_text,another_label\n\"r1\",\"r2\"\n"

    # Request upload as regular user -> 403 Forbidden
    response_forbidden = client.post(
        "/api/v1/admin/dataset/upload",
        files={"file": ("training_data.csv", good_csv_content, "text/csv")},
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_forbidden.status_code == 403
    assert "Admin privileges required" in response_forbidden.json()["detail"]

    # 2. Elevate role to admin in MockFirestoreDb
    from app.core.firebase_client import get_db
    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    record = user_ref.get().to_dict()
    record["role"] = "admin"
    user_ref.set(record)

    # Login to get admin access token
    login_resp_admin = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    admin_token = login_resp_admin.json()["access_token"]

    # Request upload with invalid admin override header -> 403 Forbidden
    response_bad_header = client.post(
        "/api/v1/admin/dataset/upload",
        files={"file": ("training_data.csv", good_csv_content, "text/csv")},
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "wrong_token",
        },
    )
    assert response_bad_header.status_code == 403
    assert "Invalid admin token" in response_bad_header.json()["detail"]

    # Request upload with bad CSV columns -> 400 Bad Request
    response_bad_csv = client.post(
        "/api/v1/admin/dataset/upload",
        files={"file": ("training_data_bad.csv", bad_csv_content, "text/csv")},
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_bad_csv.status_code == 400
    assert "missing columns" in response_bad_csv.json()["detail"].lower()

    # Request upload with valid CSV and headers -> 201 Created
    response_success = client.post(
        "/api/v1/admin/dataset/upload",
        files={"file": ("training_data.csv", good_csv_content, "text/csv")},
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_success.status_code == 201
    data = response_success.json()
    assert data["dataset_id"].startswith("dataset_")
    assert data["filename"] == "training_data.csv"
    assert data["samples_count"] == 2
    assert data["languages"] == ["en", "zh"]
    assert data["message"] == "Dataset uploaded successfully"

    # Verify that the file was written to data/training/
    dataset_file = os.path.join("data", "training", f"{data['dataset_id']}_training_data.csv")
    assert os.path.exists(dataset_file)
    with open(dataset_file, "r", encoding="utf-8") as f:
        file_content = f.read()
    assert file_content == good_csv_content


def test_admin_analytics_endpoint_success_and_failures() -> None:
    """
    Verifies that GET /api/v1/admin/analytics validates roles, X-Admin-Token override header,
    and yields complete system usage, cost, and classification stats.
    """
    # 1. Register a user
    username = f"admin_analytics_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    assert client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201

    # Login to get session token
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    user_token = login_resp.json()["access_token"]

    # Request analytics as regular user -> 403 Forbidden
    response_forbidden = client.get(
        "/api/v1/admin/analytics?period=30d",
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_forbidden.status_code == 403
    assert "Admin privileges required" in response_forbidden.json()["detail"]

    # 2. Elevate role to admin in MockFirestoreDb
    from app.core.firebase_client import get_db
    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    record = user_ref.get().to_dict()
    record["role"] = "admin"
    user_ref.set(record)

    # Login to get admin access token
    login_resp_admin = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    admin_token = login_resp_admin.json()["access_token"]

    # Request analytics with invalid admin override header -> 403 Forbidden
    response_bad_header = client.get(
        "/api/v1/admin/analytics?period=30d",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "wrong_token",
        },
    )
    assert response_bad_header.status_code == 403
    assert "Invalid admin token" in response_bad_header.json()["detail"]

    # Request analytics with valid credentials -> 200 OK
    response_success = client.get(
        "/api/v1/admin/analytics?period=30d",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_success.status_code == 200
    data = response_success.json()
    assert data["period"] == "30d"
    assert isinstance(data["api_usage"]["total_requests"], int)
    assert isinstance(data["api_usage"]["daily_average"], int)
    assert isinstance(data["api_usage"]["peak_daily"], int)
    assert isinstance(data["verification_stats"]["total"], int)
    assert isinstance(data["verification_stats"]["fake"], int)
    assert isinstance(data["verification_stats"]["real"], int)
    assert data["model_performance"] == {
        "accuracy": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1_score": 0.0,
    }
    assert data["cost_analysis"] == {
        "google_api_cost": 0.0,
        "ipfs_storage_gb": 0.0,
        "total_monthly": 0.0,
    }


def test_admin_users_endpoint_success_and_failures() -> None:
    """
    Verifies that GET /api/v1/admin/users validates roles, X-Admin-Token override header,
    and returns a paginated list of users with correct counts.
    """
    username = f"admin_users_{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "AdminPassword123!"

    # 1. Register a standard user
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert register_resp.status_code == 201
    user_id = register_resp.json()["user_id"]

    # Login standard user to get access token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    regular_token = login_resp.json()["access_token"]

    # Request users list as regular user -> 403 Forbidden
    response_forbidden = client.get(
        "/api/v1/admin/users?limit=10&offset=0",
        headers={
            "Authorization": f"Bearer {regular_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_forbidden.status_code == 403
    assert "Admin privileges required" in response_forbidden.json()["detail"]

    # 2. Promote standard user to admin role directly in MockFirestoreDb
    from app.core.firebase_client import get_db
    db = get_db()
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    assert user_ref.get().exists

    record = user_ref.get().to_dict()
    record["role"] = "admin"
    user_ref.set(record)

    # Login to get admin access token
    login_resp_admin = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    admin_token = login_resp_admin.json()["access_token"]

    # Request users list with invalid admin override header -> 403 Forbidden
    response_bad_header = client.get(
        "/api/v1/admin/users?limit=10&offset=0",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "wrong_token",
        },
    )
    assert response_bad_header.status_code == 403
    assert "Invalid admin token" in response_bad_header.json()["detail"]

    # Request users list with valid credentials -> 200 OK
    response_success = client.get(
        "/api/v1/admin/users?limit=10&offset=0",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_success.status_code == 200
    data = response_success.json()
    assert "users" in data
    assert data["total_count"] >= 1
    assert data["page"] == 1

    # Check if registered user item is present in list
    matched_user = None
    for u in data["users"]:
        if u["user_id"] == user_id:
            matched_user = u
            break
    assert matched_user is not None
    assert matched_user["username"] == username
    assert matched_user["email"] == email
    assert matched_user["role"] == "admin"
    assert "verifications_count" in matched_user
    assert isinstance(matched_user["verifications_count"], int)


def test_admin_user_deletion_endpoint() -> None:
    """
    Verifies that DELETE /api/v1/admin/users/{user_id} validates roles,
    prevents self-deletion, handles 404 missing user cases, and deletes files.
    """
    # 1. Create a standard user to delete
    username_del = f"user_del_{uuid4().hex[:8]}"
    email_del = f"{username_del}@example.com"
    password = "UserPassword123!"

    register_resp_del = client.post(
        "/api/v1/auth/register",
        json={"username": username_del, "email": email_del, "password": password},
    )
    assert register_resp_del.status_code == 201
    user_id_del = register_resp_del.json()["user_id"]

    # 2. Create an admin user to execute deletion
    username_adm = f"admin_del_{uuid4().hex[:8]}"
    email_adm = f"{username_adm}@example.com"

    register_resp_adm = client.post(
        "/api/v1/auth/register",
        json={"username": username_adm, "email": email_adm, "password": password},
    )
    assert register_resp_adm.status_code == 201
    user_id_adm = register_resp_adm.json()["user_id"]

    # Promote to admin
    from app.core.firebase_client import get_db
    db = get_db()
    email_adm_hash = hashlib.sha256(email_adm.encode("utf-8")).hexdigest()
    user_ref_adm = db.collection("users").document(email_adm_hash)
    record = user_ref_adm.get().to_dict()
    record["role"] = "admin"
    user_ref_adm.set(record)

    # Login admin user to get access token
    login_resp_adm = client.post(
        "/api/v1/auth/login",
        json={"email": email_adm, "password": password},
    )
    assert login_resp_adm.status_code == 200
    admin_token = login_resp_adm.json()["access_token"]

    # Request deletion as regular user (non-admin) -> 403 Forbidden
    login_resp_regular = client.post(
        "/api/v1/auth/login",
        json={"email": email_del, "password": password},
    )
    regular_token = login_resp_regular.json()["access_token"]

    response_forbidden = client.delete(
        f"/api/v1/admin/users/{user_id_del}",
        headers={
            "Authorization": f"Bearer {regular_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_forbidden.status_code == 403

    # Request self-deletion -> 400 Bad Request
    response_self = client.delete(
        f"/api/v1/admin/users/{user_id_adm}",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_self.status_code == 400
    assert "Self-deletion" in response_self.json()["detail"]

    # Request deletion of non-existent user ID -> 404 Not Found
    response_missing = client.delete(
        "/api/v1/admin/users/non_existent_id",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_missing.status_code == 404

    # Request deletion with invalid admin override token -> 403 Forbidden
    response_bad_header = client.delete(
        f"/api/v1/admin/users/{user_id_del}",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "wrong_token",
        },
    )
    assert response_bad_header.status_code == 403

    # Request successful deletion -> 200 OK
    response_success = client.delete(
        f"/api/v1/admin/users/{user_id_del}",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Token": "super_secret_admin_token_change_me",
        },
    )
    assert response_success.status_code == 200
    assert response_success.json()["user_id"] == user_id_del
    assert response_success.json()["message"] == "User deleted successfully"

    # Verify that user record is actually removed in MockFirestoreDb
    from app.core.firebase_client import get_db
    db = get_db()
    email_del_hash = hashlib.sha256(email_del.encode("utf-8")).hexdigest()
    user_ref_del = db.collection("users").document(email_del_hash)
    assert not user_ref_del.get().exists


def test_submit_user_feedback_endpoint() -> None:
    """
    Verifies that POST /api/v1/feedback accepts disputes and saves them to disk.
    """
    article_id = "507f1f77bcf86cd799439011"
    feedback_type = "incorrect_classification"
    message = "This news is actually real, not fake"
    user_email = "john@example.com"

    payload = {
        "article_id": article_id,
        "feedback_type": feedback_type,
        "message": message,
        "user_email": user_email,
    }

    # Request feedback submission -> 201 Created
    response = client.post("/api/v1/feedback", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert "feedback_id" in data
    assert data["status"] == "submitted"
    assert data["message"] == "Thank you for your feedback"

    # Verify that the feedback record was saved to Firestore
    from app.core.firebase_client import get_db
    db = get_db()
    feedback_id = data["feedback_id"]
    feedback_ref = db.collection("feedback").document(feedback_id)
    assert feedback_ref.get().exists

    saved_record = feedback_ref.get().to_dict()
    assert saved_record["feedback_id"] == feedback_id
    assert saved_record["article_id"] == article_id
    assert saved_record["feedback_type"] == feedback_type
    assert saved_record["message"] == message
    assert saved_record["user_email"] == user_email
    assert "submitted_at" in saved_record







