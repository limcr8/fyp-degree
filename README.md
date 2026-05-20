# Fake News Detection

An Explainable AI fake news detection system for English cryptocurrency and financial news. The project uses a React/Vite frontend and a FastAPI backend. The backend is being developed in stages.

## Current Stage

The staged backend currently includes:

* `GET /health`
* `POST /analyze`
* Pydantic request/response schemas
* Frontend-compatible response shape
* Stage 4 RoBERTa inference service using Hugging Face `transformers`
* Stage 2 topic verification with spaCy NER and Google CSE support
* Stage 3 integrity proof with IPFS pinning and EVM testnet anchoring support
* Local deterministic fallback logic when RoBERTa is not configured
* Placeholder SHAP-style attribution until the SHAP stage is implemented
* React frontend integration with the FastAPI `/analyze` endpoint

## Prerequisites

* Python 3.9+
* Node.js

## Backend Setup

Go to the backend folder:

```powershell
cd backend
```

Create and activate a Python virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

Install backend dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install the spaCy English model for topic extraction:

```powershell
python -m spacy download en_core_web_sm
```

Create backend environment settings:

```powershell
Copy-Item .env.example .env
```

For real RoBERTa inference, fill this value in `backend/.env`:

```text
ROBERTA_MODEL_NAME_OR_PATH=
```

This can be either a local fine-tuned checkpoint path or a Hugging Face model ID. If it is empty, the backend keeps running with fallback linguistic logic.

For real Google topic verification, fill these values in `backend/.env`:

```text
GOOGLE_API_KEY=
GOOGLE_CSE_ID=
```

For real integrity proof creation, also fill these values in `backend/.env`:

```text
IPFS_API_URL=
IPFS_API_KEY=
WEB3_PROVIDER_URL=
WEB3_PRIVATE_KEY=
WEB3_CHAIN_ID=
PROOF_CONTRACT_ADDRESS=
```

`PROOF_CONTRACT_ADDRESS` is optional. If it is empty, the backend anchors proof data in a zero-value transaction sent to the signer address.

Start the FastAPI backend:

```powershell
uvicorn app.main:app --reload --port 8000
```

Backend URLs:

* API root/docs: http://localhost:8000/docs
* Health check: http://localhost:8000/health
* Analyze endpoint: http://localhost:8000/analyze

Example `/analyze` request:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/analyze" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"text":"Bitcoin rises after confirmation from financial regulators."}'
```

## Frontend Setup

Open a second terminal and go to the frontend folder:

```powershell
cd frontend
```

Install frontend dependencies:

```powershell
npm install
```

Create frontend environment settings:

```powershell
Copy-Item .env.example .env
```

The default frontend API target is:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Start the React/Vite frontend:

```powershell
npm run dev
```

Frontend URL:

* http://localhost:3000

## Running Tests

Run the backend test suite:

```powershell
cd backend
python -m pytest tests/ -v
```

## Development Notes

Run the backend and frontend in separate terminals:

1. Terminal 1: `cd backend`, then `uvicorn app.main:app --reload --port 8000`
2. Terminal 2: `cd frontend`, then `npm run dev`

The backend already allows CORS from `http://localhost:3000` and `http://127.0.0.1:3000`.
