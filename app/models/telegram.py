from datetime import datetime, UTC
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class PropertyType(str, Enum):
    """Property type enumeration"""
    APARTMENT = "apartment"
    HOUSE = "house"
    ROOM = "room"
    HOTEL_ROOM = "hotel_room"


class RentalType(str, Enum):
    """Rental type enumeration"""
    LONG_TERM = "long_term"
    DAILY = "daily"


# TelegramPost removed - use IncomingMessage for incoming messages
# and OutgoingPost for messages we send


class RealEstateAd(BaseModel):
    """Model for parsed real estate advertisement"""
    id: Optional[str] = None
    incoming_message_id: Optional[str] = None  # Link to IncomingMessage
    original_post_id: int
    original_channel_id: int
    original_topic_id: Optional[int] = None  # Topic ID for topic-based channels
    original_message: str
    original_url: Optional[str] = None
    
    # Parsed data
    property_type: Optional[PropertyType] = None
    rental_type: Optional[RentalType] = None
    rooms_count: Optional[int] = None
    area_sqm: Optional[float] = None
    price: Optional[float] = None  # Generic price field
    currency: Optional[str] = None  # Currency code (AMD, USD, RUB, EUR, GBP)
    district: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    contacts: List[str] = []
    
    # Additional features
    has_balcony: Optional[bool] = None
    has_air_conditioning: Optional[bool] = None
    has_internet: Optional[bool] = None
    has_furniture: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_garden: Optional[bool] = None
    has_pool: Optional[bool] = None
    has_elevator: Optional[bool] = None  # Added from LLM prompt
    pets_allowed: Optional[bool] = None
    utilities_included: Optional[bool] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    additional_notes: Optional[str] = None
    
    # Processing status
    processing_status: str = Field(default="pending", description="pending, processing, completed, failed")
    llm_processed: bool = False  # Whether LLM processing is complete
    llm_cost: Optional[float] = None  # Cost of LLM processing in USD
    
    # Parsing metadata
    is_real_estate: bool = True  # Whether this is actually a real estate ad
    parsing_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    parsing_errors: List[str] = []
    
    # Note: Filter matching is now handled separately via UserFilterMatch model
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ForwardedPost(BaseModel):
    """Model for forwarded posts"""
    id: Optional[str] = None
    original_post_id: int
    original_channel_id: int
    real_estate_ad_id: Optional[str] = None
    filter_id: str
    forwarded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "forwarded"  # forwarded, failed, pending
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Channel(BaseModel):
    """Model for Telegram channels"""
    id: Optional[str] = None
    telegram_id: Optional[int] = None  # Telegram channel ID
    title: str
    username: Optional[str] = None
    channel_link: Optional[str] = None  # Full Telegram link
    
    # Topic/Subchannel support
    has_topics: bool = False
    default_topic_id: Optional[int] = None  # Default topic to monitor
    
    # Monitoring settings
    is_monitored: bool = True
    is_real_estate_channel: bool = False
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
