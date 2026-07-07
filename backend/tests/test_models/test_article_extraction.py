from unittest.mock import patch

import httpx

from models.article_extraction import extract_article_text, is_url, resolve_input_text


def test_is_url_accepts_http_and_https_only() -> None:
    """
    Verifies URL detection for supported article inputs.
    """
    assert is_url("https://crypto.news/article")
    assert is_url("http://example.com/news")
    assert not is_url("Bitcoin ETF approved by regulators.")
    assert not is_url("ftp://example.com/file")


def test_extract_article_text_parses_article_body() -> None:
    """
    Verifies article extraction from a mocked HTML response.
    """
    html = """
    <html>
      <head><title>Ignored browser title</title></head>
      <body>
        <article>
          <h1>BitMine expands Ethereum holdings</h1>
          <p>BitMine increased its Ethereum treasury position this week.</p>
          <p>The company said it remains focused on its five percent supply goal.</p>
        </article>
      </body>
    </html>
    """
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "https://example.com/news"),
        text=html,
    )

    with patch("models.article_extraction.httpx.get", return_value=response):
        text = extract_article_text("https://example.com/news")

    assert "BitMine expands Ethereum holdings" in text
    assert "Ethereum treasury position" in text
    assert "five percent supply goal" in text


def test_resolve_input_text_keeps_plain_text_unchanged() -> None:
    """
    Verifies plain text input is not fetched or modified.
    """
    text = "Bitcoin ETF approved after regulator confirmation."

    assert resolve_input_text(text) == text


def test_resolve_input_text_falls_back_to_original_url_on_fetch_error() -> None:
    """
    Verifies URL input stays analyzable when extraction fails.
    """
    with patch("models.article_extraction.extract_article_text", side_effect=RuntimeError):
        assert resolve_input_text("https://example.com/news") == "https://example.com/news"
