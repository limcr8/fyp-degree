import csv
import datetime
import logging
import os
import uuid

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.firebase_client import get_db
from app.schemas.datasets import (
    DatasetDetailResponse,
    DatasetListResponse,
    DatasetMetadata,
    DatasetMutationResponse,
    DatasetStats,
    DatasetUploadResponse,
    SourceCount,
)
from models.auth_service import get_user_profile
from training.train_roberta import normalize_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/datasets", tags=["admin-datasets"])

REQUIRED_COLUMNS = ["text", "label", "language", "source"]
DATASETS_DIR = os.path.join("data", "training")


def _require_admin(authorization: str, x_admin_token: str) -> str:
    """Validates admin session and returns the admin's email."""
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
    return user_profile.email or user_profile.username


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"


def _compute_stats(filepath: str) -> DatasetStats:
    """Reads a CSV and builds a rich DatasetStats profile."""
    total_rows = 0
    valid_samples = 0
    label_dist: dict[str, int] = {}
    lang_dist: dict[str, int] = {}
    source_dist: dict[str, int] = {}

    with open(filepath, "r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            total_rows += 1
            text = (row.get("text") or "").strip()
            label_raw = (row.get("label") or "").strip()
            lang = (row.get("language") or "").strip()
            src = (row.get("source") or "").strip()

            if not (text and label_raw and lang and src):
                continue
            valid_samples += 1
            try:
                norm = normalize_label(label_raw)
            except ValueError:
                norm = label_raw.upper()
            label_dist[norm] = label_dist.get(norm, 0) + 1
            lang_dist[lang] = lang_dist.get(lang, 0) + 1
            source_dist[src] = source_dist.get(src, 0) + 1

    completeness = (valid_samples / total_rows * 100) if total_rows else 0.0
    real = label_dist.get("REAL", 0)
    fake = label_dist.get("FAKE", 0)
    balanced_total = real + fake
    is_balanced = (
        balanced_total > 0 and abs(real - fake) / balanced_total < 0.35
    )

    if valid_samples >= 1000 and is_balanced and completeness >= 90:
        quality = "high"
    elif valid_samples >= 100 and is_balanced:
        quality = "medium"
    else:
        quality = "low"

    top_sources = [
        SourceCount(source=s, count=c)
        for s, c in sorted(source_dist.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    return DatasetStats(
        total_rows=total_rows,
        valid_samples=valid_samples,
        completeness_pct=round(completeness, 1),
        label_distribution=label_dist,
        languages=lang_dist,
        top_sources=top_sources,
        is_balanced=is_balanced,
        quality_tier=quality,
    )


def _doc_to_metadata(doc_id: str, data: dict) -> DatasetMetadata:
    stats_data = data.get("stats") or {}
    stats = DatasetStats(**stats_data) if stats_data else None
    return DatasetMetadata(
        dataset_id=doc_id,
        filename=data.get("filename", ""),
        storage_path=data.get("storage_path", ""),
        file_size_bytes=data.get("file_size_bytes", 0),
        file_size_display=data.get("file_size_display", ""),
        uploaded_at=data.get("uploaded_at", ""),
        uploaded_by=data.get("uploaded_by", ""),
        is_active=bool(data.get("is_active", False)),
        stats=stats,
    )


@router.get("", response_model=DatasetListResponse, status_code=200)
def list_datasets(
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> DatasetListResponse:
    """Lists every dataset metadata record currently in Firestore."""
    _require_admin(authorization, x_admin_token)
    try:
        db = get_db()
        docs = list(db.collection("datasets").stream())
    except Exception:
        logger.exception("Failed to read datasets collection.")
        raise HTTPException(status_code=500, detail="Could not load datasets.")

    datasets = [_doc_to_metadata(d.id, d.to_dict() or {}) for d in docs if hasattr(d, "to_dict")]
    datasets.sort(key=lambda x: x.uploaded_at, reverse=True)
    return DatasetListResponse(datasets=datasets, total_count=len(datasets))


@router.post("", response_model=DatasetUploadResponse, status_code=201)
def upload_dataset(
    file: UploadFile = File(..., description="CSV training dataset"),
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> DatasetUploadResponse:
    """Validates, saves, and profiles an uploaded training CSV."""
    admin_email = _require_admin(authorization, x_admin_token)

    try:
        contents = file.file.read()
        decoded = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded)) if False else csv.DictReader(
            decoded.splitlines()
        )
        headers = reader.fieldnames or []
        for col in REQUIRED_COLUMNS:
            if col not in headers:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column: {col}. Required: {', '.join(REQUIRED_COLUMNS)}",
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {exc}") from exc

    dataset_id = f"dataset_{uuid.uuid4().hex[:12]}"
    try:
        os.makedirs(DATASETS_DIR, exist_ok=True)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not create datasets directory.")

    safe_filename = "".join(c for c in (file.filename or "upload.csv") if c.isalnum() or c in "._-")
    saved_filepath = os.path.join(DATASETS_DIR, f"{dataset_id}_{safe_filename}")

    try:
        with open(saved_filepath, "wb") as out:
            out.write(contents)
    except Exception as exc:
        logger.exception("Failed to persist dataset %s.", dataset_id)
        raise HTTPException(status_code=500, detail="Failed to save dataset file.") from exc

    stats = _compute_stats(saved_filepath)
    file_size = os.path.getsize(saved_filepath)

    record = {
        "dataset_id": dataset_id,
        "filename": file.filename or "upload.csv",
        "storage_path": saved_filepath,
        "file_size_bytes": file_size,
        "file_size_display": _human_size(file_size),
        "uploaded_at": _now_iso(),
        "uploaded_by": admin_email,
        "is_active": False,
        "stats": stats.model_dump(by_alias=True),
    }
    try:
        db = get_db()
        db.collection("datasets").document(dataset_id).set(record)
    except Exception:
        logger.exception("Failed to persist dataset metadata %s.", dataset_id)
        raise HTTPException(status_code=500, detail="Could not persist dataset metadata.")

    return DatasetUploadResponse(
        message="Dataset uploaded and profiled successfully.",
        dataset_id=dataset_id,
        stats=stats,
    )


@router.get("/{dataset_id}", response_model=DatasetDetailResponse, status_code=200)
def get_dataset_detail(
    dataset_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> DatasetDetailResponse:
    """Returns the full metadata + stats for a single dataset."""
    _require_admin(authorization, x_admin_token)
    try:
        db = get_db()
        doc = db.collection("datasets").document(dataset_id).get()
    except Exception:
        raise HTTPException(status_code=500, detail="Could not fetch dataset.")
    if not getattr(doc, "exists", False):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return _doc_to_metadata(dataset_id, doc.to_dict() or {})


@router.post("/{dataset_id}/activate", response_model=DatasetMutationResponse, status_code=200)
def activate_dataset(
    dataset_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> DatasetMutationResponse:
    """Flags a single dataset as the active source for the next training run."""
    _require_admin(authorization, x_admin_token)
    try:
        db = get_db()
        col = db.collection("datasets")
        target = col.document(dataset_id).get()
        if not getattr(target, "exists", False):
            raise HTTPException(status_code=404, detail="Dataset not found.")
        for doc in col.stream():
            data = doc.to_dict() or {}
            doc_ref = col.document(doc.id)
            doc_ref.update({"is_active": doc.id == dataset_id, "updated_at": _now_iso()})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to activate dataset %s.", dataset_id)
        raise HTTPException(status_code=500, detail="Could not activate dataset.")
    return DatasetMutationResponse(
        message="Dataset marked as active for the next training run.", dataset_id=dataset_id
    )


@router.delete("/{dataset_id}", response_model=DatasetMutationResponse, status_code=200)
def delete_dataset(
    dataset_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> DatasetMutationResponse:
    """Deletes a dataset's metadata and its on-disk CSV file."""
    _require_admin(authorization, x_admin_token)
    try:
        db = get_db()
        doc_ref = db.collection("datasets").document(dataset_id)
        snapshot = doc_ref.get()
        if not getattr(snapshot, "exists", False):
            raise HTTPException(status_code=404, detail="Dataset not found.")
        data = snapshot.to_dict() or {}
        doc_ref.delete()
        storage_path = data.get("storage_path", "")
        if storage_path and os.path.exists(storage_path):
            try:
                os.remove(storage_path)
            except OSError:
                logger.warning("Could not delete file %s.", storage_path)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete dataset %s.", dataset_id)
        raise HTTPException(status_code=500, detail="Could not delete dataset.")
    return DatasetMutationResponse(message="Dataset deleted.", dataset_id=dataset_id)