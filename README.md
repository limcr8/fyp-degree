# Explainable AI (XAI) Fake News Detection System

An end-to-end Explainable AI (XAI) fake news detection and verification platform specifically designed for English cryptocurrency and financial news. The system combines deep learning-based classification, local token-level explainability, external web cross-referencing, decentralized storage, and blockchain anchoring.

The project consists of three main components:
1. **FastAPI Backend**: Handles deep learning inference (RoBERTa), explainability attribution (SHAP), topic cross-referencing (spaCy + Google CSE / RSS), report persistence (IPFS), and cryptographic anchoring (Ethereum Sepolia).
2. **React / Vite Frontend**: Provides a premium user dashboard, interactive SHAP visualization, article extraction, verified source tables, blockchain verification tools, and a 30-day credibility metrics dashboard.
3. **Chrome Extension**: Allows users to highlight or paste text directly from any web page, runs real-time checks, and provides options for API key or login credentials, along with a direct link to the web portal.

---

## Core Features

- **Verdicts**: Classifies news as either **Real**, **Fake**, or **Uncertain** (all likely subcategories normalized for clean reporting).
- **Explainability (XAI)**: Generates precise token-level attribution scores using SHAP values to visualize exactly which keywords led to a particular verdict.
- **Automated Verification**: Uses Named Entity Extraction (spaCy) to search Google CSE and RSS for matching consensus or refute signals from authoritative domains.
- **Blockchain Proofs**: Automatically generates cryptographic report hashes, pins the JSON payload to IPFS, and publishes a transaction anchoring the proof hash on the Ethereum Sepolia Testnet.
- **Admin Dashboard**: Offers administrator views containing user/feedback lists and a 30-day bar chart showing daily aggregated totals of **Real**, **Fake**, and **Uncertain** articles pulled directly from Firebase.
- **Chrome Extension**: Lightweight companion that integrates highlighting capabilities, settings (API Key / Password login), and a redirect link to the main portal.

---

## Prerequisites

- **Python 3.9+** (Python 3.12 recommended)
- **Node.js 18+** & **npm**
- **Firebase Project** (Firestore and Firebase Auth configured)
- **Google Cloud API Key** & **Programmable Search Engine (CSE) ID**
- **Pinata Account** (for IPFS Pinning)
- **Ethereum Sepolia Wallet** (MetaMask, RPC Node Provider e.g. Alchemy)

---

## Setup & Local Development

### 1. Backend Setup

Navigate to the `backend` folder:
```bash
cd backend
```

Create a virtual environment and activate it:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Install backend dependencies:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Create your configuration environment file:
```bash
# Windows
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

#### Configure `backend/.env`
Fill out the required variables:
```env
# Google Programmable Search (Used for topic verification)
GOOGLE_API_KEY=your-google-cloud-api-key
GOOGLE_CSE_ID=your-search-engine-id

# LLM fallback / Attribution (Optional alternative NLP verifications)
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key

# Classifier (Path to local RoBERTa fine-tuned checkpoint or Hugging Face model id)
ROBERTA_MODEL_NAME_OR_PATH=./checkpoints/roberta-fake-news-v2

# IPFS Pinning
IPFS_API_URL=https://api.pinata.cloud/pinning/pinJSONToIPFS
IPFS_API_KEY=your-pinata-jwt-token

# Ethereum Sepolia Anchoring
WEB3_PROVIDER_URL=https://eth-sepolia.g.alchemy.com/v2/your-alchemy-api-key
WEB3_PRIVATE_KEY=your-wallet-private-key-with-sepolia-eth
WEB3_CHAIN_ID=11155111
PROOF_CONTRACT_ADDRESS=0xD7ACd2a9FD159E69Bb102A1ca21C9a3e3A5F771B

# Admins & Authentication
ADMIN_TOKEN=your-admin-token
ADMIN_EMAILS=admin@example.com

# Alternate Search instances
SEARXNG_URL=https://searx.oloke.xyz/

