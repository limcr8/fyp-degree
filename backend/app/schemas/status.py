from pydantic import BaseModel, ConfigDict, Field


class ApiServerStatus(BaseModel):
    """
    Detailed status of the API server.
    """

    status: str
    response_time_ms: int = Field(alias="response_time_ms")

    model_config = ConfigDict(populate_by_name=True)


class DatabaseStatus(BaseModel):
    """
    Detailed status of the local database storage.
    """

    status: str
    connection_pool: str = Field(alias="connection_pool")

    model_config = ConfigDict(populate_by_name=True)


class MlModelsStatus(BaseModel):
    """
    Detailed status of the machine learning classifier models.
    """

    status: str
    bert_loaded: bool = Field(alias="bert_loaded")
    average_inference_time_ms: int = Field(alias="average_inference_time_ms")

    model_config = ConfigDict(populate_by_name=True)


class ExternalApisStatus(BaseModel):
    """
    Detailed status of downstream external integrations.
    """

    google_search: str = Field(alias="google_search")
    twitter: str
    redis: str

    model_config = ConfigDict(populate_by_name=True)


class ComponentsStatus(BaseModel):
    """
    System component metrics mapping.
    """

    api_server: ApiServerStatus = Field(alias="api_server")
    database: DatabaseStatus
    ml_models: MlModelsStatus = Field(alias="ml_models")
    external_apis: ExternalApisStatus = Field(alias="external_apis")

    model_config = ConfigDict(populate_by_name=True)


class StatusResponse(BaseModel):
    """
    Detailed system status check response payload.
    """

    overall_status: str = Field(alias="overall_status")
    components: ComponentsStatus
    last_checked: str = Field(alias="last_checked")

    model_config = ConfigDict(populate_by_name=True)
