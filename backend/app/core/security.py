import datetime
import logging

from fastapi import Header, HTTPException

from app.core.firebase_client import get_db
from models.auth_service import create_access_token_for_email

logger = logging.getLogger(__name__)

API_QUOTA_DEFAULT_LIMIT = 100


def _find_user_by_api_key(api_key: str):
    db = get_db()
    users_col = db.collection("users")
    for doc in users_col.stream():
        data = doc.to_dict() or {}
        if data.get("api_key") == api_key:
            user_ref = users_col.document(doc.id)
            return user_ref, data
    return None, None


def _resolve_quota(user_record: dict) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    quota = dict(user_record.get("api_quota") or {})
    reset_at_str = quota.get("reset_at")
    reset_at = None
    if reset_at_str:
        try:
            reset_at = datetime.datetime.strptime(
                reset_at_str, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=datetime.timezone.utc)
        except (ValueError, TypeError):
            reset_at = None

    if not reset_at or now >= reset_at:
        tomorrow = now + datetime.timedelta(days=1)
        quota = {
            "daily_limit": quota.get("daily_limit", API_QUOTA_DEFAULT_LIMIT),
            "used_today": 0,
            "reset_at": tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    else:
        quota = {
            "daily_limit": quota.get("daily_limit", API_QUOTA_DEFAULT_LIMIT),
            "used_today": quota.get("used_today", 0),
            "reset_at": reset_at_str,
        }
    return quota


def _enforce_and_increment_quota(user_ref, user_record: dict) -> None:
    quota = _resolve_quota(user_record)
    used = quota.get("used_today", 0)
    limit = quota.get("daily_limit", API_QUOTA_DEFAULT_LIMIT)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily API quota exceeded. Resets at {quota.get('reset_at', 'midnight UTC')}.",
        )
    quota["used_today"] = used + 1
    try:
        try:
            user_ref.update({"api_quota": quota})
        except (AttributeError, TypeError):
            user_ref.set({"api_quota": quota}, merge=True)
    except Exception:
        logger.exception("Failed to persist API quota increment.")


def require_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key", description="Per-user API key for programmatic access"),
) -> str | None:
    """Validates an X-API-Key header, enforces the caller's daily quota, and
    returns an ephemeral access token bridging into the existing auth pipeline.

    Returns None when no API key is supplied so callers may fall back to Bearer auth.

    Raises:
        HTTPException: 401 if the key is invalid, 429 if the daily quota is exhausted.
    """
    if not x_api_key:
        return None
    user_ref, user_record = _find_user_by_api_key(x_api_key)
    if not user_record:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    _enforce_and_increment_quota(user_ref, user_record)
    return create_access_token_for_email(user_record["email"])