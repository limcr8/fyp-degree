from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceCount(BaseModel):
    """A single source domain and how many rows reference it."""

    source: str
    count: int

    model_config = ConfigDict(populate_by_name=True)


class DatasetStats(BaseModel):
    """
    Auto-computed statistical and quality profile of an uploaded dataset.

    Attributes:
        total_rows (int): Every data row in the CSV (excluding header).
        valid_samples (int): Rows with non-empty text, label, language, source.
        completeness_pct (float): valid_samples / total_rows * 100.
        label_distribution (dict[str, int]): Normalized REAL/FAKE counts.
        languages (dict[str, int]): Row count per language code.
        top_sources (list[SourceCount]): Top five source domains by frequency.
        is_balanced (bool): Whether REAL and FAKE counts are within 35% of each other.
        quality_tier (str): Auto grade — "high", "medium", or "low".
    """

    total_rows: int = Field(alias="total_rows")
    valid_samples: int = Field(alias="valid_samples")
    completeness_pct: float = Field(alias="completeness_pct")
    label_distribution: dict[str, int] = Field(default_factory=dict, alias="label_distribution")
    languages: dict[str, int] = Field(default_factory=dict, alias="languages")
    top_sources: list[SourceCount] = Field(default_factory=list, alias="top_sources")
    is_balanced: bool = Field(default=False, alias="is_balanced")
    quality_tier: str = Field(default="low", alias="quality_tier")

    model_config = ConfigDict(populate_by_name=True)


class DatasetMetadata(BaseModel):
    """
    Persisted metadata record for an uploaded training dataset.

    Attributes:
        dataset_id (str): Generated unique identifier.
        filename (str): Original uploaded filename.
        storage_path (str): On-disk path where the CSV is stored.
        file_size_bytes (int): File size in bytes.
        file_size_display (str): Human-readable file size (e.g. "1.2 MB").
        uploaded_at (str): ISO-8601 upload timestamp.
        uploaded_by (str): Email of the admin who uploaded it.
        is_active (bool): Whether this dataset is flagged for the next training run.
        stats (DatasetStats | None): Computed statistics, or None while computing.
    """

    dataset_id: str = Field(alias="dataset_id")
    filename: str
    storage_path: str = Field(alias="storage_path")
    file_size_bytes: int = Field(alias="file_size_bytes")
    file_size_display: str = Field(default="", alias="file_size_display")
    uploaded_at: str = Field(default="", alias="uploaded_at")
    uploaded_by: str = Field(default="", alias="uploaded_by")
    is_active: bool = Field(default=False, alias="is_active")
    stats: DatasetStats | None = None

    model_config = ConfigDict(populate_by_name=True)


class DatasetListResponse(BaseModel):
    """Paginated list of dataset metadata records."""

    datasets: list[DatasetMetadata]
    total_count: int = Field(alias="total_count")

    model_config = ConfigDict(populate_by_name=True)


class DatasetDetailResponse(DatasetMetadata):
    """Single dataset record including full statistics."""


class DatasetUploadResponse(BaseModel):
    """Acknowledgement returned immediately after a successful upload."""

    message: str
    dataset_id: str = Field(alias="dataset_id")
    stats: DatasetStats

    model_config = ConfigDict(populate_by_name=True)


class DatasetMutationResponse(BaseModel):
    """Generic acknowledgement for activate / delete operations."""

    message: str
    dataset_id: str | None = Field(default=None, alias="dataset_id")

    model_config = ConfigDict(populate_by_name=True)
