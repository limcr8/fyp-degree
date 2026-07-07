import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrustedSourceBase(BaseModel):
    """
    Shared fields for a trusted news source.

    Attributes:
        domain (str): Root domain, e.g. "reuters.com".
        display_name (str): Human-readable source label.
        tier (str): Credibility tier, one of T1/T2/T3.
        region (str): Geographic or language region tag.
        active (bool): Whether the source is used by the verifier.
    """

    domain: str
    display_name: str
    tier: str = Field(default="T2")
    region: str = Field(default="global")
    active: bool = True

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        cleaned = value.strip().lower().removeprefix("www.").rstrip("/")
        if not cleaned or "." not in cleaned:
            raise ValueError("domain must be a valid hostname such as 'reuters.com'")
        return cleaned

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if cleaned not in {"T1", "T2", "T3"}:
            raise ValueError("tier must be one of T1, T2, T3")
        return cleaned

    model_config = ConfigDict(populate_by_name=True)


class TrustedSourceCreate(TrustedSourceBase):
    """Payload accepted when creating a new trusted source."""


class TrustedSourceUpdate(BaseModel):
    """
    Partial update payload for an existing trusted source.

    All fields are optional so admins can toggle just `active`
    or rename the display label without resending everything.
    """

    display_name: str | None = None
    tier: str | None = None
    region: str | None = None
    active: bool | None = None

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if cleaned not in {"T1", "T2", "T3"}:
            raise ValueError("tier must be one of T1, T2, T3")
        return cleaned

    model_config = ConfigDict(populate_by_name=True)


class TrustedSourceResponse(TrustedSourceBase):
    """
    Full trusted source record returned to the admin UI.

    Attributes:
        source_id (str): Firestore document id.
        created_at (str): ISO-8601 creation timestamp.
        updated_at (str): ISO-8601 last-update timestamp.
    """

    source_id: str
    created_at: str = ""
    updated_at: str = ""

    model_config = ConfigDict(populate_by_name=True)


class TrustedSourceListResponse(BaseModel):
    """Paginated list of trusted sources."""

    sources: list[TrustedSourceResponse]
    total_count: int = Field(alias="total_count")

    model_config = ConfigDict(populate_by_name=True)


class TrustedSourceMutationResponse(BaseModel):
    """Generic acknowledgement returned after create/update/delete/seed."""

    message: str
    source_id: str | None = Field(default=None, alias="source_id")

    model_config = ConfigDict(populate_by_name=True)