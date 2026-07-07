import json
import logging
import os
import hashlib
import base64
import time
import datetime
import secrets
import hmac
from uuid import uuid4

from app.core.config import get_settings
from app.schemas.auth import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse, UserDetail, RefreshResponse, LogoutResponse, UserMeResponse, ApiQuota, UpdateProfileRequest, UpdateProfileResponse, ChangePasswordRequest, ChangePasswordResponse
from app.schemas.admin import AdminUsersResponse, AdminUserItem
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.core.firebase_client import get_db

logger = logging.getLogger(__name__)

USERS_DIR = os.path.join("data", "users")


def _resolve_admin_role(email: str) -> str:
    """
    Determines the user role based on the ADMIN_EMAILS environment variable.

    The ADMIN_EMAILS env var is a comma-separated list of emails that should
    be granted admin privileges, e.g.:
        ADMIN_EMAILS=admin@example.com,root@example.com

    Args:
        email (str): The user's normalized email address.

    Returns:
        str: 'admin' if the email is in the admin list, otherwise 'user'.
    """
    admin_emails_raw = os.environ.get("ADMIN_EMAILS", "")
    admin_emails = {
        e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()
    }
    if email.strip().lower() in admin_emails:
        return "admin"
    return "user"


def register_user(request: RegisterRequest) -> RegisterResponse:
    """
    Registers a new user and persists their account locally.

    Args:
        request (RegisterRequest): The registration payload.

    Returns:
        RegisterResponse: Successful registration response.
    """
    db = get_db()
    normalized_email = request.email.strip().lower()
    email_hash = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)

    # 1. Check if email already registered
    if user_ref.get().exists:
        raise ValueError("Email address already registered.")

    # 2. Auto-generate username from email prefix (unique)
    provided_name = request.username.strip() if request.username else normalized_email.split("@")[0]
    base_slug = provided_name.lower().replace(" ", "_")
    existing_usernames = {
        (d.to_dict().get("username", "") or "").strip().lower()
        for d in db.collection("users").stream()
    }
    username = base_slug
    suffix = 1
    while username.strip().lower() in existing_usernames:
        username = f"{base_slug}{suffix}"
        suffix += 1

    # 3. Create user record
    user_id = str(uuid4())
    api_key = f"sk_live_{str(uuid4()).replace('-', '')[:24]}"
    pwdhash, salt = _hash_password(request.password)
    # Determine role: 'admin' if email is in ADMIN_EMAILS, otherwise 'user'
    assigned_role = _resolve_admin_role(normalized_email)

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tomorrow = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    reset_at = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    user_record = {
        "user_id": user_id,
        "username": username,
        "name": provided_name,
        "email": normalized_email,
        "password_hash": pwdhash,
        "salt": salt,
        "role": assigned_role,
        "api_key": api_key,
        "firebase_uid": request.firebase_uid,
        "created_at": now_iso,
        "last_login": now_iso,
        "api_quota": {
            "daily_limit": 100,
            "used_today": 0,
            "reset_at": reset_at,
        }
    }

    # 4. Save user document
    user_ref.set(user_record)

    return RegisterResponse(
        user_id=user_id,
        username=username,
        email=normalized_email,
        role=assigned_role,
        api_key=api_key,
        doc_id=email_hash,
        message="Account created successfully",
    )


def _hash_password(password: str) -> tuple[str, str]:
    """
    Hashes a password with PBKDF2-HMAC-SHA256 and a random salt.
    """
    salt = os.urandom(16)
    pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return pwdhash.hex(), salt.hex()


