"""
Model for outgoing posts that we send to users/channels
"""

from datetime import datetime, UTC
from typing import Optional
from pydantic import BaseModel, Field


class OutgoingPost(BaseModel):
    """Model for posts that we send to users or channels"""
    
    # Basic post data
    id: Optional[str] = None
    message: str
    
    # Media information
    media_type: Optional[str] = None  # photo, video, document, etc.
    media_url: Optional[str] = None
    
    # Sending information
    sent_at: Optional[datetime] = None
    sent_to: str  # User ID or channel ID
    sent_to_type: str = Field(default="user", description="user or channel")
    
    # Status
    status: str = Field(default="pending", description="pending, sent, failed")
    error_message: Optional[str] = None
    
    # Link to source
    real_estate_ad_id: Optional[str] = None  # Link to original RealEstateAd
    incoming_message_id: Optional[int] = None  # Link to original IncomingMessage
    
    # Channel and topic information
    channel_id: Optional[int] = None  # Original channel ID
    channel_username: Optional[str] = None  # Channel username
    channel_title: Optional[str] = None  # Channel title
    topic_id: Optional[int] = None  # Topic ID if from topic-based channel
    topic_title: Optional[str] = None  # Topic title
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
