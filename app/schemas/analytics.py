from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class ClickEventSchema(BaseModel):
    timestamp: datetime
    referer: Optional[str] = None
    country: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class URLAnalyticsResponse(BaseModel):
    short_code: str
    original_url: str
    total_clicks: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    top_referrers: Dict[str, int]
    clicks_last_24h: int
    recent_events: List[ClickEventSchema]

    model_config = ConfigDict(from_attributes=True)
