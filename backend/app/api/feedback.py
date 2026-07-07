import datetime
import logging
import uuid

from fastapi import APIRouter

from app.core.firebase_client import get_db
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    feedback_id = f"fb-{uuid.uuid4().hex[:12]}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = {
        "feedback_id": feedback_id,
        "article_id": request.article_id,
        "feedback_type": request.feedback_type,
        "message": request.message,
        "user_email": request.user_email,
        "status": "open",
        "created_at": timestamp,
    }
    try:
        db = get_db()
        db.collection("feedback").document(feedback_id).set(record)
        logger.info("Stored feedback %s for article %s.", feedback_id, request.article_id)
    except Exception:
        logger.exception("Failed to persist feedback %s.", feedback_id)
        return FeedbackResponse(feedback_id=feedback_id, status="error", message="Could not persist.")
    return FeedbackResponse(feedback_id=feedback_id, status="submitted", message="Submitted successfully.")


@router.get("/feedback")
def list_feedback() -> dict:
    try:
        db = get_db()
        docs = db.collection("feedback").stream()
        items = [doc.to_dict() for doc in docs if hasattr(doc, "to_dict") and doc.to_dict()]
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"count": len(items), "feedback": items}
    except Exception:
        logger.exception("Failed to retrieve feedback list.")
        return {"count": 0, "feedback": []}