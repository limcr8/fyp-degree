from pydantic import BaseModel, ConfigDict


class ServicesHealth(BaseModel):
    """
    Status of individual backend services.

    Attributes:
        api (str): Status of the API service.
        database (str): Status of the database / file storage service.
        bert_model (str): Status of the RoBERTa NLP classifier model.
        cache (str): Status of the local cache service.
    """

    api: str
    database: str
    bert_model: str
    cache: str


class HealthResponse(BaseModel):
    """
    Detailed system health check response payload.

    Attributes:
        status (str): Overall system status ('healthy' or 'unhealthy').
        timestamp (str): ISO8601 UTC timestamp of the health check.
        services (ServicesHealth): Individual statuses for downstream services.
        version (str): Application version string.
        uptime_seconds (int): Uptime of the application in seconds.
    """

    status: str
    timestamp: str
    services: ServicesHealth
    version: str
    uptime_seconds: int

    model_config = ConfigDict(populate_by_name=True)