def _verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verifies a password against its PBKDF2-HMAC-SHA256 hash.

    Args:
        password (str): The plain text password to verify.
        password_hash (str): The hex-encoded target hash.
        salt (str): The hex-encoded salt.

    Returns:
        bool: True if password matches the hash, False otherwise.
    """
    pwdhash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000
    )
    return pwdhash.hex() == password_hash


def _base64url_encode(data: bytes) -> str:
    """Encodes bytes into a base64url string without padding.

    Args:
        data (bytes): The byte string to encode.

    Returns:
        str: The base64url encoded string.
    """
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _generate_jwt(payload: dict, secret: str) -> str:
    """Generates a HS256 JWT using standard Python libraries.

    Args:
        payload (dict): The token payload dictionary.
        secret (str): The secret key used for signing.

    Returns:
        str: The signed JWT string.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    header_b64 = _base64url_encode(header_json)
    payload_b64 = _base64url_encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def authenticate_user(request: LoginRequest) -> LoginResponse:
    """Authenticates a user with email and password.

    Loads the user credentials from local disk, verifies the password hash, and
    generates a signed JWT access token.

    Args:
        request (LoginRequest): User email and password payload.

    Returns:
        LoginResponse: Successful login response detailing access tokens and user profile.

    Raises:
        ValueError: If email is not registered or password is incorrect.
    """
    db = get_db()
    normalized_email = request.email.strip().lower()
    email_hash = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    user_snap = user_ref.get()

    if not user_snap.exists:
        raise ValueError("Invalid email or password.")

    user_record = user_snap.to_dict()

    if not _verify_password(request.password, user_record["password_hash"], user_record["salt"]):
        raise ValueError("Invalid email or password.")

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    user_record["last_login"] = now_iso
    try:
        user_ref.update({"last_login": now_iso})
    except Exception:
        logger.exception("Failed to update last_login on user record.")

    # Promote to admin if the email is in ADMIN_EMAILS (even if already registered as 'user').
    # This lets existing users become admins without re-registering.
    if _resolve_admin_role(user_record.get("email", "")) == "admin" and user_record.get("role") != "admin":
        user_record["role"] = "admin"
        try:
            user_ref.update({"role": "admin"})
            logger.info("Promoted user %s to admin via ADMIN_EMAILS.", user_record.get("email"))
        except Exception:
            logger.exception("Failed to persist admin promotion for %s.", user_record.get("email"))

    settings = get_settings()
    expires_in = 3600
    payload = {
        "sub": user_record["user_id"],
        "email": user_record["email"],
        "username": user_record["username"],
        "role": user_record.get("role", "user"),
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }

    access_token = _generate_jwt(payload, settings.jwt_secret_key)
    
    refresh_payload = {
        "sub": user_record["user_id"],
        "email": user_record["email"],
        "username": user_record["username"],
        "role": user_record.get("role", "user"),
        "type": "refresh",
        "exp": int(time.time()) + (7 * 24 * 3600), # 7 days
        "iat": int(time.time()),
    }
    refresh_token = _generate_jwt(refresh_payload, settings.jwt_secret_key)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=expires_in,
        user=UserDetail(
            user_id=user_record["user_id"],
            username=user_record["username"],
            role=user_record.get("role", "user"),
        ),
    )


def _verify_and_decode_jwt(token: str, secret: str) -> dict:
    """Decodes and verifies a JWT token.

    Args:
        token (str): The JWT token string.
        secret (str): The signing secret.

    Returns:
        dict: The decoded token payload.

    Raises:
        ValueError: If token format, signature, or expiration is invalid.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format.")

    header_b64, payload_b64, signature_b64 = parts

    # Reconstruct signing input
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()

    # Base64url decode helper
    def base64url_decode(s: str) -> bytes:
        rem = len(s) % 4
        if rem > 0:
            s += "=" * (4 - rem)
        return base64.urlsafe_b64decode(s.encode("utf-8"))

    try:
        decoded_sig = base64url_decode(signature_b64)
    except Exception as exc:
        raise ValueError("Invalid signature encoding.") from exc

    if not hmac.compare_digest(decoded_sig, expected_signature):
        raise ValueError("Invalid signature.")

    try:
        payload = json.loads(base64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid payload encoding.") from exc

    if "exp" in payload and time.time() > payload["exp"]:
        raise ValueError("Token has expired.")

    return payload


def refresh_access_token(refresh_token: str) -> RefreshResponse:
    """Refreshes the access token using a valid refresh token.

    Args:
        refresh_token (str): The signed refresh token.

    Returns:
        RefreshResponse: A new signed access token and expiration window.

    Raises:
        ValueError: If the refresh token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = _verify_and_decode_jwt(refresh_token, settings.jwt_secret_key)
    except ValueError as exc:
        raise ValueError(f"Invalid refresh token: {str(exc)}") from exc

    # Ensure it's a refresh token, not an access token
    if payload.get("type") != "refresh":
        raise ValueError("Invalid token type.")

    # Generate a new access token
    expires_in = 3600
    access_payload = {
        "sub": payload["sub"],
        "email": payload["email"],
        "username": payload["username"],
        "role": payload.get("role", "user"),
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }

    access_token = _generate_jwt(access_payload, settings.jwt_secret_key)

    return RefreshResponse(
        access_token=access_token,
        expires_in=expires_in,
    )


