from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from app.core.config import Settings
from app.schemas.analysis import SourceMatch
from models.verification import (
    extract_entities,
    search_authoritative_sources,
    verify_topics,
    search_google_news_rss,
    search_searxng_sources,
    verify_topics_with_context,
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
    Verifies Google CSE parsing and dynamic naming of .gov and .org domains.
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
                    "title": "FCC official statement",
                    "link": "https://www.fcc.gov/news-events",
                    "displayLink": "www.fcc.gov",
                },
                {
                    "title": "FCA UK regulatory update",
                    "link": "https://www.fca.org.uk/news/statements",
                    "displayLink": "www.fca.org.uk",
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
    assert len(matches) == 3
    assert matches[0].name == "Reuters"
    assert matches[0].confirmed is True
    assert matches[0].url == "https://www.reuters.com/markets/bitcoin-etf"
    
    assert matches[1].name == "FCC (Official .gov)"
    assert matches[1].confirmed is True
    
    assert matches[2].name == "Fca (.org)"
    assert matches[2].confirmed is True
    
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


def test_verify_topics_merges_matches_with_default_sources() -> None:
    """
    Verifies that verify_topics merges search matches with fallback sources.
    """
    settings = Settings(google_api_key="test-key", google_cse_id="test-cx")
    mock_matches = [
        SourceMatch(name="Reuters", confirmed=True, url="https://reuters.com/1"),
        SourceMatch(name="FCC (Official .gov)", confirmed=True, url="https://fcc.gov/2"),
    ]

    with patch("models.verification.extract_entities", return_value=["Bitcoin", "FCC"]), \
         patch("models.verification.search_authoritative_sources", return_value=mock_matches):
        results = verify_topics("Bitcoin regulation updates.", settings)

    assert len(results) == 5
    
    # Reuters should be merged and confirmed
    reuters = next(r for r in results if r.name == "Reuters")
    assert reuters.confirmed is True
    assert reuters.url == "https://reuters.com/1"

    # Bloomberg, CoinDesk, SEC should be present but unconfirmed
    bloomberg = next(r for r in results if r.name == "Bloomberg")
    assert bloomberg.confirmed is False
    assert bloomberg.url is None

    coindesk = next(r for r in results if r.name == "CoinDesk")
    assert coindesk.confirmed is False

    sec = next(r for r in results if r.name == "SEC")
    assert sec.confirmed is False

    # FCC should be appended as a dynamic confirmed source
    fcc = next(r for r in results if r.name == "FCC (Official .gov)")
    assert fcc.confirmed is True
    assert fcc.url == "https://fcc.gov/2"


def test_search_searxng_sources_parses_response() -> None:
    """
    Verifies that search_searxng_sources successfully queries SearXNG
    and returns mapped SourceMatch and context snippet lists.
    """
    settings = Settings(searxng_url="http://localhost:8080")
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "http://localhost:8080/search"),
        json={
            "results": [
                {
                    "title": "Reuters reports on crypto regulation",
                    "url": "https://www.reuters.com/crypto-rules",
                    "content": "Regulators are finalizing new rules...",
                },
                {
                    "title": "SEC Official Statement",
                    "url": "https://www.sec.gov/news/press-release/1",
                    "content": "The Commission announced today...",
                },
                {
                    "title": "Non-authoritative blog post",
                    "url": "https://unverifiedblog.com/123",
                    "content": "My thoughts on regulation...",
                }
            ]
        }
    )

    with patch("models.verification.httpx.get", return_value=response) as mock_get:
        matches, snippets = search_searxng_sources(["Bitcoin", "regulation"], settings)

    assert mock_get.called
    assert len(matches) == 2
    assert matches[0].name == "Reuters"
    assert matches[0].url == "https://www.reuters.com/crypto-rules"
    assert matches[1].name == "SEC"
    assert matches[1].url == "https://www.sec.gov/news/press-release/1"

    assert len(snippets) == 2
    assert snippets[0]["title"] == "Reuters reports on crypto regulation"
    assert snippets[0]["snippet"] == "Regulators are finalizing new rules..."
    assert snippets[0]["source"] == "Reuters"


def test_verify_topics_with_context_uses_google_news_rss_first() -> None:
    """
    Verifies verify_topics_with_context tries Google News RSS before SearXNG.
    When Google News RSS succeeds, SearXNG should not be called.
    """
    settings = Settings(searxng_url="http://localhost:8080")
    mock_matches = [
        SourceMatch(name="Reuters", confirmed=True, url="https://reuters.com/1"),
    ]
    mock_snippets = [{"title": "Reuters Title", "snippet": "Snippet content", "link": "https://reuters.com/1", "source": "Reuters"}]

    with patch("models.verification.extract_entities", return_value=["Bitcoin"]), \
         patch("models.verification.search_google_news_rss", return_value=(mock_matches, mock_snippets)) as mock_rss, \
         patch("models.verification.search_searxng_sources") as mock_searxng:
        sources, context = verify_topics_with_context("Bitcoin updates", settings)

    assert mock_rss.called
    assert not mock_searxng.called  # SearXNG not needed since RSS succeeded
    assert context == mock_snippets
    assert any(s.name == "Reuters" and s.confirmed for s in sources)


