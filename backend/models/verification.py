import logging
import xml.etree.ElementTree as ET
from functools import lru_cache
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings
from app.schemas.analysis import SourceMatch

logger = logging.getLogger(__name__)

SUPPORTED_ENTITY_LABELS = {"ORG", "GPE", "PERSON", "PRODUCT"}
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
AUTHORITATIVE_DOMAINS = {
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "coindesk.com": "CoinDesk",
    "cointelegraph.com": "Cointelegraph",
    "theblock.co": "The Block",
    "sec.gov": "SEC",
    "federalreserve.gov": "Federal Reserve",
    "imf.org": "IMF",
    "worldbank.org": "World Bank",
    # Malay / Malaysian sources
    "bernama.com": "Bernama",
    "malaymail.com": "Malay Mail",
    "thestar.com.my": "The Star",
    "sinarharian.com.my": "Sinar Harian",
    "hmetro.com.my": "Harian Metro",
    "bharian.com.my": "Berita Harian",
    "astroawani.com": "Astro Awani",
    "freemalaysiatoday.com": "Free Malaysia Today",
    "malaysiakini.com": "Malaysiakini",
    # Chinese / Taiwan / Hong Kong sources
    "chinapress.com.my": "China Press",
    "nanyang.com.my": "Nanyang Siang Pau",
    "xinhua.net": "Xinhua",
    "scmp.com": "South China Morning Post",
    "zaobao.com": "Zaobao",
    "cna.com.tw": "CNA Taiwan",
}


def verify_topics(text: str, settings: Settings | None = None) -> list[SourceMatch]:
    """
    Extracts topics and verifies them through authoritative Google CSE results.

    Args:
        text (str): News text to verify.
        settings (Settings | None): Optional runtime settings override.

    Returns:
        list[SourceMatch]: Frontend-compatible source matches.
    """
    active_settings = settings or get_settings()

    if not active_settings.google_api_key or not active_settings.google_cse_id:
        return []

    try:
        entities = extract_entities(text)
    except RuntimeError:
        logger.exception("Topic entity extraction failed.")
        return []

    if not entities:
        return []

    try:
        matches = search_authoritative_sources(entities, active_settings)
    except httpx.HTTPError:
        logger.exception("Google CSE request failed.")
        return []

    return matches


def _is_valid_entity(value: str) -> bool:
    """
    Validates that an entity string is clean and searchable.

    Filters out corrupted entities containing replacement characters
    (U+FFFD), control characters, or other encoding artifacts that
    would poison search queries.

    Args:
        value (str): Entity text to validate.

    Returns:
        bool: Whether the entity is clean enough to use in a search query.
    """
    # Reject empty or whitespace-only strings
    if not value or not value.strip():
        return False

    # Reject strings containing the Unicode replacement character (mojibake)
    if '\ufffd' in value:
        return False

    # Reject strings with control characters (except space/tab/newline)
    if any(ord(ch) < 32 and ch not in ' \t\n' for ch in value):
        return False

    # Reject strings that are mostly non-alphanumeric (likely binary garbage)
    alphanumeric = sum(1 for ch in value if ch.isalnum())
    if len(value) > 0 and alphanumeric / len(value) < 0.5:
        return False

    # Reject very short entities (single chars or less)
    if len(value.strip()) < 2:
        return False

    return True


def extract_entities(text: str) -> list[str]:
    """
    Extracts unique topic entities from text using spaCy NER.

    Args:
        text (str): News text to analyze.

    Returns:
        list[str]: Unique supported entities in document order.
    """
    nlp = _load_spacy_model()
    doc = nlp(text)
    entities: list[str] = []

    for entity in doc.ents:
        value = entity.text.strip()
        if (
            entity.label_ in SUPPORTED_ENTITY_LABELS
            and value
            and value not in entities
            and _is_valid_entity(value)
        ):
            entities.append(value)

    return entities[:5]


def search_authoritative_sources(
    entities: list[str],
    settings: Settings,
) -> list[SourceMatch]:
    """
    Searches Google CSE for authoritative source matches.

    Args:
        entities (list[str]): Extracted topic entities.
        settings (Settings): Runtime settings with Google CSE credentials.

    Returns:
        list[SourceMatch]: Confirmed authoritative source matches.
    """
    query = _build_query(entities)
    response = httpx.get(
        GOOGLE_CSE_URL,
        params={
            "key": settings.google_api_key,
            "cx": settings.google_cse_id,
            "q": query,
            "num": 5,
        },
        timeout=10,
    )
    response.raise_for_status()

    matches: list[SourceMatch] = []
    for item in response.json().get("items", []):
        link = str(item.get("link", ""))
        source_name = _source_name_from_url(link)
        if source_name is None:
            continue
        matches.append(SourceMatch(name=source_name, confirmed=True, url=link))

    return _deduplicate_matches(matches)


