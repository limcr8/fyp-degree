import argparse
import logging
import os
import sys
from typing import Any

logger = logging.getLogger("backfill_verdicts")


def _resolve_label(data: dict[str, Any]) -> str | None:
    """
    Extracts the authoritative verdict label from a stored document.

    Checks camelCase (finalAssessment.label) first because that is the
    canonical shape written by both the backend and frontend, then falls
    back to snake_case (final_assessment.label) for legacy records.

    Args:
        data (dict[str, Any]): The Firestore document payload.

    Returns:
        str | None: The raw label string (e.g. 'fake', 'likely_real'),
            or None if no final assessment is present.
    """
    final = data.get("finalAssessment") or data.get("final_assessment")
    if isinstance(final, dict):
        label = final.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return None


def _normalize_verdict(label: str) -> str:
    """
    Normalizes a finalAssessment label to the displayed verdict form.

    Mirrors the backend `_resolve_displayed_verdict` helper and the
    frontend display layer: uppercase with underscores replaced by spaces.

    Args:
        label (str): The raw label (e.g. 'likely_fake').

    Returns:
        str: The normalized verdict (e.g. 'LIKELY FAKE').
    """
    return label.upper().replace("_", " ")


def _backfill_collection(
    db: Any,
    collection_path: tuple[str, ...],
    dry_run: bool,
) -> tuple[int, int]:
    """
    Scans a collection and rewrites classification.verdict to match
    finalAssessment.label where they diverge.

    Args:
        db: The Firestore client (real Admin SDK, local file DB, or mock).
        collection_path (tuple[str, ...]): Path segments identifying the
            collection (e.g. ('articles',) or ('users', uid, 'history')).
        dry_run (bool): If True, only report what would change; do not write.

    Returns:
        tuple[int, int]: (scanned_count, updated_count).
    """
    col_ref = db.collection("/".join(collection_path))
    scanned = 0
    updated = 0

    try:
        docs = list(col_ref.stream())
    except Exception:
        logger.exception("Failed to stream collection %s", "/".join(collection_path))
        return scanned, updated

    for doc_snap in docs:
        scanned += 1
        data = doc_snap.to_dict() if hasattr(doc_snap, "to_dict") else {}
        if not isinstance(data, dict):
            continue

        label = _resolve_label(data)
        if not label:
            continue

        classification = data.get("classification")
        if not isinstance(classification, dict):
            continue

        current_verdict = str(classification.get("verdict", "") or "").strip()
        desired_verdict = _normalize_verdict(label)

        if current_verdict.upper() == desired_verdict:
            continue

        logger.info(
            "[%s] doc=%s | '%s' -> '%s'",
            "/".join(collection_path),
            getattr(doc_snap, "id", "?"),
            current_verdict or "(empty)",
            desired_verdict,
        )

        if dry_run:
            continue

        try:
            doc_ref = db.collection(*collection_path).document(doc_snap.id)
            doc_ref.update({"classification.verdict": desired_verdict})
            updated += 1
        except Exception:
            logger.exception(
                "Failed to update doc %s in %s",
                getattr(doc_snap, "id", "?"),
                "/".join(collection_path),
            )

    return scanned, updated


def main() -> int:
    """
    Entry point for the verdict backfill script.

    Rewrites classification.verdict on every articles document and every
    users/{uid}/history document so it matches finalAssessment.label — the
    same value the UI displays. Existing records written before the verdict
    sync fix stored the raw model verdict (e.g. UNCERTAIN) and are corrected
    here in place using a shallow merge update.

    Returns:
        int: Process exit code (0 = success, 1 = fatal error).
    """
    parser = argparse.ArgumentParser(
        description="Backfill classification.verdict from finalAssessment.label "
        "in the articles and users/*/history collections."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the changes that would be made without writing to Firestore.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.firebase_client import get_db

    db = get_db()
    logger.info(
        "Connected to Firestore (dry_run=%s). Beginning backfill...",
        args.dry_run,
    )

    total_scanned = 0
    total_updated = 0

    scanned, updated = _backfill_collection(db, ("articles",), args.dry_run)
    total_scanned += scanned
    total_updated += updated
    logger.info("articles: scanned=%d updated=%d", scanned, updated)

    try:
        user_docs = list(db.collection("users").stream())
    except Exception:
        logger.exception("Failed to stream users collection.")
        user_docs = []

    for user_doc in user_docs:
        uid = getattr(user_doc, "id", None)
        if not uid:
            continue
        scanned, updated = _backfill_collection(
            db, ("users", uid, "history"), args.dry_run
        )
        total_scanned += scanned
        total_updated += updated
        if scanned:
            logger.info(
                "users/%s/history: scanned=%d updated=%d", uid, scanned, updated
            )

    action = "would be updated" if args.dry_run else "updated"
    logger.info(
        "Backfill complete. Total: scanned=%d, %s=%d.",
        total_scanned,
        action,
        total_updated,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())