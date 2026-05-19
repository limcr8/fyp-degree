# System Architecture: Fake News Detection

## 1. Project Brief

The **Fake News Detection** project is an Explainable AI system with Topic-Based Verification. It is designed for English-language cryptocurrency and financial news, and moves beyond traditional black-box classification by combining four layers of evidence:

1. **Linguistic Risk Analysis:** A fine-tuned RoBERTa model assesses text for sensationalism, manipulation, and misinformation risk.
2. **Explainable AI:** SHAP explains which tokens or phrases contributed most strongly to the model verdict.
3. **Topic-Based Verification:** Named Entity Recognition (NER) extracts core subjects and cross-references them against authoritative news and institutional domains through the Google Programmable Search Engine API.
4. **Integrity Proof:** The completed verification result is pinned to IPFS and anchored on a blockchain testnet so users can verify that a report was not modified after analysis.

---

## 2. Tech Stack

* **Frontend:** React + Vite + TypeScript
* **Backend API:** FastAPI (Python 3.9+)
* **Machine Learning:** PyTorch, Hugging Face `transformers` (RoBERTa)
* **Explainable AI (XAI):** `shap`
* **NLP / Extraction:** `spaCy`, `nltk`
* **External APIs:** Google Programmable Search Engine API
* **Decentralized Storage:** IPFS-compatible pinning service
* **Blockchain:** EVM-compatible testnet using `web3.py`
* **Testing:** `pytest`

---

## 3. Project Structure & Module Organization

The repository follows a modular design that separates frontend UI, backend routing, AI logic, external API integrations, and integrity proof services.

```text
fake_news_detection/
+-- backend/                   # FastAPI backend and Python services
|   +-- app/                   # Backend API package
|   |   +-- api/               # API routers and endpoints
|   |   +-- core/              # Config, security, and environment variables
|   |   +-- schemas/           # Pydantic request/response schemas
|   |   +-- main.py            # FastAPI application entry point
|   +-- models/                # AI, verification, and proof logic
|   |   +-- linguistic.py      # RoBERTa inference and tokenization
|   |   +-- explainer.py       # SHAP explanation generation
|   |   +-- verification.py    # spaCy NER and Google Search API logic
|   |   +-- integrity_proof.py # IPFS pinning and EVM testnet anchoring
|   +-- tests/                 # Pytest test suite
|   |   +-- test_api/
|   |   +-- test_models/
|   +-- requirements.txt       # Python backend dependencies
+-- frontend/                  # React/Vite frontend
|   +-- components/            # React UI components
|   +-- services/              # Frontend API clients and shared client utilities
|   +-- App.tsx                # React application root
|   +-- package.json           # React frontend dependencies
+-- data/                      # Local datasets, caches, and training artifacts
+-- AGENTS.md                  # AI/developer workflow guidelines
+-- ARCHITECTURE.md            # System design
+-- README.md                  # Local setup and development guide
```

---

## 4. System Data Flow & Subsystems

When writing integration code, follow this data flow:

1. **Input:** The user submits a text snippet through the React frontend.
2. **Routing:** The frontend sends a `POST /analyze` request to the FastAPI backend using a typed API client.
3. **Linguistic + XAI Processing:** Text is tokenized, passed through RoBERTa, converted into a credibility verdict and confidence score, then explained with SHAP token attributions.
4. **Topic-Based Verification:** Text is passed through spaCy NER. Extracted entities are formatted into Google Programmable Search queries restricted to authoritative cryptocurrency, finance, and institutional domains.
5. **Integrity Proof:** The final report payload is canonicalized, hashed, pinned to IPFS, and anchored on an EVM-compatible testnet smart contract or transaction memo.
6. **Aggregation:** FastAPI aggregates the verdict, confidence, explanation, SHAP data, source matches, IPFS hash, transaction hash, block number, timestamp, and network name into one JSON response.
7. **Output:** The React frontend renders the verdict dashboard, feature attribution, authority matching, and integrity proof.

---

## 5. Backend API Contract

The primary endpoint is:

```text
POST /analyze
```

The response must remain compatible with the existing React `VerificationResult` shape:

```text
id
text
status
confidence
explanation
shapData
sources
blockchain
```

The backend must use Pydantic models in `backend/app/schemas/` for all request and response validation. Raw dictionaries must not be passed across API boundaries.

---

## 6. Security, Credentials, and Testing

Secrets must never be hardcoded. The backend must load credentials from environment variables or `.env` through `pydantic-settings` or `os.getenv`.

Required configurable values include:

```text
GOOGLE_API_KEY
GOOGLE_CSE_ID
ROBERTA_MODEL_NAME_OR_PATH
IPFS_API_URL
IPFS_API_KEY
WEB3_PROVIDER_URL
WEB3_PRIVATE_KEY
WEB3_CHAIN_ID
PROOF_CONTRACT_ADDRESS
```

Tests must mock:

* RoBERTa inference
* SHAP generation
* Google Programmable Search responses
* IPFS pinning
* Blockchain testnet transactions

No test may call live external APIs, spend testnet funds, or load a full deep-learning model unless explicitly marked as an integration test.
