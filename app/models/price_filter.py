from datetime import datetime, UTC
from typing import Optional
from pydantic import BaseModel, Field
from app.models.telegram import Currency


class PriceFilter(BaseModel):
    """Model for price filtering criteria linked to a SimpleFilter"""
    
    filter_id: str = Field(..., description="ID of the parent SimpleFilter")
    min_price: Optional[float] = Field(None, ge=0, description="Minimum price")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price")
    currency: Currency = Field(..., description="Currency code")
    is_active: bool = Field(default=True, description="Whether this price filter is active")
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def matches_price(self, price: Optional[float], currency) -> bool:
        """Check if given price and currency match this price filter"""
        if price is None or currency is None:
            return False
        
        # Convert currency to string for comparison (handle both enum and string)
        currency_str = currency.value if hasattr(currency, 'value') else str(currency)
        filter_currency_str = self.currency.value if hasattr(self.currency, 'value') else str(self.currency)
            
        # Currency must match exactly
        if currency_str != filter_currency_str:
            return False
            
        # Check price range
        if self.min_price is not None and price < self.min_price:
            return False
        if self.max_price is not None and price > self.max_price:
            return False
            
        return True