def _build_query(entities: list[str]) -> str:
    """
    Builds a constrained Google CSE query from topic entities.

    Args:
        entities (list[str]): Extracted topic entities.

    Returns:
        str: Search query.
    """
    topic = " ".join(entities[:3])
    domains = list(AUTHORITATIVE_DOMAINS.keys()) + [".gov", ".org"]
    domain_filter = " OR ".join(
        f"site:{domain}" for domain in domains
    )
    return f"{topic} ({domain_filter})"


def _source_name_from_url(url: str) -> str | None:
    """
    Resolves a display source name for an authoritative URL.

    Args:
        url (str): Search result URL.

    Returns:
        str | None: Source display name, if whitelisted or matching TLD.
    """
    hostname = urlparse(url).hostname or ""
    normalized = hostname.removeprefix("www.").lower()

    for domain, source_name in AUTHORITATIVE_DOMAINS.items():
        if normalized == domain or normalized.endswith(f".{domain}"):
            return source_name

    if ".gov" in normalized:
        parts = normalized.split(".gov")
        subparts = parts[0].split(".")
        name = subparts[-1].upper() if subparts[-1] else "Government"
        return f"{name} (Official .gov)"

    if ".org" in normalized:
        parts = normalized.split(".org")
        subparts = parts[0].split(".")
        name = subparts[-1].capitalize() if subparts[-1] else "Organization"
        return f"{name} (.org)"

    return None


def _deduplicate_matches(matches: list[SourceMatch]) -> list[SourceMatch]:
    """
    Keeps the first match for each authoritative source.

    Args:
        matches (list[SourceMatch]): Parsed source matches.

    Returns:
        list[SourceMatch]: Deduplicated source matches.
    """
    seen_names: set[str] = set()
    deduplicated: list[SourceMatch] = []

    for match in matches:
        if match.name in seen_names:
            continue
        seen_names.add(match.name)
        deduplicated.append(match)

    return deduplicated


def _fallback_sources() -> list[SourceMatch]:
    """
    Returns safe unconfirmed source rows for missing credentials or no matches.

    Returns:
        list[SourceMatch]: Default unconfirmed source matches.
    """
    return []


def _build_broad_query(entities: list[str]) -> str:
    """
    Builds a broad search query without site restrictions to fetch general related news.
    """
    return " ".join(entities[:3])


def _extract_keywords_multilingual(text: str, max_keywords: int = 4) -> list[str]:
    """
    Fallback keyword extractor for non-English text where spaCy's English model
    returns zero entities. Extracts high-frequency, content-bearing tokens.

    Args:
        text (str): News text in any language.
        max_keywords (int): Maximum number of keywords to return.

    Returns:
        list[str]: List of candidate search keywords.
    """
    import re
    # Remove URLs, numbers, common stopwords for Malay and generic Latin
    malay_stopwords = {
        "yang", "di", "dan", "ke", "ini", "itu", "dalam", "dengan", "untuk",
        "pada", "adalah", "tidak", "dari", "telah", "boleh", "akan", "ada",
        "juga", "ia", "kami", "saya", "anda", "kita", "mereka", "atau",
        "oleh", "bagi", "sudah", "belum", "pula", "lebih", "lagi",
        "the", "a", "an", "is", "was", "in", "on", "at", "to", "of", "and",
    }
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', text)
    # Tokenise on whitespace and punctuation; keep Chinese character runs as single tokens
    tokens = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]+|[A-Za-z][A-Za-z\u2019-]{2,}', cleaned)
    # Filter short tokens and stopwords, keep unique order
    seen: set[str] = set()
    keywords: list[str] = []
    for tok in tokens:
        lower = tok.lower()
        if lower in malay_stopwords or len(tok) < 3:
            continue
        if lower not in seen:
            seen.add(lower)
            keywords.append(tok)
        if len(keywords) >= max_keywords:
            break
    return keywords


def search_google_news_rss(
    entities: list[str],
    language: str = "en",
) -> tuple[list[SourceMatch], list[dict[str, str]]]:
    """
    Searches Google News RSS for related articles matching the topic entities.

    Args:
        entities (list[str]): Extracted topic entities to search for.
        language (str): BCP-47 language code used to tune Google News locale params.

    Returns:
        tuple[list[SourceMatch], list[dict[str, str]]]: Source matches and article snippets.
    """
    # Map language → Google News locale parameters
    _LOCALE_MAP = {
        "zh": ("zh-CN", "CN", "CN:zh-Hans"),
        "ms": ("ms-MY", "MY", "MY:ms"),
        "id": ("id-ID", "ID", "ID:id"),
        "ar": ("ar", "SA", "SA:ar"),
    }
    hl, gl, ceid = _LOCALE_MAP.get(language, ("en-US", "US", "US:en"))

    query = " ".join(entities[:4])  # Use up to 4 entities for a better query
    response = httpx.get(
        GOOGLE_NEWS_RSS_URL,
        params={
            "q": query,
            "hl": hl,
            "gl": gl,
            "ceid": ceid,
        },
        headers={"User-Agent": "FakeNewsDetector/1.0 (research project)"},
        timeout=8,
    )
    response.raise_for_status()

    root = ET.fromstring(response.text)
    items = root.findall(".//item")

    matches: list[SourceMatch] = []
    snippets: list[dict[str, str]] = []

    for item in items[:8]:  # Limit to 8 articles
        title_el = item.find("title")
        link_el = item.find("link")
        source_el = item.find("source")

        if title_el is None or link_el is None:
            continue

        raw_title = title_el.text or ""
        link = link_el.text or ""
        source_url = source_el.get("url", "") if source_el is not None else ""
        source_name = source_el.text if source_el is not None else ""

        # Strip the " - Source Name" suffix appended by Google News
        clean_title = raw_title
        if source_name and raw_title.endswith(f" - {source_name}"):
            clean_title = raw_title[: -len(f" - {source_name}")].strip()

        if not source_name:
            # Derive source name from the source URL
            hostname = urlparse(source_url).hostname or ""
            source_name = hostname.removeprefix("www.").split(".")[0].capitalize() or "News"

        # Check if this source is in our authoritative domains list
        source_hostname = urlparse(source_url).hostname or ""
        normalized_host = source_hostname.removeprefix("www.").lower()
        is_authoritative = any(
            normalized_host == domain or normalized_host.endswith(f".{domain}")
            for domain in AUTHORITATIVE_DOMAINS
        ) or ".gov" in normalized_host or ".org" in normalized_host

        matches.append(SourceMatch(
            name=source_name,
            confirmed=is_authoritative,
            url=link or source_url,
        ))
        snippets.append({
            "title": clean_title,
            "snippet": f"Latest news from {source_name} about {query}",
            "link": link or source_url,
            "source": source_name,
        })

    return matches, snippets


def search_searxng_sources(
    entities: list[str],
    settings: Settings,
    fallback_broad: bool = False,
) -> tuple[list[SourceMatch], list[dict[str, str]]]:
    """
    Searches SearXNG metasearch engine for authoritative source matches.

    Note: Many public SearXNG instances are protected by bot-detection.
    This function will raise an exception if the response is not valid JSON.
    """
    if fallback_broad:
        query = _build_broad_query(entities)
    else:
        query = _build_query(entities)

    url = f"{settings.searxng_url.rstrip('/')}/search"
    response = httpx.get(
        url,
        params={
            "q": query,
            "format": "json",
        },
        headers={"Accept": "application/json"},
        timeout=8,
    )
    response.raise_for_status()

    # Validate we actually got JSON (not a bot-challenge HTML page)
    content_type = response.headers.get("content-type", "")
    if "html" in content_type or not response.text.strip().startswith("{"):
        raise ValueError(f"SearXNG returned non-JSON response (likely bot-check): {content_type}")

    data = response.json()

    matches: list[SourceMatch] = []
    snippets: list[dict[str, str]] = []

    for item in data.get("results", []):
        link = str(item.get("url", ""))
        title = str(item.get("title", ""))
        snippet = str(item.get("content", ""))
        source_name = _source_name_from_url(link)

        if source_name is None:
            if fallback_broad:
                hostname = urlparse(link).hostname or ""
                source_name = hostname.removeprefix("www.").lower().capitalize() or "News Article"
            else:
                continue

        matches.append(SourceMatch(
            name=source_name,
            confirmed=(source_name in AUTHORITATIVE_DOMAINS.values() or ".gov" in link or ".org" in link),
            url=link
        ))
        snippets.append({
            "title": title,
            "snippet": snippet,
            "link": link,
            "source": source_name
        })

    return matches, snippets


def search_authoritative_sources_with_context(
    entities: list[str],
    settings: Settings,
    fallback_broad: bool = False,
) -> tuple[list[SourceMatch], list[dict[str, str]]]:
    """
    Searches Google CSE for authoritative source matches with snippets.
    """
    if fallback_broad:
        query = _build_broad_query(entities)
    else:
        query = _build_query(entities)

    response = httpx.get(
        GOOGLE_CSE_URL,
        params={
            "key": settings.google_api_key,
            "cx": settings.google_cse_id,
            "q": query,
            "num": 5,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    matches: list[SourceMatch] = []
    snippets: list[dict[str, str]] = []

    for item in data.get("items", []):
        link = str(item.get("link", ""))
        title = str(item.get("title", ""))
        snippet = str(item.get("snippet", ""))
        source_name = _source_name_from_url(link)
        
        if source_name is None:
            if fallback_broad:
                from urllib.parse import urlparse
                hostname = urlparse(link).hostname or ""
                source_name = hostname.removeprefix("www.").lower().capitalize() or "News Article"
            else:
                continue
            
        matches.append(SourceMatch(
            name=source_name, 
            confirmed=(source_name in AUTHORITATIVE_DOMAINS.values() or ".gov" in link or ".org" in link), 
            url=link
        ))
        snippets.append({
            "title": title,
            "snippet": snippet,
            "link": link,
            "source": source_name
        })

    return matches, snippets


def verify_topics_with_context(
    text: str,
    settings: Settings | None = None,
    language: str = "en",
) -> tuple[list[SourceMatch], list[dict[str, str]]]:
    """
    Extracts topics, searches for related news via Google News RSS (primary),
    SearXNG (secondary), or Google CSE (tertiary), and returns both frontend
    SourceMatch items and detailed search snippets for Gemini RAG context.

    Args:
        text (str): News text to verify.
        settings (Settings | None): Optional runtime settings override.
        language (str): BCP-47 language code of the input text.

    Returns:
        tuple[list[SourceMatch], list[dict[str, str]]]: Source matches and search snippets.
    """
    active_settings = settings or get_settings()
    fallback_sources = _fallback_sources()

    # Try spaCy English NER first; for non-English text, fall back to multilingual keyword extraction
    entities: list[str] = []
    try:
        spacy_entities = extract_entities(text)
        if spacy_entities:
            entities = spacy_entities
        else:
            # spaCy returned nothing (likely non-English) — use multilingual keyword extractor
            entities = _extract_keywords_multilingual(text)
            logger.info(
                "spaCy returned no entities for language=%s; using keyword fallback: %s",
                language, entities
            )
    except RuntimeError:
        logger.exception("Topic entity extraction failed; trying multilingual keyword fallback.")
        entities = _extract_keywords_multilingual(text)

    if not entities:
        return fallback_sources, []

    matches: list[SourceMatch] = []
    snippets: list[dict[str, str]] = []
    search_success = False

    # 1. Try Google News RSS first (free, no API key needed, most reliable)
    try:
        matches, snippets = search_google_news_rss(entities, language=language)
        if matches:
            search_success = True
            logger.info("Google News RSS returned %d results.", len(matches))
    except Exception:
        logger.exception("Google News RSS search failed.")

    # 2. Try SearXNG if Google News RSS failed and SearXNG is configured
    if not search_success and active_settings.searxng_url:
        try:
            matches, snippets = search_searxng_sources(entities, active_settings, fallback_broad=False)
            if not matches:
                matches, snippets = search_searxng_sources(entities, active_settings, fallback_broad=True)
            if matches:
                search_success = True
                logger.info("SearXNG returned %d results.", len(matches))
        except Exception:
            logger.exception("SearXNG search failed. Trying Google CSE.")

    # 3. Try Google CSE if both above failed and CSE is configured
    if not search_success and active_settings.google_api_key and active_settings.google_cse_id:
        try:
            matches, snippets = search_authoritative_sources_with_context(
                entities, active_settings, fallback_broad=False
            )
            if not matches:
                matches, snippets = search_authoritative_sources_with_context(
                    entities, active_settings, fallback_broad=True
                )
            if matches:
                search_success = True
                logger.info("Google CSE returned %d results.", len(matches))
        except Exception:
            logger.exception("Google CSE search failed in verify_topics_with_context.")

    if not search_success:
        logger.warning("All search providers failed; returning fallback sources.")
        return fallback_sources, []

    # Build final source list: only return actual matches found!
    final_sources = _deduplicate_matches(matches)
    return final_sources, snippets


@lru_cache
def _load_spacy_model() -> object:
    """
    Loads the spaCy English model lazily, preferring en_core_web_lg and falling back to en_core_web_sm.

    Returns:
        object: Loaded spaCy language pipeline.
    """
    try:
        import spacy
    except ImportError as exc:
        raise RuntimeError(
            "spaCy is required for topic verification. Install backend "
            "requirements and run: python -m spacy download en_core_web_sm"
        ) from exc

    for model_name in ["en_core_web_lg", "en_core_web_sm"]:
        try:
            logger.info("Attempting to load spaCy model: %s", model_name)
            return spacy.load(model_name)
        except OSError:
            logger.warning("spaCy model %s not found.", model_name)

    raise RuntimeError(
        "No suitable spaCy model found. Please run: "
        "python -m spacy download en_core_web_sm"
    )
