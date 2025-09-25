from datetime import datetime, UTC
from typing import List, Optional

from pydantic import BaseModel, Field


class UserChannelSubscription(BaseModel):
    """Model for user subscriptions to Telegram channels"""
    id: Optional[str] = None
    user_id: int
    channel_id: Optional[int] = None  # Telegram channel ID (numeric)
    channel_username: Optional[str] = None  # Channel username (string)
    channel_title: str
    channel_link: Optional[str] = None  # Full Telegram link
    
    # Subchannel/Topic support
    topic_id: Optional[int] = None  # For channels with topics (like @rent_comissionfree/2629)
    topic_title: Optional[str] = None
    
    # Subscription settings
    is_active: bool = True
    monitor_all_topics: bool = False  # If True, monitor all topics in the channel
    monitored_topics: List[int] = Field(default_factory=list)  # Specific topic IDs to monitor
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserChannelSubscriptionCreate(BaseModel):
    """Model for creating user channel subscriptions"""
    user_id: int
    channel_input: str  # Can be username, link, or full URL
    topic_id: Optional[int] = None
    monitor_all_topics: bool = False
    monitored_topics: List[int] = Field(default_factory=list)


class UserChannelSubscriptionResponse(BaseModel):
    """Model for API responses"""
    id: str
    user_id: int
    channel_id: Optional[str] = None  # Changed to str to match database storage
    channel_username: Optional[str] = None
    channel_title: str
    channel_link: Optional[str] = None
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    is_active: bool
    monitor_all_topics: bool
    monitored_topics: List[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @classmethod
    def from_db_doc(cls, doc: dict):
        """Create response model from database document"""
        return cls(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            channel_id=doc.get("channel_id"),  # Keep as string
            channel_username=doc.get("channel_username"),
            channel_title=doc.get("channel_title", "Unknown"),
            channel_link=doc.get("channel_link"),
            topic_id=doc.get("topic_id"),
            topic_title=doc.get("topic_title"),
            is_active=doc.get("is_active", True),
            monitor_all_topics=doc.get("monitor_all_topics", False),
            monitored_topics=doc.get("monitored_topics", []),
            created_at=doc.get("created_at", datetime.now(UTC)),
            updated_at=doc.get("updated_at", datetime.now(UTC))
        )



