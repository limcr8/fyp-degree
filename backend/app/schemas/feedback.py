from pydantic import BaseModel, ConfigDict, Field


class FeedbackRequest(BaseModel):
    """
    Submission request payload representing user dispute/feedback.
    """

    article_id: str = Field(alias="article_id")
    feedback_type: str = Field(alias="feedback_type")
    message: str
    user_email: str = Field(alias="user_email")

    model_config = ConfigDict(populate_by_name=True)


class FeedbackResponse(BaseModel):
    """
    API Response confirmation returned on successful feedback registration.
    """

    feedback_id: str = Field(alias="feedback_id")
    status: str
    message: str

    model_config = ConfigDict(populate_by_name=True)
