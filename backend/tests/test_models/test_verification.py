from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from app.core.config import Settings
from models.verification import (
    extract_entities,
    search_authoritative_sources,
    verify_topics,
)


def test_extract_entities_returns_supported_unique_entities() -> None:
    """
    Verifies that spaCy extraction keeps only supported entity labels.
    """
    fake_doc = SimpleNamespace(
        ents=[
            SimpleNamespace(text="Bitcoin", label_="ORG"),
            SimpleNamespace(text="SEC", label_="ORG"),
            SimpleNamespace(text="May", label_="DATE"),
            SimpleNamespace(text="Bitcoin", label_="ORG"),
        ]
    )
    fake_nlp = Mock(return_value=fake_doc)

    with patch("models.verification._load_spacy_model", return_value=fake_nlp):
        entities = extract_entities("Bitcoin rises after SEC update.")

    assert entities == ["Bitcoin", "SEC"]


def test_search_authoritative_sources_parses_google_cse_response() -> None:
    """
    Verifies Google CSE parsing without making a live API call.
    """
    settings = Settings(google_api_key="test-key", google_cse_id="test-cx")
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "https://www.googleapis.com/customsearch/v1"),
        json={
            "items": [
                {
                    "title": "Reuters confirms Bitcoin ETF update",
                    "link": "https://www.reuters.com/markets/bitcoin-etf",
                    "displayLink": "www.reuters.com",
                },
                {
                    "title": "Unknown blog post",
                    "link": "https://example.com/post",
                    "displayLink": "example.com",
                },
            ]
        },
    )

    with patch("models.verification.httpx.get", return_value=response) as mock_get:
        matches = search_authoritative_sources(["Bitcoin", "SEC"], settings)

    assert mock_get.called
    assert matches[0].name == "Reuters"
    assert matches[0].confirmed is True
    assert matches[0].url == "https://www.reuters.com/markets/bitcoin-etf"
    assert all(match.name != "example.com" for match in matches)


def test_verify_topics_returns_fallback_when_google_is_not_configured() -> None:
    """
    Verifies safe behavior when Google CSE credentials are absent.
    """
    settings = Settings(google_api_key="", google_cse_id="")

    with patch("models.verification.extract_entities", return_value=["Ethereum"]):
        matches = verify_topics("Ethereum price rises.", settings)

    assert matches
    assert all(match.confirmed is False for match in matches)
