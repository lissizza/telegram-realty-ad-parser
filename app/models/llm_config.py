"""
LLM Configuration model for storing LLM provider configurations in database.
"""

from datetime import datetime, UTC
from typing import Optional
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Model for LLM provider configuration"""
    
    name: str = Field(..., description="Display name for this LLM configuration")
    provider: str = Field(..., description="Provider type: openai, anthropic, zai, local, mock")
    model: str = Field(..., description="Model name (e.g., gpt-3.5-turbo, glm-4.6)")
    base_url: Optional[str] = Field(None, description="Base URL for API (for local models or custom endpoints)")
    encrypted_api_key: str = Field(..., description="Encrypted API key")
    max_tokens: int = Field(default=1000, description="Maximum tokens for LLM response")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="Temperature for LLM generation")
    is_active: bool = Field(default=False, description="Whether this configuration is currently active")
    is_default: bool = Field(default=False, description="Whether this is the default configuration")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: Optional[int] = Field(None, description="User ID who created this configuration")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }





