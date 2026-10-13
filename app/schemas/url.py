from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class URLCreateRequest(BaseModel):
    original_url: str = Field(
        ...,
        description="The target URL to be shortened",
        examples=["https://example.com/very/long/path/to/resource"],
    )
    custom_code: Optional[str] = Field(
        None,
        min_length=3,
        max_length=16,
        description="Optional custom alias short code (alphanumeric, hyphens, underscores)",
        examples=["my-custom-link"],
    )
    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Optional lifespan of the short URL in days",
        examples=[30],
    )

    @field_validator("original_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("URL length exceeds 2048 characters limit")
        return v

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v.isalnum() and not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("Custom code may only contain alphanumeric characters, hyphens, and underscores")
        return v


class URLResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    click_count: int

    model_config = ConfigDict(from_attributes=True)


class URLUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None
