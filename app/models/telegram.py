from datetime import datetime
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
    
    # Filter matching metadata
    matched_filters: List[str] = []  # List of filter IDs that this ad matches
    should_forward: bool = False  # Whether this ad should be forwarded to user
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ForwardedPost(BaseModel):
    """Model for forwarded posts"""
    id: Optional[str] = None
    original_post_id: int
    original_channel_id: int
    real_estate_ad_id: Optional[str] = None
    filter_id: str
    forwarded_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "forwarded"  # forwarded, failed, pending


class Channel(BaseModel):
    """Model for Telegram channels"""
    id: int
    title: str
    username: Optional[str] = None
    is_monitored: bool = True
    is_real_estate_channel: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
