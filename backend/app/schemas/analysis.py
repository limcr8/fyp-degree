from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class VerificationStatus(str, Enum):
    """
    Defines supported credibility verdicts.
    """

    REAL = "REAL"
    FAKE = "FAKE"
    UNCERTAIN = "UNCERTAIN"


class AnalyzeRequest(BaseModel):
    """
    Request body for news analysis.

    Attributes:
        text (str): English cryptocurrency or financial news text.
        language (str | None): Optional language key (e.g. 'en', 'zh', 'ms').
        platform (str | None): Optional platform source key (e.g. 'twitter', 'reddit', 'telegram').
        fast_mode (bool): If True, bypass LLM verification.
    """

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    language: str | None = "en"
    platform: str | None = "website"
    fast_mode: bool = False



class ShapExplanation(BaseModel):
    """
    Frontend-compatible SHAP token attribution.

    Attributes:
        word (str): Token or phrase being explained.
        weight (float): Contribution weight for the verdict.
    """

    word: str
    weight: float


class SourceMatch(BaseModel):
    """
    Source verification result for an authoritative domain.

    Attributes:
        name (str): Source display name.
        confirmed (bool): Whether corroborating evidence was found.
        url (str | None): Optional matching article URL.
    """

    name: str
    confirmed: bool
    url: str | None = None


class BlockchainProof(BaseModel):
    """
    Integrity proof metadata for the completed verification report.

    Attributes:
        transaction_hash (str): EVM transaction hash.
        block_number (int): Block number containing the proof.
        timestamp (str): Proof creation timestamp.
        ipfs_hash (str): IPFS content identifier.
        network (str): Blockchain network name.
    """

    transaction_hash: str = Field(alias="transactionHash")
    block_number: int = Field(alias="blockNumber")
    timestamp: str
    ipfs_hash: str = Field(alias="ipfsHash")
    network: str

    model_config = ConfigDict(populate_by_name=True)


class ClassificationDetail(BaseModel):
    """
    Classification outcome from RoBERTa or Gemini.
    """

    verdict: str
    confidence: float
    risk_level: str = Field(alias="riskLevel")
    explanation: str

    model_config = ConfigDict(populate_by_name=True)


class ExplanationDetail(BaseModel):
    """
    Attributions explaining the linguistic verdict.
    """

    shap_data: list[ShapExplanation] = Field(alias="shapData")
    summary: str
    top_factors: list[str] = Field(alias="topFactors")

    model_config = ConfigDict(populate_by_name=True)


class MatchingArticle(BaseModel):
    """
    Metadata representation of a retrieved matching search result/news article.
    """

    title: str
    link: str
    source: str
    snippet: str


class SourceComparison(BaseModel):
    """
    Comparative analysis of a retrieved source against the news claim.

    Attributes:
        source_name (str): Display name of the source (e.g. Reuters, Bloomberg).
        article_title (str): Headline of the matching article.
        relationship (str): One of SUPPORTS, REFUTES, or UNRELATED.
        key_finding (str): One-sentence insight extracted from the source.
    """

    source_name: str = Field(alias="source_name")
    article_title: str = Field(alias="article_title")
    relationship: str
    key_finding: str = Field(alias="key_finding")

    model_config = ConfigDict(populate_by_name=True)


class VerificationDetail(BaseModel):
    """
    Verification matches from authoritative external sources.
    """

    sources: list[SourceMatch]
    verification_score: float = Field(alias="verificationScore")
    explanation: str
    matching_articles: list[MatchingArticle] = Field(default=[], alias="matchingArticles")
    summary: str | None = None
    source_comparison: list[SourceComparison] = Field(default=[], alias="sourceComparison")

    model_config = ConfigDict(populate_by_name=True)


class FinalAssessment(BaseModel):
    """
    Weighted decision combining classification and source grounding.
    """

    score: float
    label: str
    reasoning: str


class AnalyzeResponse(BaseModel):
    """
    Aggregated multi-layer analysis response.
    """

    id: str
    text: str
    classification: ClassificationDetail
    explanation: ExplanationDetail
    verification: VerificationDetail
    final_assessment: FinalAssessment = Field(alias="finalAssessment")
    blockchain: BlockchainProof
    processing_time_ms: int = Field(alias="processingTimeMs")
    created_at: str | None = Field(default=None, alias="createdAt")
    platform: str | None = "website"
    language: str | None = "en"

    model_config = ConfigDict(populate_by_name=True)


class BatchArticleItem(BaseModel):
    """
    Individual article item for batch verification.

    Attributes:
        text (str): News text to classify.
        language (str | None): Optional language key (e.g. 'en', 'zh', 'ms').
    """

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    language: str | None = "en"


class BatchVerifyRequest(BaseModel):
    """
    Request body for bulk news verification.

    Attributes:
        articles (list[BatchArticleItem]): List of news articles to verify.
    """

    articles: list[BatchArticleItem]


class BatchVerifyResponse(BaseModel):
    """
    Response schema for bulk news verification.

    Attributes:
        batch_id (str): Generated identifier for the batch.
        results (list[AnalyzeResponse]): Analysis reports for each article.
        status (str): Overall completion status (e.g., 'completed').
        total_time_ms (int): Total processing time in milliseconds.
    """

    batch_id: str = Field(alias="batch_id")
    results: list[AnalyzeResponse]
    status: str
    total_time_ms: int = Field(alias="total_time_ms")

    model_config = ConfigDict(populate_by_name=True)


class SearchResultItem(BaseModel):
    """
    Search result representation of a verified news report.
    """

    article_id: str = Field(alias="article_id")
    text: str
    classification: ClassificationDetail
    created_at: str = Field(alias="created_at")
    platform: str
    language: str

    model_config = ConfigDict(populate_by_name=True)


class SearchResponse(BaseModel):
    """
    Paginated search response for verified news reports.
    """

    results: list[SearchResultItem]
    total_count: int = Field(alias="total_count")
    page: int
    per_page: int = Field(alias="per_page")

    model_config = ConfigDict(populate_by_name=True)


class TrendingTopicItem(BaseModel):
    """
    Representation of a trending topic and its associated articles.
    """

    topic: str
    mentions: int
    fake_count: int = Field(alias="fake_count")
    articles: list[SearchResultItem]

    model_config = ConfigDict(populate_by_name=True)


class TrendingResponse(BaseModel):
    """
    Response schema for trending topics.
    """

    trending: list[TrendingTopicItem]


class HistoryItem(BaseModel):
    """
    A single verification history record.
    """

    article_id: str = Field(alias="article_id")
    text: str
    classification: ClassificationDetail
    verified_at: str = Field(alias="verified_at")
    explanation: ExplanationDetail | None = None
    verification: VerificationDetail | None = None
    finalAssessment: FinalAssessment | None = Field(None, alias="finalAssessment")
    blockchain: BlockchainProof | None = None
    processingTimeMs: int | None = Field(None, alias="processingTimeMs")
    platform: str | None = None
    language: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class UserHistoryResponse(BaseModel):
    """
    Paginated user verification history response.
    """

    history: list[HistoryItem]
    total_count: int = Field(alias="total_count")
    page: int

    model_config = ConfigDict(populate_by_name=True)



