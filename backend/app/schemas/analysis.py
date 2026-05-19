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
    """

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


class AnalyzeResponse(BaseModel):
    """
    Aggregated analysis response consumed by the React frontend.

    Attributes:
        id (str): Stable report identifier.
        text (str): Original analyzed text.
        status (VerificationStatus): Credibility verdict.
        confidence (float): Confidence score from 0 to 1.
        explanation (str): Human-readable verdict explanation.
        shap_data (list[ShapExplanation]): Token attribution list.
        sources (list[SourceMatch]): Authority matching results.
        blockchain (BlockchainProof): Integrity proof metadata.
    """

    id: str
    text: str
    status: VerificationStatus
    confidence: float = Field(ge=0, le=1)
    explanation: str
    shap_data: list[ShapExplanation] = Field(alias="shapData")
    sources: list[SourceMatch]
    blockchain: BlockchainProof

    model_config = ConfigDict(populate_by_name=True)
