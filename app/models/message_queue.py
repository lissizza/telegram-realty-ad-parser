"""
Models for message processing queue
"""

from datetime import datetime, UTC
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    """Message processing status"""
    PENDING = "pending"          # Message received, waiting for processing
    PROCESSING = "processing"    # Currently being processed by LLM
    COMPLETED = "completed"      # Successfully processed
    FAILED = "failed"           # Processing failed
    SKIPPED = "skipped"         # Skipped (e.g., not real estate)


class QueuedMessage(BaseModel):
    """Model for messages in processing queue"""
    id: Optional[str] = None
    original_post_id: int
    original_channel_id: int
    original_message: str
    original_url: Optional[str] = None
    
    # Processing metadata
    status: ProcessingStatus = ProcessingStatus.PENDING
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_errors: List[str] = []
    
    # LLM processing results
    llm_processed: bool = False
    llm_cost: Optional[float] = None
    llm_model: Optional[str] = None
    llm_tokens_used: Optional[int] = None
    
    # Parsed data (populated after LLM processing)
    parsed_data: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProcessingResult(BaseModel):
    """Result of message processing"""
    success: bool
    message_id: str
    real_estate_ad_id: Optional[str] = None  # ID of created RealEstateAd
    errors: List[str] = []
    llm_cost: Optional[float] = None
    processing_time_seconds: Optional[float] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
