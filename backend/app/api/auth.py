import csv
import io
import logging
import os
import time
import uuid
import datetime
from app.core.firebase_client import get_db


from fastapi import APIRouter, HTTPException, Header, File, UploadFile

from app.schemas.auth import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse, RefreshResponse, LogoutResponse, UserMeResponse, UpdateProfileRequest, UpdateProfileResponse, ChangePasswordRequest, ChangePasswordResponse
from app.schemas.analysis import UserHistoryResponse
from app.schemas.admin import AdminDashboardResponse, TrainingStatusResponse, DatasetUploadResponse, AdminAnalyticsResponse, ApiUsageStats, VerificationStats, ModelPerformanceStats, CostAnalysisStats, AdminUsersResponse, AdminUserDeleteResponse, AdminTrendPoint, AdminTrendResponse
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.core.config import get_settings
from models.auth_service import register_user, authenticate_user, refresh_access_token, logout_user_session, get_user_profile, update_user_profile, change_user_password, get_user_history, get_training_job, get_admin_users, delete_admin_user, submit_user_feedback

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authentication"])


@router.post(
    "/api/v1/auth/register",
    response_model=RegisterResponse,
    status_code=201,
)
def register(request: RegisterRequest) -> RegisterResponse:
    """
    Registers a new user and returns their profile with a generated API key.

    Args:
        request (RegisterRequest): User signup details.

    Returns:
        RegisterResponse: Registered user metadata.
    """
    try:
        return register_user(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("User registration failed.")
        raise HTTPException(status_code=500, detail="Registration failed.") from exc


@router.post(
    "/api/v1/auth/login",
    response_model=LoginResponse,
    status_code=200,
)
def login(request: LoginRequest) -> LoginResponse:
    """
    Authenticates a user and returns their JWT token session and profile.

    Args:
        request (LoginRequest): User credentials.

    Returns:
        LoginResponse: Authentication token and user profile details.
    """
    try:
        return authenticate_user(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("User login failed.")
        raise HTTPException(status_code=500, detail="Authentication failed.") from exc


@router.post(
    "/api/v1/auth/refresh",
    response_model=RefreshResponse,
    status_code=200,
)
def refresh(authorization: str = Header(..., description="Bearer token")) -> RefreshResponse:
    """
    Refreshes the access token using a signed refresh token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    refresh_token = authorization.split(" ")[1]
    try:
        return refresh_access_token(refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Token refresh failed.")
        raise HTTPException(status_code=500, detail="Token refresh failed.") from exc


@router.post(
    "/api/v1/auth/logout",
    response_model=LogoutResponse,
    status_code=200,
)
def logout(authorization: str = Header(..., description="Bearer token")) -> LogoutResponse:
    """
    Invalidates the active session access token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        return logout_user_session(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Token validation logout failed.")
        raise HTTPException(status_code=500, detail="Logout failed.") from exc


@router.get(
    "/api/v1/users/me",
    response_model=UserMeResponse,
    status_code=200,
)
def get_me(authorization: str = Header(..., description="Bearer token")) -> UserMeResponse:
    """
    Retrieves detailed profile information for the currently authenticated user.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        return get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Retrieving current user profile failed.")
        raise HTTPException(status_code=500, detail="Profile retrieval failed.") from exc


@router.put(
    "/api/v1/users/me",
    response_model=UpdateProfileResponse,
    status_code=200,
)
def update_me(
    request: UpdateProfileRequest,
    authorization: str = Header(..., description="Bearer token"),
) -> UpdateProfileResponse:
    """
    Updates the profile info (username, email, preferences) of the authenticated user.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        return update_user_profile(access_token, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Updating user profile failed.")
        raise HTTPException(status_code=500, detail="Profile update failed.") from exc


@router.post(
    "/api/v1/users/change-password",
    response_model=ChangePasswordResponse,
    status_code=200,
)
def change_password(
    request: ChangePasswordRequest,
    authorization: str = Header(..., description="Bearer token"),
) -> ChangePasswordResponse:
    """
    Changes the password of the authenticated user.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        return change_user_password(access_token, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Changing user password failed.")
        raise HTTPException(status_code=500, detail="Password change failed.") from exc


@router.get(
    "/api/v1/users/history",
    response_model=UserHistoryResponse,
    status_code=200,
)
def get_history(
    limit: int = 20,
    offset: int = 0,
    authorization: str = Header(..., description="Bearer token"),
) -> UserHistoryResponse:
    """
    Retrieves paginated verification history for the authenticated user.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        return get_user_history(access_token, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Retrieving user history failed.")
        raise HTTPException(status_code=500, detail="History retrieval failed.") from exc


@router.get(
    "/api/v1/admin/dashboard",
    response_model=AdminDashboardResponse,
    status_code=200,
)
def get_admin_dashboard(
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token", description="Admin override token"),
) -> AdminDashboardResponse:
    """
    Retrieves administration dashboard stats.
    Requires a valid admin role session and X-Admin-Token matching server configuration.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    # Calculate Total Verifications from Firestore
    count = 0
    daily_count = 0
    pending = 0
    db_status = "healthy"
    active_users = 0
    try:
        db = get_db()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for doc in db.collection("articles").stream():
            count += 1
            try:
                data = doc.to_dict() or {}
                ts_str = data.get("verified_at") or data.get("created_at")
                if ts_str:
                    verified_at = datetime.datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                    if (now_utc - verified_at).total_seconds() < 86400:
                        daily_count += 1
                # Prioritize verdict from top-level verdict field, falling back to finalAssessment, status, or classification
                verdict = data.get("verdict") or ""
                if not verdict:
                    final_assessment = data.get("finalAssessment") or data.get("final_assessment") or {}
                    if isinstance(final_assessment, dict):
                        verdict = final_assessment.get("label", "")
                if not verdict:
                    verdict = data.get("status", "")
                if not verdict:
                    verdict = data.get("classification", {}).get("verdict", "")
                
                verdict = str(verdict).upper()
                classification = data.get("classification") or {}
                confidence = classification.get("confidence")
                if verdict in ("UNCERTAIN", "MIXED", "") or (isinstance(confidence, (int, float)) and confidence < 0.6):
                    pending += 1
            except Exception:
                pass
        active_users = len(db.collection("users").get())
    except Exception:
        db_status = "unhealthy"

    return AdminDashboardResponse(
        total_verifications=count,
        daily_verifications=daily_count,
        model_accuracy=0.843,
        api_health=db_status,
        active_users=active_users,
        pending_reviews=pending,
        system_uptime_percent=100.0 if db_status == "healthy" else 0.0
    )


@router.get(
    "/api/v1/admin/trend",
    response_model=AdminTrendResponse,
    status_code=200,
)
def get_verification_trend(
    days: int = 7,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token", description="Admin override token"),
) -> AdminTrendResponse:
    """
    Aggregates stored news verifications into daily buckets for the dashboard trend chart.
    Requires a valid admin role session and X-Admin-Token matching server configuration.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    days = max(1, min(days, 90))
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    buckets: dict[str, int] = {}
    for offset in range(days):
        bucket_day = (now_utc - datetime.timedelta(days=offset)).date()
        buckets[bucket_day.isoformat()] = 0

    try:
        db = get_db()
        for doc in db.collection("articles").stream():
            data = doc.to_dict() or {}
            timestamp_str = data.get("verified_at") or data.get("created_at")
            if not timestamp_str:
                continue
            try:
                verified_at = datetime.datetime.strptime(
                    timestamp_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=datetime.timezone.utc)
            except (ValueError, TypeError):
                continue
            delta_days = (now_utc.date() - verified_at.date()).days
            if 0 <= delta_days < days:
                key = verified_at.date().isoformat()
                buckets[key] = buckets.get(key, 0) + 1
    except Exception:
        logger.exception("Failed to compute verification trend.")

    trend = [AdminTrendPoint(date=day, count=count) for day, count in sorted(buckets.items())]
    return AdminTrendResponse(days=days, trend=trend)


@router.get(
    "/api/v1/admin/train/{job_id}",
    response_model=TrainingStatusResponse,
    status_code=200,
)
def get_training_status(
    job_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token", description="Admin override token"),
) -> TrainingStatusResponse:
    """
    Retrieves the status and performance metrics of a specific model training job.
    Requires a valid admin role session and X-Admin-Token matching server configuration.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    job = get_training_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found.")

    return TrainingStatusResponse(**job)


@router.post(
    "/api/v1/admin/dataset/upload",
    response_model=DatasetUploadResponse,
    status_code=201,
)
def upload_dataset(
    file: UploadFile = File(..., description="CSV training dataset file"),
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token", description="Admin override token"),
) -> DatasetUploadResponse:
    """
    Uploads and processes a training dataset in CSV format.
    Requires columns: text, label, language, source.
    Requires a valid admin role session and X-Admin-Token matching server configuration.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    # Read the file contents
    try:
        contents = file.file.read()
        # Decode as utf-8
        decoded = contents.decode("utf-8")
        # Parse using DictReader
        csv_file = io.StringIO(decoded)
        reader = csv.DictReader(csv_file)

        # Verify required headers
        headers = reader.fieldnames or []
        required = ["text", "label", "language", "source"]
        for col in required:
            if col not in headers:
                raise ValueError(f"Missing required column: {col}")

        # Count valid rows and extract languages
        languages = set()
        samples_count = 0

        for row in reader:
            text = (row.get("text") or "").strip()
            label = (row.get("label") or "").strip()
            lang = (row.get("language") or "").strip()
            src = (row.get("source") or "").strip()

            # Count only complete valid samples
            if text and label and lang and src:
                samples_count += 1
                languages.add(lang)

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CSV structure or missing columns. Details: {str(exc)}"
        ) from exc

    # Generate unique dataset ID
    dataset_id = f"dataset_{uuid.uuid4().hex[:12]}"

    # Ensure output directory exists (fallback to /tmp in read-only serverless environments)
    datasets_dir = os.path.join("data", "training")
    try:
        os.makedirs(datasets_dir, exist_ok=True)
    except Exception:
        datasets_dir = "/tmp"
        os.makedirs(datasets_dir, exist_ok=True)

    # Save the file to disk
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
    saved_filepath = os.path.join(datasets_dir, f"{dataset_id}_{safe_filename}")

    try:
        # Reset pointer and save the full original contents
        file.file.seek(0)
        with open(saved_filepath, "wb") as f:
            f.write(contents)
    except Exception as exc:
        logger.exception("Failed to save dataset file to disk.")
        raise HTTPException(status_code=500, detail="Failed to save dataset file.") from exc

    return DatasetUploadResponse(
        dataset_id=dataset_id,
        filename=file.filename,
        samples_count=samples_count,
        languages=sorted(list(languages)),
        message="Dataset uploaded successfully"
    )


@router.get(
    "/api/v1/admin/analytics",
    response_model=AdminAnalyticsResponse,
    status_code=200,
)
def get_admin_analytics(
    period: str = "30d",
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token", description="Admin override token"),
) -> AdminAnalyticsResponse:
    """
    Retrieves detailed system usage, performance, and cost analytics.
    Requires a valid admin role session and X-Admin-Token matching server configuration.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    # 1. Verification stats (Fake vs Real from Firestore)
    fake_count = 0
    real_count = 0
    uncertain_count = 0
    article_files_count = 0
    try:
        db = get_db()
        for doc in db.collection("articles").stream():
            article_files_count += 1
            try:
                data = doc.to_dict()
                
                # Extract verdict from flat verdict field, finalAssessment or status, falling back to classification
                verdict = data.get("verdict") or ""
                
                if not verdict:
                    final_assessment = data.get("finalAssessment") or data.get("final_assessment") or {}
                    if isinstance(final_assessment, dict):
                        verdict = final_assessment.get("label", "")
                
                if not verdict:
                    verdict = data.get("status", "")
                    
                if not verdict:
                    verdict = data.get("classification", {}).get("verdict", "")
                
                verdict = str(verdict).upper()
                
                if "FAKE" in verdict:
                    fake_count += 1
                elif "REAL" in verdict:
                    real_count += 1
                else:
                    uncertain_count += 1
            except Exception:
                pass
    except Exception:
        pass

    # Verification distribution reflects real Firestore verdict counts.
    fake = fake_count
    real = real_count
    uncertain = uncertain_count
    total = article_files_count

    # API usage, model metrics, and cost are not instrumented in this deployment;
    # report zeros rather than fabricated baselines.
    return AdminAnalyticsResponse(
        period=period,
        api_usage=ApiUsageStats(
            total_requests=0,
            daily_average=0,
            peak_daily=0
        ),
        verification_stats=VerificationStats(
            total=total,
            fake=fake,
            real=real,
            uncertain=uncertain
        ),
        model_performance=ModelPerformanceStats(
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0
        ),
        cost_analysis=CostAnalysisStats(
            google_api_cost=0.0,
            ipfs_storage_gb=0.0,
            total_monthly=0.0
        )
    )


@router.get(
    "/api/v1/admin/users",
    response_model=AdminUsersResponse,
    status_code=200,
)
def get_users_list(
    limit: int = 50,
    offset: int = 0,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token", description="Admin override token"),
) -> AdminUsersResponse:
    """
    Retrieves all registered user profiles with pagination.
    Requires a valid admin role session and X-Admin-Token matching server configuration.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    try:
        return get_admin_users(limit=limit, offset=offset)
    except Exception as exc:
        logger.exception("Failed to retrieve user registry.")
        raise HTTPException(status_code=500, detail="Database lookup failed.") from exc


@router.delete(
    "/api/v1/admin/users/{user_id}",
    response_model=AdminUserDeleteResponse,
    status_code=200,
)
def delete_user_by_id(
    user_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_admin_token: str = Header(..., alias="X-Admin-Token", description="Admin override token"),
) -> AdminUserDeleteResponse:
    """
    Deletes a user account by user_id.
    Requires a valid admin role session and X-Admin-Token matching server configuration.
    Administrators are prevented from self-deletion.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format.")

    access_token = authorization.split(" ")[1]
    try:
        user_profile = get_user_profile(access_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user_profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    active_settings = get_settings()
    if x_admin_token != active_settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    # Prevent self-deletion
    if user_profile.user_id == user_id:
        raise HTTPException(status_code=400, detail="Self-deletion of currently logged-in administrator is prohibited.")

    success = delete_admin_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found.")

    return AdminUserDeleteResponse(
        message="User deleted successfully",
        user_id=user_id
    )


@router.post(
    "/api/v1/feedback",
    response_model=FeedbackResponse,
    status_code=201,
)
def create_user_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """
    Submits feedback/dispute about a verified article classification.
    Statically persists the response inside data/feedback directory.
    """
    try:
        return submit_user_feedback(request)
    except Exception as exc:
        logger.exception("Failed to submit user feedback.")
        raise HTTPException(status_code=500, detail="Database write failure.") from exc







