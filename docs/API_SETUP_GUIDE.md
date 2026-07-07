# API Setup Guide

This project can run in fallback mode without external credentials, but the full feature set needs a few services configured in `backend/.env`.

## What Works After Adding Keys?

After all keys are configured and a fine-tuned RoBERTa checkpoint exists, the web app can run end-to-end:

1. React sends the article text to FastAPI `/analyze`.
2. RoBERTa produces the linguistic verdict and confidence.
3. SHAP explains the RoBERTa prediction.
4. spaCy extracts topics.
5. Google CSE searches authoritative domains.
6. The report is pinned to IPFS.
7. The IPFS hash/report hash is anchored on an EVM testnet.
8. React renders the verdict, sources, SHAP values, and proof.

If a service is missing, the backend currently falls back safely for that part instead of crashing.

## Backend Environment Variables

Create `backend/.env` from `backend/.env.example`.

```text
GOOGLE_API_KEY=
GOOGLE_CSE_ID=
ROBERTA_MODEL_NAME_OR_PATH=
IPFS_API_URL=
IPFS_API_KEY=
WEB3_PROVIDER_URL=
WEB3_PRIVATE_KEY=
WEB3_CHAIN_ID=0
PROOF_CONTRACT_ADDRESS=
```

## RoBERTa Checkpoint

`ROBERTA_MODEL_NAME_OR_PATH` points to either:

* a local fine-tuned checkpoint folder, recommended for this FYP project
* a Hugging Face model ID

Example local value:

```text
ROBERTA_MODEL_NAME_OR_PATH=./checkpoints/roberta-fake-news
```

Train a checkpoint:

```powershell
cd backend
python -m training.train_roberta `
  --dataset data/training/news_dataset.csv `
  --output-dir checkpoints/roberta-fake-news `
  --base-model roberta-base `
  --text-column text `
  --label-column label
```

Dataset CSV format:

```csv
text,label
"Bitcoin ETF approved after regulator confirmation",real
"Secret token guaranteed to 100x overnight",fake
```

Supported label values:

```text
REAL: real, true, credible, reliable, 0
FAKE: fake, false, misinformation, unreliable, 1
```

## Google Programmable Search

Used by topic verification.

You need:

```text
GOOGLE_API_KEY
GOOGLE_CSE_ID
```

Where to get it:

* Google Programmable Search Engine: https://programmablesearchengine.google.com/
* Google Custom Search JSON API docs: https://developers.google.com/custom-search/v1/overview
* Google Cloud API credentials: https://console.cloud.google.com/apis/credentials

High-level steps:

1. Create a Google Cloud project.
2. Enable the Custom Search JSON API.
3. Create an API key.
4. Create a Programmable Search Engine.
5. Copy the Search Engine ID into `GOOGLE_CSE_ID`.
6. Configure the search engine to search the web or restrict it to authoritative domains.

## IPFS Pinning

Used to store the completed verification report.

Recommended beginner option: Pinata.

You need:

```text
IPFS_API_URL=https://api.pinata.cloud/pinning/pinJSONToIPFS
IPFS_API_KEY=<Pinata JWT>
```

Where to get it:

* Pinata docs: https://docs.pinata.cloud/
* Generate Pinata API key docs: https://docs.pinata.cloud/api-reference/endpoint/ipfs/generate-pinata-api-key
* IPFS pinning overview: https://docs.ipfs.tech/quickstart/pin/

Use a Pinata JWT as `IPFS_API_KEY`. The backend sends it as:

```text
Authorization: Bearer <token>
```

## Blockchain Testnet

Used to anchor the IPFS/report proof.

Recommended beginner stack:

* Wallet: MetaMask
* Testnet: Ethereum Sepolia
* RPC provider: Alchemy

You need:

```text
WEB3_PROVIDER_URL=https://eth-sepolia.g.alchemy.com/v2/<api-key>
WEB3_PRIVATE_KEY=<testnet-wallet-private-key>
WEB3_CHAIN_ID=11155111
PROOF_CONTRACT_ADDRESS=
```

Where to get it:

* MetaMask wallet setup: https://support.metamask.io/start/getting-started-with-metamask/
* Alchemy getting started: https://www.alchemy.com/docs/get-started
* Alchemy Sepolia RPC URL: https://www.alchemy.com/rpc/ethereum-sepolia
* Sepolia faucet from Alchemy: https://www.alchemy.com/faucets/ethereum-sepolia

High-level steps:

1. Create a MetaMask wallet dedicated only to this project.
2. Switch MetaMask to Sepolia testnet.
3. Get Sepolia test ETH from a faucet.
4. Create an Alchemy app for Ethereum Sepolia.
5. Copy the Sepolia HTTPS RPC URL into `WEB3_PROVIDER_URL`.
6. Export the private key for the test wallet and put it in `WEB3_PRIVATE_KEY`.
7. Set `WEB3_CHAIN_ID=11155111`.

Security rule:

Never use a wallet with real funds. Use a fresh testnet-only wallet.

## Proof Contract Address

`PROOF_CONTRACT_ADDRESS` is optional right now.

If empty, the backend sends a zero-value transaction to the signer address with proof data in the transaction `data` field.

Later, you can deploy a small smart contract and set:

```text
PROOF_CONTRACT_ADDRESS=<deployed-testnet-contract-address>
```

That would be a good future improvement, but it is not required for the current testnet proof flow.

## Frontend Environment

Create `frontend/.env` from `frontend/.env.example`.

```text
VITE_API_BASE_URL=http://localhost:8000
```

## Local Run Checklist

Terminal 1:

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```powershell
cd frontend
npm.cmd run dev
```

Open:

```text
http://localhost:3000
```
