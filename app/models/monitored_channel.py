import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field, validator

from app.utils.channel_id_utils import normalize_channel_id, channel_id_to_string


class MonitoredChannel(BaseModel):
    """Model for monitored channels (not tied to specific users)"""
    channel_id: str = Field(..., description="Telegram channel ID in normalized format")
    channel_username: Optional[str] = Field(None, description="Channel username (without @)")
    channel_title: Optional[str] = Field(None, description="Channel title")
    channel_link: Optional[str] = Field(None, description="Channel link")
    topic_id: Optional[int] = Field(None, description="Topic ID for supergroups")
    topic_title: Optional[str] = Field(None, description="Topic title")
    is_active: bool = Field(True, description="Whether the channel is actively monitored")
    monitor_all_topics: bool = Field(False, description="Monitor all topics in supergroup")
    monitored_topics: List[int] = Field(default=[], description="List of specific topic IDs to monitor")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    created_by: Optional[int] = Field(None, description="Admin user ID who created this channel subscription")

    @validator('channel_id', pre=True)
    def normalize_channel_id_field(cls, v):
        """Normalize channel_id to standard format"""
        if v is None:
            return v
        return channel_id_to_string(v)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime.datetime: lambda dt: dt.isoformat()
        }

    @classmethod
    def from_db_doc(cls, doc: dict) -> "MonitoredChannel":
        """Create MonitoredChannel from MongoDB document"""
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        return cls(**doc)


class MonitoredChannelCreate(BaseModel):
    """Model for creating monitored channels"""
    channel_input: str = Field(..., description="Channel URL, username, or ID")
    topic_id: Optional[int] = Field(None, description="Specific topic ID to monitor")
    monitor_all_topics: bool = Field(False, description="Monitor all topics in supergroup")


class MonitoredChannelResponse(BaseModel):
    """Model for API responses"""
    id: str
    channel_id: str
    channel_username: Optional[str]
    channel_title: Optional[str]
    channel_link: Optional[str]
    topic_id: Optional[int]
    topic_title: Optional[str]
    is_active: bool
    monitor_all_topics: bool
    monitored_topics: List[int]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: Optional[int]

    @classmethod
    def from_db_doc(cls, doc: dict) -> "MonitoredChannelResponse":
        """Create MonitoredChannelResponse from MongoDB document"""
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        return cls(**doc)




