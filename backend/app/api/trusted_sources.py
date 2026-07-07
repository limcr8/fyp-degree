import datetime
import logging
import uuid

from fastapi import APIRouter, Header, HTTPException

from app.core.config import get_settings
from app.core.firebase_client import get_db
from models.auth_service import get_user_profile
from models.verification import AUTHORITATIVE_DOMAINS, invalidate_trusted_sources_cache
from app.schemas.trusted_sources import (
    TrustedSourceCreate,
    TrustedSourceListResponse,
    TrustedSourceMutationResponse,
    TrustedSourceResponse,
    TrustedSourceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/trusted-sources", tags=["admin-trusted-sources"])


def _require_admin(authorization: str, x_admin_token: str) -> None:
    """Validates the bearer token + admin override token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")
    access_token = authorization.split(" ", 1)[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _doc_to_response(source_id: str, data: dict) -> TrustedSourceResponse:
    return TrustedSourceResponse(
        source_id=source_id,
        domain=data.get("domain", ""),
        display_name=data.get("display_name", ""),
        tier=data.get("tier", "T2"),
        region=data.get("region", "global"),
        active=bool(data.get("active", True)),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )


@router.get("", response_model=TrustedSourceListResponse, status_code=200)
def list_trusted_sources(
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> TrustedSourceListResponse:
    """Lists every trusted source currently stored in Firestore."""
    _require_admin(authorization, x_admin_token)
    try:
        db = get_db()
        docs = list(db.collection("trusted_sources").stream())
    except Exception:
        logger.exception("Failed to read trusted_sources collection.")
        raise HTTPException(status_code=500, detail="Could not load trusted sources.")

    sources = [_doc_to_response(d.id, d.to_dict() or {}) for d in docs if hasattr(d, "to_dict")]
    sources.sort(key=lambda s: (s.tier, s.domain))
    return TrustedSourceListResponse(sources=sources, total_count=len(sources))


@router.post("", response_model=TrustedSourceMutationResponse, status_code=201)
def create_trusted_source(
    payload: TrustedSourceCreate,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> TrustedSourceMutationResponse:
    """Creates a single trusted source."""
    _require_admin(authorization, x_admin_token)
    source_id = f"ts-{uuid.uuid4().hex[:12]}"
    record = {
        "source_id": source_id,
        "domain": payload.domain,
        "display_name": payload.display_name.strip(),
        "tier": payload.tier,
        "region": payload.region.strip().lower(),
        "active": payload.active,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    try:
        db = get_db()
        db.collection("trusted_sources").document(source_id).set(record)
    except Exception:
        logger.exception("Failed to create trusted source %s.", source_id)
        raise HTTPException(status_code=500, detail="Could not create trusted source.")
    invalidate_trusted_sources_cache()
    return TrustedSourceMutationResponse(message="Trusted source created.", source_id=source_id)


@router.put("/{source_id}", response_model=TrustedSourceMutationResponse, status_code=200)
def update_trusted_source(
    source_id: str,
    payload: TrustedSourceUpdate,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> TrustedSourceMutationResponse:
    """Updates one or more fields of an existing trusted source."""
    _require_admin(authorization, x_admin_token)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updatable fields supplied.")
    if "region" in updates:
        updates["region"] = str(updates["region"]).strip().lower()
    updates["updated_at"] = _now_iso()
    try:
        db = get_db()
        doc_ref = db.collection("trusted_sources").document(source_id)
        snapshot = doc_ref.get()
        if not getattr(snapshot, "exists", False):
            raise HTTPException(status_code=404, detail="Trusted source not found.")
        doc_ref.update(updates)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update trusted source %s.", source_id)
        raise HTTPException(status_code=500, detail="Could not update trusted source.")
    invalidate_trusted_sources_cache()
    return TrustedSourceMutationResponse(message="Trusted source updated.", source_id=source_id)


@router.delete("/{source_id}", response_model=TrustedSourceMutationResponse, status_code=200)
def delete_trusted_source(
    source_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> TrustedSourceMutationResponse:
    """Deletes a trusted source permanently."""
    _require_admin(authorization, x_admin_token)
    try:
        db = get_db()
        doc_ref = db.collection("trusted_sources").document(source_id)
        snapshot = doc_ref.get()
        if not getattr(snapshot, "exists", False):
            raise HTTPException(status_code=404, detail="Trusted source not found.")
        doc_ref.delete()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete trusted source %s.", source_id)
        raise HTTPException(status_code=500, detail="Could not delete trusted source.")
    invalidate_trusted_sources_cache()
    return TrustedSourceMutationResponse(message="Trusted source deleted.", source_id=source_id)


@router.post("/seed", response_model=TrustedSourceMutationResponse, status_code=200)
def seed_trusted_sources(
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> TrustedSourceMutationResponse:
    """Backfills the trusted_sources collection from the built-in baseline."""
    _require_admin(authorization, x_admin_token)
    now = _now_iso()
    inserted = 0
    try:
        db = get_db()
        col = db.collection("trusted_sources")
        for domain, display_name in AUTHORITATIVE_DOMAINS.items():
            doc_id = f"ts-{uuid.uuid4().hex[:12]}"
            col.document(doc_id).set({
                "source_id": doc_id,
                "domain": domain,
                "display_name": display_name,
                "tier": "T1",
                "region": "global",
                "active": True,
                "created_at": now,
                "updated_at": now,
            })
            inserted += 1
    except Exception:
        logger.exception("Failed to seed trusted sources.")
        raise HTTPException(status_code=500, detail="Could not seed trusted sources.")
    invalidate_trusted_sources_cache()
    return TrustedSourceMutationResponse(
        message=f"Seeded {inserted} baseline trusted sources.", source_id=None
    )