def test_verify_topics_with_context_uses_searxng() -> None:
    """
    Verifies verify_topics_with_context falls back to SearXNG when Google News RSS fails.
    """
    settings = Settings(searxng_url="http://localhost:8080")
    mock_matches = [
        SourceMatch(name="Reuters", confirmed=True, url="https://reuters.com/1"),
    ]
    mock_snippets = [{"title": "Reuters Title", "snippet": "Snippet content", "link": "https://reuters.com/1", "source": "Reuters"}]

    with patch("models.verification.extract_entities", return_value=["Bitcoin"]), \
         patch("models.verification.search_google_news_rss", side_effect=RuntimeError("RSS failed")), \
         patch("models.verification.search_searxng_sources", return_value=(mock_matches, mock_snippets)) as mock_searxng:
        sources, context = verify_topics_with_context("Bitcoin updates", settings)

    assert mock_searxng.called
    assert context == mock_snippets
    assert any(s.name == "Reuters" and s.confirmed for s in sources)


def test_verify_topics_with_context_falls_back_to_google_on_searxng_error() -> None:
    """
    Verifies that if both Google News RSS and SearXNG fail, the search falls back to Google CSE.
    """
    settings = Settings(
        searxng_url="http://localhost:8080",
        google_api_key="google-key",
        google_cse_id="google-cx"
    )
    mock_google_matches = [
        SourceMatch(name="Bloomberg", confirmed=True, url="https://bloomberg.com/news"),
    ]
    mock_google_snippets = [{"title": "Bloomberg News", "snippet": "Google snippet", "link": "https://bloomberg.com/news", "source": "Bloomberg"}]

    with patch("models.verification.extract_entities", return_value=["Ethereum"]), \
         patch("models.verification.search_google_news_rss", side_effect=RuntimeError("RSS failed")), \
         patch("models.verification.search_searxng_sources", side_effect=RuntimeError("SearXNG offline")), \
         patch("models.verification.search_authoritative_sources_with_context", return_value=(mock_google_matches, mock_google_snippets)) as mock_google:
        sources, context = verify_topics_with_context("Ethereum updates", settings)

    assert mock_google.called
    assert context == mock_google_snippets
    assert any(s.name == "Bloomberg" and s.confirmed for s in sources)


def test_search_google_news_rss_parses_rss_feed() -> None:
    """
    Verifies that search_google_news_rss correctly parses a Google News RSS XML response.
    """
    import xml.etree.ElementTree as ET
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Bitcoin SEC ETF - Google News</title>
    <item>
      <title>SEC Approves Bitcoin ETF - Reuters</title>
      <link>https://news.google.com/rss/articles/abc123</link>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>BlackRock Bitcoin ETF Begins Trading - CoinDesk</title>
      <link>https://news.google.com/rss/articles/def456</link>
      <source url="https://coindesk.com">CoinDesk</source>
    </item>
    <item>
      <title>Crypto News Update - UnknownBlog</title>
      <link>https://news.google.com/rss/articles/ghi789</link>
      <source url="https://unknownblog.example.com">UnknownBlog</source>
    </item>
  </channel>
</rss>"""

    response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "https://news.google.com/rss/search"),
        content=rss_xml.encode("utf-8"),
    )

    with patch("models.verification.httpx.get", return_value=response):
        matches, snippets = search_google_news_rss(["Bitcoin", "SEC", "ETF"])

    assert len(matches) == 3
    # Reuters should be confirmed (in AUTHORITATIVE_DOMAINS)
    reuters_match = next((m for m in matches if m.name == "Reuters"), None)
    assert reuters_match is not None
    assert reuters_match.confirmed is True
    assert reuters_match.url == "https://news.google.com/rss/articles/abc123"

    # CoinDesk should be confirmed (in AUTHORITATIVE_DOMAINS)
    coindesk_match = next((m for m in matches if m.name == "CoinDesk"), None)
    assert coindesk_match is not None
    assert coindesk_match.confirmed is True
    assert coindesk_match.url == "https://news.google.com/rss/articles/def456"

    # UnknownBlog should NOT be confirmed
    unknown_match = next((m for m in matches if m.name == "UnknownBlog"), None)
    assert unknown_match is not None
    assert unknown_match.confirmed is False
    assert unknown_match.url == "https://news.google.com/rss/articles/ghi789"

    assert len(snippets) == 3
    # Title should have " - Reuters" suffix stripped
    reuters_snippet = next((s for s in snippets if s["source"] == "Reuters"), None)
    assert reuters_snippet is not None
    assert reuters_snippet["title"] == "SEC Approves Bitcoin ETF"
    assert reuters_snippet["link"] == "https://news.google.com/rss/articles/abc123"


def test_search_searxng_sources_fallback_broad() -> None:
    """
    Verifies that search_searxng_sources with fallback_broad=True parses non-authoritative
    domains and does not set confirmed=True for them, but includes them in results.
    """
    settings = Settings(searxng_url="http://localhost:8080")
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "http://localhost:8080/search"),
        json={
            "results": [
                {
                    "title": "CryptoNews report",
                    "url": "https://cryptonews.example.com/item",
                    "content": "A general crypto blog post.",
                }
            ]
        }
    )

    with patch("models.verification.httpx.get", return_value=response) as mock_get:
        matches, snippets = search_searxng_sources(["Bitcoin"], settings, fallback_broad=True)

    assert mock_get.called
    assert len(matches) == 1
    assert matches[0].name == "Cryptonews.example.com"
    assert matches[0].confirmed is False
    assert matches[0].url == "https://cryptonews.example.com/item"
    assert len(snippets) == 1
