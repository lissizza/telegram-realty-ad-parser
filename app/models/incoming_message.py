"""
Model for incoming messages from Telegram channels
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    """Model for incoming messages from Telegram channels"""
    
    # Basic message data
    id: int
    channel_id: int
    topic_id: Optional[int] = None  # Topic ID for topic-based channels
    channel_title: str
    message: str
    date: datetime
    
    # Message statistics (from Telegram)
    views: Optional[int] = None
    forwards: Optional[int] = None
    replies: Optional[int] = None
    
    # Media information
    media_type: Optional[str] = None  # photo, video, document, etc.
    media_url: Optional[str] = None
    
    # Processing status
    processing_status: str = Field(default="pending", description="pending, processing, completed, failed")
    processed_at: Optional[datetime] = None
    parsing_errors: List[str] = []
    
    # Content analysis
    is_spam: Optional[bool] = None
    spam_reason: Optional[str] = None
    is_real_estate: Optional[bool] = None
    real_estate_confidence: Optional[float] = None
    
    # Link to parsed real estate ad
    real_estate_ad_id: Optional[str] = None
    
    # Forwarding information
    forwarded: bool = False
    forwarded_at: Optional[datetime] = None
    forwarded_to: Optional[str] = None  # User ID who received the forward
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
