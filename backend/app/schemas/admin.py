from pydantic import BaseModel, ConfigDict, Field


class AdminDashboardResponse(BaseModel):
    """
    Overview stats for the administrator dashboard.

    Attributes:
        total_verifications (int): Total historical news verifications performed.
        daily_verifications (int): Verifications performed in the last 24 hours.
        model_accuracy (float): Current predictive accuracy rate of the ML model.
        api_health (str): Diagnostic health indicator.
        active_users (int): Count of active users on the platform.
        pending_reviews (int): Count of flag/uncertain verifications awaiting review.
        system_uptime_percent (float): Overall uptime metric percentage.
    """

    total_verifications: int = Field(alias="total_verifications")
    daily_verifications: int = Field(alias="daily_verifications")
    model_accuracy: float = Field(alias="model_accuracy")
    api_health: str = Field(alias="api_health")
    active_users: int = Field(alias="active_users")
    pending_reviews: int = Field(alias="pending_reviews")
    system_uptime_percent: float = Field(alias="system_uptime_percent")

    model_config = ConfigDict(populate_by_name=True)


class TrainingStatusResponse(BaseModel):
    """
    Status metrics for an active model training/fine-tuning job.

    Attributes:
        job_id (str): Identifier of the training job.
        status (str): Current execution state (e.g., 'in_progress', 'completed', 'failed').
        progress_percent (int): Completion progress percentage.
        current_epoch (int): Current epoch iteration number.
        total_epochs (int): Total epochs planned for training.
        current_loss (float): Current training loss value.
        elapsed_time_minutes (int): Elapsed duration in minutes.
        estimated_remaining_minutes (int): Remaining estimated minutes.
    """

    job_id: str = Field(alias="job_id")
    status: str
    progress_percent: int = Field(alias="progress_percent")
    current_epoch: int = Field(alias="current_epoch")
    total_epochs: int = Field(alias="total_epochs")
    current_loss: float = Field(alias="current_loss")
    elapsed_time_minutes: int = Field(alias="elapsed_time_minutes")
    estimated_remaining_minutes: int = Field(alias="estimated_remaining_minutes")

    model_config = ConfigDict(populate_by_name=True)


class DatasetUploadResponse(BaseModel):
    """
    Metadata summary of a successfully uploaded CSV training dataset.

    Attributes:
        dataset_id (str): Generated unique dataset identifier.
        filename (str): The original name of the uploaded CSV file.
        samples_count (int): Count of valid data rows containing text and labels.
        languages (list[str]): List of unique languages extracted from the dataset.
        message (str): Successful status indicator message.
    """

    dataset_id: str = Field(alias="dataset_id")
    filename: str
    samples_count: int = Field(alias="samples_count")
    languages: list[str]
    message: str

    model_config = ConfigDict(populate_by_name=True)



class ApiUsageStats(BaseModel):
    """
    API invocation usage metrics.
    """

    total_requests: int = Field(alias="total_requests")
    daily_average: int = Field(alias="daily_average")
    peak_daily: int = Field(alias="peak_daily")

    model_config = ConfigDict(populate_by_name=True)


class VerificationStats(BaseModel):
    """
    Summarized credibility classification counts.
    """

    total: int
    fake: int
    real: int
    uncertain: int

    model_config = ConfigDict(populate_by_name=True)


class ModelPerformanceStats(BaseModel):
    """
    Historical model predictive performance metrics.
    """

    accuracy: float
    precision: float
    recall: float
    f1_score: float = Field(alias="f1_score")

    model_config = ConfigDict(populate_by_name=True)


class CostAnalysisStats(BaseModel):
    """
    Cost breakdown analysis for APIs and storage.
    """

    google_api_cost: float = Field(alias="google_api_cost")
    ipfs_storage_gb: float = Field(alias="ipfs_storage_gb")
    total_monthly: float = Field(alias="total_monthly")

    model_config = ConfigDict(populate_by_name=True)


class AdminAnalyticsResponse(BaseModel):
    """
    Detailed analytics response metrics for administration monitoring.
    """

    period: str
    api_usage: ApiUsageStats = Field(alias="api_usage")
    verification_stats: VerificationStats = Field(alias="verification_stats")
    model_performance: ModelPerformanceStats = Field(alias="model_performance")
    cost_analysis: CostAnalysisStats = Field(alias="cost_analysis")

    model_config = ConfigDict(populate_by_name=True)


class AdminUserItem(BaseModel):
    """
    Individual user record details for admin management.
    """

    user_id: str = Field(alias="user_id")
    username: str
    email: str
    role: str
    created_at: str = Field(alias="created_at")
    last_login: str = Field(alias="last_login")
    verifications_count: int = Field(alias="verifications_count")

    model_config = ConfigDict(populate_by_name=True)


class AdminUsersResponse(BaseModel):
    """
    Registry of registered user accounts returned for administration monitoring.
    """

    users: list[AdminUserItem]
    total_count: int = Field(alias="total_count")
    page: int

    model_config = ConfigDict(populate_by_name=True)


class AdminUserDeleteResponse(BaseModel):
    """
    Status response of a user deletion action.
    """

    message: str
    user_id: str = Field(alias="user_id")

    model_config = ConfigDict(populate_by_name=True)


class AdminTrendPoint(BaseModel):
    """
    A single daily bucket in the verification trend.

    Attributes:
        date (str): ISO date (YYYY-MM-DD) for the bucket.
        count (int): Number of verifications performed on that day.
    """

    date: str
    count: int

    model_config = ConfigDict(populate_by_name=True)


class AdminTrendResponse(BaseModel):
    """
    Time-series verification counts used to render the dashboard trend chart.

    Attributes:
        days (int): Number of days covered by the trend.
        trend (list[AdminTrendPoint]): Ordered daily verification buckets.
    """

    days: int
    trend: list[AdminTrendPoint]

    model_config = ConfigDict(populate_by_name=True)