def logout_user_session(access_token: str) -> LogoutResponse:
    """Validates the active user session token during logout.

    Args:
        access_token (str): The active user session access token.

    Returns:
        LogoutResponse: Successful logout message.

    Raises:
        ValueError: If the token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = _verify_and_decode_jwt(access_token, settings.jwt_secret_key)
    except ValueError as exc:
        raise ValueError(f"Invalid access token: {str(exc)}") from exc

    if payload.get("type") == "refresh":
        raise ValueError("Invalid token type.")

    return LogoutResponse(message="Logged out successfully")


def create_access_token_for_email(email: str) -> str:
    """Mints a short-lived access token for a user identified by email.

    Used to bridge API-key authentication into the existing token-based request
    pipeline without requiring external clients to perform a full login flow.

    Args:
        email (str): The registered email of the API-key owner.

    Returns:
        str: A signed HS256 access JWT valid for one hour.

    Raises:
        ValueError: If no user exists for the supplied email.
    """
    settings = get_settings()
    normalized_email = email.strip().lower()
    email_hash = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    db = get_db()
    user_ref = db.collection("users").document(email_hash)
    user_snap = user_ref.get()
    if not user_snap.exists:
        raise ValueError("User not found.")
    user_record = user_snap.to_dict()

    expires_in = 3600
    payload = {
        "sub": user_record.get("user_id", ""),
        "email": user_record.get("email", normalized_email),
        "username": user_record.get("username", ""),
        "role": user_record.get("role", "user"),
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }
    return _generate_jwt(payload, settings.jwt_secret_key)


def get_user_profile(access_token: str) -> UserMeResponse:
    """Retrieves the full profile of the authenticated user.

    Args:
        access_token (str): The active session token.

    Returns:
        UserMeResponse: The detailed user profile.

    Raises:
        ValueError: If token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = _verify_and_decode_jwt(access_token, settings.jwt_secret_key)
    except ValueError as exc:
        raise ValueError(f"Invalid access token: {str(exc)}") from exc

    if payload.get("type") == "refresh":
        raise ValueError("Invalid token type.")

    db = get_db()
    email = payload["email"]
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    user_snap = user_ref.get()

    if not user_snap.exists:
        raise ValueError("User not found.")

    user_record = user_snap.to_dict()

    # Compute/sanitize/fallback fields
    now = datetime.datetime.now(datetime.timezone.utc)
    if "created_at" not in user_record:
        user_record["created_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "last_login" not in user_record:
        user_record["last_login"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Quota check / reset logic
    quota = user_record.get("api_quota", {})
    reset_at_str = quota.get("reset_at")
    reset_at = None
    if reset_at_str:
        try:
            reset_at = datetime.datetime.strptime(reset_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pass

    if not reset_at or now >= reset_at:
        # Reset quota
        tomorrow = now + datetime.timedelta(days=1)
        new_reset_at = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        quota = {
            "daily_limit": 100,
            "used_today": 0,
            "reset_at": new_reset_at,
        }
        user_record["api_quota"] = quota
        try:
            user_ref.update({"api_quota": quota})
        except Exception:
            logger.exception("Failed to save updated user record quota.")
    else:
        # Quota is still valid, ensure structure
        quota = {
            "daily_limit": quota.get("daily_limit", 100),
            "used_today": quota.get("used_today", 0),
            "reset_at": reset_at_str,
        }

    return UserMeResponse(
        user_id=user_record["user_id"],
        username=user_record["username"],
        name=user_record.get("name", user_record["username"]),
        email=user_record["email"],
        role=user_record.get("role", "user"),
        api_key=user_record.get("api_key", ""),
        api_quota=ApiQuota(
            daily_limit=quota["daily_limit"],
            used_today=quota["used_today"],
            reset_at=quota["reset_at"],
        ),
        created_at=user_record["created_at"],
        last_login=user_record.get("last_login"),
        preferences=user_record.get("preferences"),
    )


def update_user_profile(access_token: str, request: UpdateProfileRequest) -> UpdateProfileResponse:
    """Updates the user profile (username, email, preferences).

    Re-hashes and moves the user database file if the email changes, and checks
    for username/email duplicates.

    Args:
        access_token (str): The active session token.
        request (UpdateProfileRequest): The profile update payload.

    Returns:
        UpdateProfileResponse: Success confirmation and updated user profile.

    Raises:
        ValueError: If token is invalid, or if new email/username is already taken.
    """
    settings = get_settings()
    try:
        payload = _verify_and_decode_jwt(access_token, settings.jwt_secret_key)
    except ValueError as exc:
        raise ValueError(f"Invalid access token: {str(exc)}") from exc

    if payload.get("type") == "refresh":
        raise ValueError("Invalid token type.")

    db = get_db()
    old_email = payload["email"]
    old_email_hash = hashlib.sha256(old_email.encode("utf-8")).hexdigest()
    old_user_ref = db.collection("users").document(old_email_hash)
    old_user_snap = old_user_ref.get()

    if not old_user_snap.exists:
        raise ValueError("User not found.")

    user_record = old_user_snap.to_dict()
    user_id = user_record["user_id"]

    # 2. Check and validate new username
    new_username = request.username.strip()
    normalized_new_username = new_username.lower()
    
    # Verify username uniqueness across other users
    username_exists = False
    for doc in db.collection("users").stream():
        u_data = doc.to_dict()
        if u_data.get("user_id") != user_id and u_data.get("username", "").strip().lower() == normalized_new_username:
            username_exists = True
            break
    if username_exists:
        raise ValueError("Username already taken.")

    # 3. Check and validate new email
    new_email = request.email.strip().lower()
    new_email_hash = hashlib.sha256(new_email.encode("utf-8")).hexdigest()
    new_user_ref = db.collection("users").document(new_email_hash)

    if new_email != old_email:
        new_user_snap = new_user_ref.get()
        if new_user_snap.exists:
            if new_user_snap.to_dict().get("user_id") != user_id:
                raise ValueError("Email address already registered.")

    # 4. Perform updates
    user_record["username"] = new_username
    user_record["name"] = request.username.strip()
    user_record["email"] = new_email
    user_record["preferences"] = {
        "language": request.preferences.language,
        "notifications": request.preferences.notifications,
    }

    # 5. Persist and rename if email changes
    if new_email != old_email:
        try:
            new_user_ref.set(user_record)
            old_user_ref.delete()
        except Exception as exc:
            logger.exception("Failed to relocate user profile doc.")
            raise ValueError("Profile persistence failed.") from exc
    else:
        try:
            old_user_ref.set(user_record)
        except Exception as exc:
            logger.exception("Failed to update user profile doc.")
            raise ValueError("Profile persistence failed.") from exc

    # 6. Retrieve detailed profile response
    quota = user_record.get("api_quota", {"daily_limit": 100, "used_today": 0, "reset_at": ""})
    
    updated_user = UserMeResponse(
        user_id=user_record["user_id"],
        username=user_record["username"],
        name=user_record.get("name", user_record["username"]),
        email=user_record["email"],
        role=user_record.get("role", "user"),
        api_key=user_record.get("api_key", ""),
        api_quota=ApiQuota(
            daily_limit=quota.get("daily_limit", 100),
            used_today=quota.get("used_today", 0),
            reset_at=quota.get("reset_at", ""),
        ),
        created_at=user_record.get("created_at", ""),
        last_login=user_record.get("last_login"),
        preferences=user_record.get("preferences"),
    )

    return UpdateProfileResponse(
        message="Profile updated successfully",
        user=updated_user,
    )


def change_user_password(access_token: str, request: ChangePasswordRequest) -> ChangePasswordResponse:
    """Changes the user's password in their local file database.

    Args:
        access_token (str): The active session token.
        request (ChangePasswordRequest): The old and new passwords.

    Returns:
        ChangePasswordResponse: Success confirmation message.

    Raises:
        ValueError: If token is invalid, or if the old password is incorrect.
    """
    settings = get_settings()
    try:
        payload = _verify_and_decode_jwt(access_token, settings.jwt_secret_key)
    except ValueError as exc:
        raise ValueError(f"Invalid access token: {str(exc)}") from exc

    if payload.get("type") == "refresh":
        raise ValueError("Invalid token type.")

    db = get_db()
    email = payload["email"]
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    user_ref = db.collection("users").document(email_hash)
    user_snap = user_ref.get()

    if not user_snap.exists:
        raise ValueError("User not found.")

    user_record = user_snap.to_dict()

    # Verify old password
    if not _verify_password(request.old_password, user_record["password_hash"], user_record["salt"]):
        raise ValueError("Invalid old password.")

    # Hash new password
    pwdhash, salt = _hash_password(request.new_password)
    user_record["password_hash"] = pwdhash
    user_record["salt"] = salt

    # Persist updated user record
    try:
        user_ref.set(user_record)
    except Exception as exc:
        logger.exception("Failed to update user password.")
        raise ValueError("Password persistence failed.") from exc

    return ChangePasswordResponse(message="Password changed successfully")


def get_user_history(access_token: str, limit: int = 20, offset: int = 0) -> "UserHistoryResponse":
    """Retrieves the verification history of the authenticated user.

    Args:
        access_token (str): The active session token.
        limit (int): The maximum number of history records to return.
        offset (int): The pagination offset.

    Returns:
        UserHistoryResponse: Paginated list of user's verification history.

    Raises:
        ValueError: If access token is invalid or user not found.
    """
    from app.schemas.analysis import UserHistoryResponse, HistoryItem
    settings = get_settings()
    try:
        payload = _verify_and_decode_jwt(access_token, settings.jwt_secret_key)
    except ValueError as exc:
        raise ValueError(f"Invalid access token: {str(exc)}") from exc

    if payload.get("type") == "refresh":
        raise ValueError("Invalid token type.")

    db = get_db()
    email = payload["email"]
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()

    history_docs = db.collection("users").document(email_hash).collection("history").stream()
    history = [doc.to_dict() for doc in history_docs]
    history.sort(key=lambda x: x.get("verified_at", "") or "", reverse=True)
    total_count = len(history)

    # Slice for pagination
    sliced_history = history[offset : offset + limit]
    
    # Calculate page number
    page = (offset // limit) + 1 if limit > 0 else 1

    # Map raw JSON objects to HistoryItem model
    history_items = []
    for item in sliced_history:
        try:
            history_items.append(HistoryItem.model_validate(item))
        except Exception:
            logger.exception("Skipping malformed history item.")
            continue

    return UserHistoryResponse(
        history=history_items,
        total_count=total_count,
        page=page,
    )


def add_report_to_user_history(access_token: str, report: "AnalyzeResponse") -> None:
    """Appends an analyzed report to the user's verification history in their user record.

    Args:
        access_token (str): The active session token.
        report (AnalyzeResponse): The generated report model.
    """
    settings = get_settings()
    try:
        payload = _verify_and_decode_jwt(access_token, settings.jwt_secret_key)
    except ValueError as exc:
        raise ValueError(f"Invalid access token: {str(exc)}") from exc

    if payload.get("type") == "refresh":
        raise ValueError("Invalid token type.")

    db = get_db()
    email = payload["email"]
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()

    # Map AnalyzeResponse to HistoryItem fields
    history_item = {
        "article_id": report.id,
        "text": report.text,
        "classification": report.classification.model_dump(by_alias=True),
        "verified_at": report.created_at,
        "explanation": report.explanation.model_dump(by_alias=True) if report.explanation else None,
        "verification": report.verification.model_dump(by_alias=True) if report.verification else None,
        "finalAssessment": report.final_assessment.model_dump() if report.final_assessment else None,
        "blockchain": report.blockchain.model_dump(by_alias=True) if report.blockchain else None,
        "processingTimeMs": report.processing_time_ms,
        "platform": report.platform,
        "language": report.language,
        "stored_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "stored_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    history_ref = db.collection("users").document(email_hash).collection("history").document(report.id)
    try:
        history_ref.set(history_item)
    except Exception as exc:
        logger.exception("Failed to save report to user history subcollection.")
        raise ValueError("Database write failed.") from exc


def get_training_job(job_id: str) -> dict | None:
    """Retrieves status and progress metrics of a model training job.

    Args:
        job_id (str): The unique identifier of the training job.

    Returns:
        dict | None: The job training status dictionary if found, else None.
    """
    db = get_db()
    job_ref = db.collection("training_jobs").document(job_id)
    job_snap = job_ref.get()

    if not job_snap.exists:
        # If default job, pre-populate
        if job_id == "job_123abc":
            default_job = {
                "job_id": "job_123abc",
                "status": "in_progress",
                "progress_percent": 65,
                "current_epoch": 3,
                "total_epochs": 5,
                "current_loss": 0.234,
                "elapsed_time_minutes": 23,
                "estimated_remaining_minutes": 12,
            }
            try:
                job_ref.set(default_job)
                return default_job
            except Exception:
                return default_job
        return None

    return job_snap.to_dict()


def get_admin_users(limit: int = 50, offset: int = 0) -> AdminUsersResponse:
    """Retrieves all registered user profiles with pagination.

    Args:
        limit (int): Max number of user entries to return.
        offset (int): Starting index offset for pagination.

    Returns:
        AdminUsersResponse: Paginated list of users with total user count and page number.
    """
    db = get_db()
    users = []
    
    for doc in db.collection("users").stream():
        user_data = doc.to_dict()
        try:
            verifications_count = len(list(doc.collection("history").stream()))
        except Exception:
            logger.warning("Could not read history subcollection for user %s", user_data.get("user_id", "?"))
            verifications_count = 0
        users.append({
            "user_id": user_data.get("user_id", ""),
            "username": user_data.get("username", ""),
            "email": user_data.get("email", ""),
            "role": user_data.get("role", "user"),
            "created_at": user_data.get("created_at", ""),
            "last_login": user_data.get("last_login", ""),
            "verifications_count": verifications_count
        })

    # Sort users by created_at descending (latest users first)
    users.sort(key=lambda u: u.get("created_at", ""), reverse=True)

    total_count = len(users)
    sliced_users = users[offset : offset + limit]

    # Calculate page number
    page = (offset // limit) + 1 if limit > 0 else 1

    mapped_users = []
    for u in sliced_users:
        try:
            mapped_users.append(AdminUserItem.model_validate(u))
        except Exception:
            logger.exception("Skipping malformed user record validation.")
            continue

    return AdminUsersResponse(
        users=mapped_users,
        total_count=total_count,
        page=page
    )


def delete_admin_user(user_id: str) -> bool:
    """Deletes a user record JSON file matching the provided user_id.

    Args:
        user_id (str): The unique identifier of the target user.

    Returns:
        bool: True if user record was successfully located and deleted, False otherwise.
    """
    db = get_db()
    for doc in db.collection("users").stream():
        user_data = doc.to_dict()
        if user_data.get("user_id") == user_id:
            try:
                db.collection("users").document(doc.id).delete()
                return True
            except Exception:
                logger.exception(f"Error deleting user document: {doc.id}")
                return False
    return False


def submit_user_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Persists user feedback submissions to disk as JSON records.

    Args:
        request (FeedbackRequest): Feedback details submitted by the user.

    Returns:
        FeedbackResponse: Confirmation message and feedback ID.
    """
    db = get_db()
    feedback_id = f"feedback_{str(uuid4()).replace('-', '')[:12]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    feedback_record = {
        "feedback_id": feedback_id,
        "article_id": request.article_id,
        "feedback_type": request.feedback_type,
        "message": request.message,
        "user_email": request.user_email,
        "submitted_at": now_iso
    }

    try:
        db.collection("feedback").document(feedback_id).set(feedback_record)
    except Exception as exc:
        logger.exception("Failed to persist user feedback record.")
        raise ValueError("Database write failed.") from exc

    return FeedbackResponse(
        feedback_id=feedback_id,
        status="submitted",
        message="Thank you for your feedback"
    )





