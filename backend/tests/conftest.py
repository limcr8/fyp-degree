import os
import pytest

# Force TESTING environment variable to be true so firebase_client uses MockFirestoreDb
os.environ["TESTING"] = "true"

@pytest.fixture(autouse=True)
def clean_mock_firestore():
    """Clears the MockFirestoreDb collections before each test to ensure test isolation."""
    from app.core.firebase_client import get_db
    db = get_db()
    if hasattr(db, "_collections"):
        db._collections.clear()
    yield
