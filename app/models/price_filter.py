from datetime import datetime, UTC
from typing import Optional
from pydantic import BaseModel, Field


class PriceFilter(BaseModel):
    """Model for price filtering criteria linked to a SimpleFilter"""
    
    id: Optional[str] = None
    filter_id: str = Field(..., description="ID of the parent SimpleFilter")
    min_price: Optional[float] = Field(None, ge=0, description="Minimum price")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price")
    currency: str = Field(..., description="Currency code (AMD, USD, EUR, etc.)")
    is_active: bool = Field(default=True, description="Whether this price filter is active")
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def matches_price(self, price: Optional[float], currency: Optional[str]) -> bool:
        """Check if given price and currency match this price filter"""
        if price is None or currency is None:
            return False
            
        # Currency must match exactly
        if currency != self.currency:
            return False
            
        # Check price range
        if self.min_price is not None and price < self.min_price:
            return False
        if self.max_price is not None and price > self.max_price:
            return False
            
        return True
