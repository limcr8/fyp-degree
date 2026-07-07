from pydantic import BaseModel, StringConstraints
from typing import Annotated


class RegisterRequest(BaseModel):
    """
    Request payload for registering a new user account.
    """

    username: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)] = None
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=100)]
    password: Annotated[str, StringConstraints(min_length=6, max_length=100)]
    firebase_uid: str | None = None


class RegisterResponse(BaseModel):
    """
    Response payload after successful registration.
    """

    user_id: str
    username: str
    email: str
    role: str
    api_key: str
    doc_id: str
    message: str


class LoginRequest(BaseModel):
    """
    Request payload for user authentication.
    """

    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=100)]
    password: Annotated[str, StringConstraints(min_length=6, max_length=100)]


class UserDetail(BaseModel):
    """
    Compact user detail for token payload.
    """

    user_id: str
    username: str
    role: str


class LoginResponse(BaseModel):
    """
    Response payload after successful authentication.
    """

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    user: UserDetail


class RefreshResponse(BaseModel):
    """
    Response payload after successful token refresh.
    """

    access_token: str
    expires_in: int = 3600


class LogoutResponse(BaseModel):
    """
    Response payload after successful logout.
    """

    message: str = "Logged out successfully"


class ApiQuota(BaseModel):
    """
    API usage quota limits.
    """

    daily_limit: int = 100
    used_today: int = 0
    reset_at: str


class UserMeResponse(BaseModel):
    """
    Detailed user information profile response.
    """

    user_id: str
    username: str
    name: str | None = None
    email: str
    role: str
    api_key: str
    api_quota: ApiQuota
    created_at: str
    last_login: str | None = None
    preferences: dict | None = None


class ProfilePreferences(BaseModel):
    """
    User preference options.
    """

    language: str = "en"
    notifications: bool = True


class UpdateProfileRequest(BaseModel):
    """
    Request payload to modify user profile details.
    """

    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=100)]
    preferences: ProfilePreferences


class UpdateProfileResponse(BaseModel):
    """
    Response payload after updating profile details.
    """

    message: str = "Profile updated successfully"
    user: UserMeResponse


class ChangePasswordRequest(BaseModel):
    """
    Request payload to change user password.
    """

    old_password: Annotated[str, StringConstraints(min_length=6, max_length=100)]
    new_password: Annotated[str, StringConstraints(min_length=6, max_length=100)]


class ChangePasswordResponse(BaseModel):
    """
    Response payload after successful password change.
    """

    message: str = "Password changed successfully"