# Firebase configuration (credentials json file path or string json)
FIREBASE_CREDENTIALS_PATH=service-account.json
# OR FIREBASE_SERVICE_ACCOUNT='{"project_id": "...", ...}'
```

To run the local server in development mode:
```bash
uvicorn app.main:app --reload --port 8000
```
- API Documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

#### Fine-Tuning RoBERTa
To fine-tune a model locally using your own CSV dataset:
```bash
python -m training.train_roberta \
  --dataset data/training/news_dataset.csv \
  --output-dir checkpoints/roberta-fake-news-v2 \
  --base-model roberta-base
```

### 2. Frontend Setup

Navigate to the `frontend` folder:
```bash
cd frontend
```

Install dependencies:
```bash
npm install
```

Configure environment file:
```bash
# Windows
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

#### Configure `frontend/.env`
Fill out the required variables:
```env
VITE_API_BASE_URL=http://localhost:8000

# Firebase SDK keys for Web clients (from Firebase Console Settings)
VITE_FIREBASE_API_KEY=your-firebase-web-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id

# Token used to authenticate Admin analytics pages
VITE_ADMIN_TOKEN=your-admin-token
```

Start the Vite dev server:
```bash
npm run dev
```
Open: http://localhost:3000

### 3. Chrome Extension Setup

1. Open Google Chrome.
2. Navigate to `chrome://extensions/`.
3. Enable **Developer mode** (toggle in the top-right corner).
4. Click **Load unpacked** in the top-left.
5. Select the `chrome-extension` directory in this project workspace.
6. Open the Extension settings page to save your Login or API Key.
7. Click the **Visit Full Service Web Portal ➜** redirect link to jump to the web portal UI anytime.

---

## Running Test Suite

Verify your backend logic, models, and API endpoints using `pytest`:
```bash
cd backend
$env:PYTHONPATH="."
python -m pytest tests/ -v
```

---

## Production Deployment Guide

### Backend Deployment (FastAPI)

1. **Production Server Command**:
   In production, do not run with `--reload`. Run Uvicorn or Gunicorn with multiple worker processes:
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```
2. **Dockerization**:
   Here is a standard Dockerfile configuration to deploy the backend on cloud services (e.g. Google Cloud Run, AWS ECS, Render):
   ```dockerfile
   FROM python:3.12-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt && \
       python -m spacy download en_core_web_sm
   COPY . .
   EXPOSE 8000
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```
3. **Environment Secrets**:
   Provide production-level environment variables to your deployment engine. Use secure secret management (e.g., Cloud Secret Manager, AWS Parameter Store) instead of plain text `.env` files.
4. **Firebase Configuration**:
   Ensure your Firebase Service Account JSON is set via `FIREBASE_SERVICE_ACCOUNT` as an environment variable in production.

### Frontend Deployment (Vite)

1. **Build Step**:
   Compile the React frontend to highly optimized static assets:
   ```bash
   cd frontend
   npm run build
   ```
   This generates a production-ready folder called `dist/`.
2. **Hosting**:
   Deploy the contents of the `dist/` directory to static hosting services:
   - **Firebase Hosting**: Run `firebase init hosting` followed by `firebase deploy`.
   - **Netlify / Vercel**: Connect your repository directly for automated CI/CD builds.
3. **Routing**:
   Since React uses client-side routing, ensure your hosting server redirects all requests to `index.html` (e.g., configure `rewrites` to `"/index.html"` in `firebase.json` or create a `_redirects` file for Netlify).

### Chrome Extension Deployment

1. **Configure Production API Target**:
   Update `chrome-extension/popup.js` and `chrome-extension/options.js` to target your deployed production URL instead of `http://localhost:8000`:
   ```javascript
   const API_BASE = "https://your-deployed-backend-domain.com";
   ```
2. **Deploy Redirect link**:
   Update the web portal target in `chrome-extension/popup.js` and `chrome-extension/options.js`:
   ```javascript
   chrome.tabs.create({ url: "https://your-deployed-frontend-domain.com" });
   ```
3. **Publish to Web Store**:
   - Zip the `chrome-extension` folder.
   - Go to the [Chrome Web Store Developer Console](https://developer.chrome.com/docs/webstore/publish/).
   - Upload the zip file and complete store listing information.
