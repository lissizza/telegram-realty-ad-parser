from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LLMCost(BaseModel):
    """Model for tracking LLM costs"""
    
    id: Optional[str] = Field(None, alias="_id")
    post_id: int = Field(..., description="Original post ID")
    channel_id: int = Field(..., description="Original channel ID")
    prompt_tokens: int = Field(..., description="Number of tokens in prompt")
    completion_tokens: int = Field(..., description="Number of tokens in completion")
    total_tokens: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Cost in USD")
    model_name: str = Field(..., description="LLM model used")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }



