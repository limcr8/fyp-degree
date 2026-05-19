import logging
from functools import lru_cache
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings
from app.schemas.analysis import SourceMatch

logger = logging.getLogger(__name__)

SUPPORTED_ENTITY_LABELS = {"ORG", "GPE", "PERSON", "PRODUCT"}
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
        return _fallback_sources()

    try:
        entities = extract_entities(text)
    except RuntimeError:
        logger.exception("Topic entity extraction failed.")
        return _fallback_sources()

    if not entities:
        return _fallback_sources()

    try:
        matches = search_authoritative_sources(entities, active_settings)
    except httpx.HTTPError:
        logger.exception("Google CSE request failed.")
        return _fallback_sources()

    return matches or _fallback_sources()


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
        if entity.label_ in SUPPORTED_ENTITY_LABELS and value and value not in entities:
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
    domain_filter = " OR ".join(
        f"site:{domain}" for domain in AUTHORITATIVE_DOMAINS
    )
    return f"{topic} crypto finance news ({domain_filter})"


def _source_name_from_url(url: str) -> str | None:
    """
    Resolves a display source name for an authoritative URL.

    Args:
        url (str): Search result URL.

    Returns:
        str | None: Source display name, if whitelisted.
    """
    hostname = urlparse(url).hostname or ""
    normalized = hostname.removeprefix("www.").lower()

    for domain, source_name in AUTHORITATIVE_DOMAINS.items():
        if normalized == domain or normalized.endswith(f".{domain}"):
            return source_name

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
    return [
        SourceMatch(name="Reuters", confirmed=False),
        SourceMatch(name="Bloomberg", confirmed=False),
        SourceMatch(name="CoinDesk", confirmed=False),
        SourceMatch(name="SEC", confirmed=False),
    ]


@lru_cache
def _load_spacy_model() -> object:
    """
    Loads the spaCy English model lazily.

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

    try:
        return spacy.load("en_core_web_sm")
    except OSError as exc:
        raise RuntimeError(
            "spaCy model en_core_web_sm is missing. Run: "
            "python -m spacy download en_core_web_sm"
        ) from exc
