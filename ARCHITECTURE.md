```markdown
# System Architecture: Fake News Detection

## 1. Project Brief
The **Fake News Detection** project is an Explainable AI system with Topic-Based Verification. Designed specifically for the cryptocurrency and financial domain (English-only text), it moves beyond traditional "black box" classifiers. It provides a dual-layer credibility assessment:
1. **Linguistic Risk Analysis:** A fine-tuned RoBERTa model assesses text for sensationalism and manipulation, explained visually via SHAP (SHapley Additive exPlanations).
2. **Topic-Based Verification:** Named Entity Recognition (NER) extracts core subjects to cross-reference against a whitelist of authoritative news domains via the Google Programmable Search Engine API.

---

## 2. Tech Stack
* **Frontend:** Streamlit (Python)
* **Backend API:** FastAPI (Python 3.9+)
* **Machine Learning:** PyTorch, Hugging Face `transformers` (RoBERTa)
* **Explainable AI (XAI):** `shap`
* **NLP / Extraction:** `spaCy` (NER), `nltk`
* **External APIs:** Google Programmable Search Engine API
* **Testing:** `pytest`

---

## 3. Project Structure & Module Organization
The repository follows a modular, domain-driven design separating the AI logic, external API integrations, backend routing, and frontend UI. You must maintain this exact directory structure.
```text
fake_news_detection/
├── .github/workflows/       # CI/CD pipelines
├── app/                     # Backend API (FastAPI)
│   ├── api/                 # API routers and endpoints
│   ├── core/                # Config, security, and environment variables
│   ├── schemas/             # Pydantic models for request/response validation
│   └── main.py              # FastAPI application entry point
├── models/                  # AI and Verification Logic
│   ├── linguistic.py        # RoBERTa inference and tokenization
│   ├── explainer.py         # SHAP integration and HTML rendering
│   └── verification.py      # spaCy NER and Google Search API logic
├── ui/                      # Frontend (Streamlit)
│   ├── components/          # Reusable Streamlit UI widgets
│   └── app.py               # Main Streamlit dashboard
├── tests/                   # Pytest test suite
│   ├── test_api/
│   └── test_models/
├── data/                    # Local caching and datasets (git-ignored)
├── requirements.txt         # Python dependencies
├── AGENTS.md                # AI/Developer workflow guidelines
└── ARCHITECTURE.md          # System design (this file)

4. System Data Flow & Subsystems
When writing integration code, follow this exact data flow:
Input: User submits a text snippet via the Streamlit UI.
Routing: UI sends a POST request to the FastAPI /analyze endpoint using Pydantic validation.
Parallel Processing:
Subsystem A (Linguistic + XAI): Text is tokenized -> passed to RoBERTa -> generates Risk Score -> triggers SHAP explainer -> generates localized HTML Force Plot.
Subsystem B (Verification): Text is passed to spaCy -> ORG, GPE, and PERSON entities extracted -> formatted into a query. The Google API fetches corroborating/debunking links.
Aggregation: FastAPI aggregates the Risk Score, SHAP HTML, and Verification Links into a single JSON response.
Output: Streamlit parses the JSON and renders the final dashboard interface for the user.