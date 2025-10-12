from datetime import datetime, UTC
from typing import List, Optional

from pydantic import BaseModel, Field


class UserChannelSelection(BaseModel):
    """Model for user's selected channels from monitored channels"""
    id: Optional[str] = None
    user_id: int
    channel_id: str  # MonitoredChannel ID (not Telegram channel ID)
    is_selected: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserChannelSelectionCreate(BaseModel):
    """Model for creating user channel selections"""
    user_id: int
    channel_id: str
    is_selected: bool = True


class UserChannelSelectionResponse(BaseModel):
    """Model for API responses"""
    id: str
    user_id: int
    channel_id: str
    is_selected: bool
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
            channel_id=doc["channel_id"],
            is_selected=doc.get("is_selected", True),
            created_at=doc.get("created_at", datetime.now(UTC)),
            updated_at=doc.get("updated_at", datetime.now(UTC))
        )


class UserChannelSelectionBulkUpdate(BaseModel):
    """Model for bulk updating user channel selections"""
    user_id: int
    selected_channel_ids: List[str]  # List of MonitoredChannel IDs that user wants to monitor





