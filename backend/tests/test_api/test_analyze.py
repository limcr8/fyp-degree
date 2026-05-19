from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    """
    Verifies that the backend exposes a lightweight health check.
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_endpoint_returns_frontend_compatible_shape() -> None:
    """
    Verifies that /analyze returns the existing React VerificationResult shape.
    """
    payload = {
        "text": (
            "Bitcoin ETF approval sends BTC higher after confirmation from "
            "multiple financial regulators."
        )
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == payload["text"]
    assert body["status"] in {"REAL", "FAKE", "UNCERTAIN"}
    assert 0 <= body["confidence"] <= 1
    assert isinstance(body["explanation"], str)
    assert isinstance(body["shapData"], list)
    assert isinstance(body["sources"], list)
    assert isinstance(body["blockchain"], dict)
    assert set(body["blockchain"]) == {
        "transactionHash",
        "blockNumber",
        "timestamp",
        "ipfsHash",
        "network",
    }


def test_analyze_endpoint_rejects_empty_text() -> None:
    """
    Verifies that empty text fails request validation.
    """
    response = client.post("/analyze", json={"text": "   "})

    assert response.status_code == 422
