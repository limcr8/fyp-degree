import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

# Global db client
_db = None

# ---------------------------------------------------------------------------
# File-backed local Firestore emulator
# ---------------------------------------------------------------------------

_DATA_ROOT = os.path.join("data")


class LocalFileDocument:
    """
    Emulates a Firestore DocumentReference that persists to
    data/{collection}/{doc_id}.json on disk.
    """

    def __init__(self, collection_name: str, doc_id: str, base_dir: str = None):
        self.id = doc_id
        self._collection_name = collection_name
        self._dir = base_dir or os.path.join(_DATA_ROOT, collection_name)
        self._dir = base_dir or os.path.join(_DATA_ROOT, collection_name)
        self._path = os.path.join(self._dir, f"{doc_id}.json")

    def collection(self, name: str) -> "LocalFileCollection":
        sub_dir = os.path.join(self._dir, self.id, name)
        return LocalFileCollection(name, base_dir=sub_dir)

    # ---- internal helpers --------------------------------------------------

    def _read(self) -> dict | None:
        if not os.path.exists(self._path):
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            logger.warning("Corrupted local doc %s — treating as missing.", self._path)
            return None

    def _write(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    # ---- Firestore-compatible API ------------------------------------------

    def get(self) -> "LocalFileDocument":
        """Returns self (plays double role as DocumentSnapshot)."""
        return self

    @property
    def exists(self) -> bool:
        return os.path.exists(self._path)

    def to_dict(self) -> dict:
        return self._read() or {}

    def set(self, data: dict, merge: bool = False) -> None:
        if merge:
            existing = self._read() or {}
            existing.update(data)
            self._write(existing)
        else:
            self._write(dict(data))

    def update(self, data: dict) -> None:
        existing = self._read() or {}
        existing.update(data)
        self._write(existing)

    def delete(self) -> None:
        if os.path.exists(self._path):
            os.remove(self._path)


class LocalFileCollection:
    """
    Emulates a Firestore CollectionReference backed by a local directory.
    """

    def __init__(self, name: str, base_dir: str = None):
        self.name = name
        self._dir = base_dir or os.path.join(_DATA_ROOT, name)

    def document(self, doc_id: str | None = None) -> LocalFileDocument:
        if not doc_id:
            import uuid
            doc_id = str(uuid.uuid4())
        return LocalFileDocument(self.name, doc_id, base_dir=self._dir)

    def stream(self) -> list[LocalFileDocument]:
        """Yields all documents in the collection directory."""
        if not os.path.isdir(self._dir):
            return []
        docs = []
        for filename in os.listdir(self._dir):
            if not filename.endswith(".json"):
                continue
            doc_id = filename[:-5]  # strip .json
            docs.append(LocalFileDocument(self.name, doc_id, base_dir=self._dir))
        return docs

    def get(self) -> list[LocalFileDocument]:
        return self.stream()

    # Stub chaining methods (not filtering locally — not needed for this project)
    def limit(self, num: int) -> "LocalFileCollection":
        return self

    def offset(self, num: int) -> "LocalFileCollection":
        return self

    def order_by(self, field: str, direction=None) -> "LocalFileCollection":
        return self


class LocalFileFirestoreDb:
    """
    A file-backed Firestore emulator.  Every collection maps to a
    subdirectory under data/ and every document is a JSON file.

    This is the default backend when real Firebase credentials are absent,
    making login, user history, and the Public Portal all work correctly
    on a local development machine without any external services.
    """

    def collection(self, name: str) -> LocalFileCollection:
        return LocalFileCollection(name)


# ---------------------------------------------------------------------------
# In-memory mock — used ONLY in pytest (TESTING=true)
# ---------------------------------------------------------------------------

class MockDocument:
    def __init__(self, doc_id, collection_ref):
        self.id = doc_id
        self.collection_ref = collection_ref
        self._data = {}
        self._exists = False

    def collection(self, name):
        sub_name = f"{self.collection_ref.name}/{self.id}/{name}"
        db = self.collection_ref._db
        if sub_name not in db._collections:
            sub_col = MockCollection(sub_name)
            sub_col._db = db
            db._collections[sub_name] = sub_col
        return db._collections[sub_name]

    def get(self):
        return self

    @property
    def exists(self):
        return self._exists

    def to_dict(self):
        return dict(self._data)

    def set(self, data, merge=False):
        if merge:
            self._data.update(data)
        else:
            self._data = dict(data)
        self._exists = True

    def update(self, data):
        self._data.update(data)
        self._exists = True

    def delete(self):
        self._exists = False
        self._data = {}
        if self.id in self.collection_ref._documents:
            del self.collection_ref._documents[self.id]


class MockCollection:
    def __init__(self, name):
        self.name = name
        self._documents = {}
        self._db = None

    def document(self, doc_id=None):
        import uuid
        if not doc_id:
            doc_id = str(uuid.uuid4())
        if doc_id not in self._documents:
            self._documents[doc_id] = MockDocument(doc_id, self)
        return self._documents[doc_id]

    def stream(self):
        return list(self._documents.values())

    def get(self):
        return self.stream()

    def limit(self, num):
        return self

    def offset(self, num):
        return self

    def order_by(self, field, direction=None):
        return self


class MockFirestoreDb:
    """Pure in-memory Firestore mock — used only for unit tests."""

    def __init__(self):
        self._collections = {}

    def collection(self, name):
        if name not in self._collections:
            col = MockCollection(name)
            col._db = self
            self._collections[name] = col
        return self._collections[name]


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_firebase():
    global _db
    if _db is not None:
        return _db

    # Check if already initialized in another module
    if firebase_admin._apps:
        try:
            _db = firestore.client()
            return _db
        except Exception as e:
            logger.warning(
                "Firebase default app already exists but firestore.client() failed: %s. "
                "Falling back to LocalFileFirestoreDb.", e
            )
            _db = LocalFileFirestoreDb()
            return _db

    # Unit-test isolation — pure in-memory mock, no disk I/O
    if os.getenv("TESTING") == "true":
        logger.info("TESTING=true — using in-memory MockFirestoreDb.")
        _db = MockFirestoreDb()
        return _db

    cred = None
    use_local = False

    # 1. Try JSON string from environment variable
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if service_account_json:
        try:
            logger.info("Parsing FIREBASE_SERVICE_ACCOUNT credentials from env variable.")
            cred_info = json.loads(service_account_json)
            # Detect placeholder credentials
            if cred_info.get("project_id") != "..." and cred_info.get("private_key"):
                cred = credentials.Certificate(cred_info)
            else:
                logger.warning(
                    "FIREBASE_SERVICE_ACCOUNT contains placeholder values. "
                    "Falling back to LocalFileFirestoreDb."
                )
                use_local = True
        except Exception as e:
            logger.error("Failed to parse FIREBASE_SERVICE_ACCOUNT JSON: %s", e)

    # 2. Try file path from environment variable
    if cred is None and not use_local:
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if cred_path and os.path.exists(cred_path):
            try:
                logger.info("Loading credentials from path: %s", cred_path)
                cred = credentials.Certificate(cred_path)
            except Exception as e:
                logger.error("Failed to load credentials from file %s: %s", cred_path, e)

    # 3. Try to locate service-account.json in common locations
    if cred is None and not use_local:
        default_paths = [
            "service-account.json",
            "backend/service-account.json",
            "app/service-account.json",
        ]
        for path in default_paths:
            if os.path.exists(path):
                try:
                    logger.info("Loading credentials from default path: %s", path)
                    cred = credentials.Certificate(path)
                    break
                except Exception:
                    pass

    # 4. No real credentials — use file-backed local emulator
    is_gcp = any(
        os.getenv(var)
        for var in ["GAE_ENV", "K_SERVICE", "GOOGLE_CLOUD_PROJECT", "CLOUD_RUN_JOB"]
    )
    if use_local or (not cred and not is_gcp):
        logger.info(
            "No Firebase credentials found — using LocalFileFirestoreDb "
            "(data persisted to data/ directory)."
        )
        _db = LocalFileFirestoreDb()
        return _db

    # 5. Initialize real Firebase Admin SDK
    try:
        if cred:
            firebase_admin.initialize_app(cred)
        else:
            logger.info("Initializing Firebase SDK using Application Default Credentials.")
            firebase_admin.initialize_app()
        _db = firestore.client()
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.warning(
            "Could not initialize Firebase Admin SDK: %s. "
            "Falling back to LocalFileFirestoreDb.", e
        )
        _db = LocalFileFirestoreDb()

    return _db


def get_db():
    global _db
    if _db is None:
        init_firebase()
    return _db
