"""
Model for tracking matches between users, filters, and real estate ads
"""

from datetime import datetime, UTC
from typing import Optional
from pydantic import BaseModel, Field


class UserFilterMatch(BaseModel):
    """Model for tracking when a real estate ad matches a user's filter"""
    
    id: Optional[str] = None
    user_id: int  # Telegram user ID
    filter_id: str  # SimpleFilter ID
    real_estate_ad_id: str  # RealEstateAd ID
    
    # Match metadata
    matched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    forwarded: bool = False  # Whether this match was forwarded to user
    forwarded_at: Optional[datetime] = None
    
    # Processing status
    status: str = Field(default="matched", description="matched, forwarded, failed")
    error_message: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))













