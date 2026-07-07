import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
MIN_EXTRACTED_TEXT_LENGTH = 120


def extract_article_metadata(url: str) -> str:
    """
    Last-resort extraction that returns whatever title/description the
    page exposes, even when full article-body extraction fails.

    Many Cloudflare-protected pages still serve the base HTML containing
    OpenGraph and meta-description tags, so this typically yields a real
    headline rather than "External Article".

    Args:
        url (str): Article URL.

    Returns:
        str: Headline and (if present) description, separated by a blank
        line. Falls back to the URL host if nothing parseable is found.
    """
    try:
        html = _fetch_html(url)
    except httpx.HTTPError:
        logger.exception("Metadata fetch failed; returning domain label.")
        host = urlparse(url).hostname or url
        return f"External Article ({host.removeprefix('www.')})"

    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)

    description = ""
    desc_tag = soup.find("meta", {"name": "description"}) or soup.find(
        "meta", {"property": "og:description"}
    )
    if desc_tag and desc_tag.get("content"):
        description = str(desc_tag["content"]).strip()

    parts = [p for p in (title, description) if p]
    if not parts:
        host = urlparse(url).hostname or url
        return f"External Article ({host.removeprefix('www.')})"
    return "\n\n".join(parts)


def resolve_input_text(text: str) -> str:
    """
    Resolves user input into analyzable article text.

    Cascade:
      1. Full article-body extraction (multi-fingerprint scraper).
      2. Title + description fallback (works on most blocked pages).
      3. Raw input (only if even metadata fetch fails).

    Args:
        text (str): Raw user input, either article text or a URL.

    Returns:
        str: Extracted article text, metadata, or original input.
    """
    candidate = text.strip()
    if not is_url(candidate):
        return candidate

    try:
        return extract_article_text(candidate)
    except (httpx.HTTPError, RuntimeError, ValueError):
        logger.exception("Full article extraction failed; falling back to metadata.")
    try:
        return extract_article_metadata(candidate)
    except Exception:
        logger.exception("Metadata extraction failed; falling back to raw input.")
        return candidate


def is_url(text: str) -> bool:
    """
    Checks whether input is a supported HTTP(S) URL.

    Args:
        text (str): Raw input.

    Returns:
        bool: Whether input is an HTTP(S) URL.
    """
    parsed = urlparse(text.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _fetch_html(url: str) -> str:
    """
    Fetches raw HTML from a URL, trying multiple browser fingerprints.

    Cascade: Chrome desktop → Firefox desktop → Mobile Safari. Different
    sites block different fingerprints, so trying all three maximises the
    chance of bypassing basic anti-bot protection.

    Args:
        url (str): Article URL.

    Returns:
        str: Raw HTML response body.

    Raises:
        httpx.HTTPError: When every fingerprint attempt fails.
    """
    BASE_HEADERS = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    FINGERPRINTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    ]

    last_exc: httpx.HTTPError | None = None
    for i, ua in enumerate(FINGERPRINTS):
        headers = dict(BASE_HEADERS)
        headers["User-Agent"] = ua
        try:
            response = httpx.get(
                url,
                headers=headers,
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.info("Scraper tier %d returned %d; trying next fingerprint.", i + 1, exc.response.status_code)
            continue
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.info("Scraper tier %d raised %s; trying next fingerprint.", i + 1, type(exc).__name__)
            continue

    assert last_exc is not None
    raise last_exc


def extract_article_text(url: str) -> str:
    """
    Fetches and extracts readable article text from a URL.

    Uses a multi-tier scraper (Chrome, Firefox, Mobile) to bypass basic
    anti-bot protection that blocks a single user-agent fingerprint.

    Args:
        url (str): Article URL.

    Returns:
        str: Extracted title and article body.
    """
    html = _fetch_html(url)

    soup = BeautifulSoup(html, "html.parser")
    _remove_noise(soup)
    extracted_text = _extract_readable_text(soup)

    # Sanitize encoding artifacts: remove replacement characters (mojibake)
    # and control characters that corrupt downstream entity extraction.
    extracted_text = _sanitize_text(extracted_text)

    if len(extracted_text) < MIN_EXTRACTED_TEXT_LENGTH:
        raise RuntimeError("Extracted article text is too short.")

    return extracted_text


def _sanitize_text(text: str) -> str:
    """
    Removes encoding artifacts and corrupted characters from extracted text.

    Cleans up:
    - Unicode replacement characters (U+FFFD) from decoding errors
    - Control characters (except common whitespace)
    - Collapsed excessive whitespace

    Args:
        text (str): Raw extracted text.

    Returns:
        str: Sanitized text.
    """
    import re
    # Remove Unicode replacement characters
    cleaned = text.replace('\ufffd', '')
    # Remove control characters except tab, newline, carriage return
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    # Collapse multiple spaces/newlines
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def _remove_noise(soup: BeautifulSoup) -> None:
    """
    Removes common non-content tags from an HTML document.

    Args:
        soup (BeautifulSoup): Parsed HTML document.
    """
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer"]):
        tag.decompose()


def _extract_readable_text(soup: BeautifulSoup) -> str:
    """
    Extracts title and paragraphs from likely article containers.

    Falls back to collecting all paragraphs document-wide when no
    standard semantic container (article, main, body) is present.

    Args:
        soup (BeautifulSoup): Parsed HTML document.

    Returns:
        str: Normalized article text.
    """
    title = _extract_title(soup)
    container = (
        soup.find("article")
        or soup.find(attrs={"role": "article"})
        or soup.find("main")
        or soup.body
    )

    if container is None:
        # Last-resort fallback: scan the whole document for paragraph text.
        # Some sites wrap content in generic <div> tags with no semantic markup.
        all_paragraphs = soup.find_all(["h1", "h2", "h3", "p"])
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in all_paragraphs
            if p.get_text(" ", strip=True)
        ]
        if not paragraphs:
            raise RuntimeError("Article HTML did not contain a readable body.")
        logger.info(
            "No semantic container found; extracted %d paragraphs document-wide.",
            len(paragraphs),
        )
    else:
        paragraphs = [
            paragraph.get_text(" ", strip=True)
            for paragraph in container.find_all(["h1", "h2", "h3", "p"])
        ]

    cleaned_parts = _deduplicate_parts([title, *paragraphs])
    return "\n\n".join(cleaned_parts)


def _extract_title(soup: BeautifulSoup) -> str:
    """
    Extracts the best available article title.

    Args:
        soup (BeautifulSoup): Parsed HTML document.

    Returns:
        str: Article title or empty string.
    """
    for selector in [
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "twitter:title"}),
    ]:
        tag = soup.find(*selector)
        if tag and tag.get("content"):
            return str(tag["content"]).strip()

    heading = soup.find("h1")
    if heading:
        return heading.get_text(" ", strip=True)

    if soup.title and soup.title.string:
        return soup.title.string.strip()

    return ""


def _deduplicate_parts(parts: list[str]) -> list[str]:
    """
    Removes empty and duplicate text chunks while preserving order.

    Args:
        parts (list[str]): Candidate text chunks.

    Returns:
        list[str]: Cleaned text chunks.
    """
    seen: set[str] = set()
    cleaned: list[str] = []

    for part in parts:
        normalized = " ".join(part.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    return cleaned
