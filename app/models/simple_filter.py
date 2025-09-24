from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.telegram import PropertyType, RentalType


class SimpleFilter(BaseModel):
    """Simplified filter model for exact field matching"""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    
    # Property criteria
    property_types: List[PropertyType] = []
    rental_types: List[RentalType] = []
    
    # Room criteria
    min_rooms: Optional[int] = Field(None, ge=1, le=10)
    max_rooms: Optional[int] = Field(None, ge=1, le=10)
    
    # Area criteria (in square meters)
    min_area: Optional[float] = Field(None, ge=1.0, le=10000.0)
    max_area: Optional[float] = Field(None, ge=1.0, le=10000.0)
    
    # Price criteria (generic)
    min_price: Optional[float] = Field(None, ge=0.0)
    max_price: Optional[float] = Field(None, ge=0.0)
    price_currency: Optional[str] = None  # Filter by specific currency
    
    # Location criteria
    districts: List[str] = []
    
    # Additional features
    has_balcony: Optional[bool] = None
    has_air_conditioning: Optional[bool] = None
    has_internet: Optional[bool] = None
    has_furniture: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_garden: Optional[bool] = None
    has_pool: Optional[bool] = None
    has_elevator: Optional[bool] = None  # Added to match RealEstateAd
    pets_allowed: Optional[bool] = None  # Added to match RealEstateAd
    utilities_included: Optional[bool] = None  # Added to match RealEstateAd
    
    # Status
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def matches(self, ad) -> bool:
        """Check if ad matches this filter"""
        # Property type match
        if self.property_types and ad.property_type not in self.property_types:
            return False
        
        # Rental type match
        if self.rental_types and ad.rental_type not in self.rental_types:
            return False
        
        # Room count match
        if ad.rooms_count is not None:
            if self.min_rooms is not None and ad.rooms_count < self.min_rooms:
                return False
            if self.max_rooms is not None and ad.rooms_count > self.max_rooms:
                return False
        
        # Area match
        if ad.area_sqm is not None:
            if self.min_area is not None and ad.area_sqm < self.min_area:
                return False
            if self.max_area is not None and ad.area_sqm > self.max_area:
                return False
        
        # Price match (generic)
        if ad.price is not None:
            # Check currency if specified
            if self.price_currency and ad.currency != self.price_currency:
                return False
            
            # Check price range
            if self.min_price is not None and ad.price < self.min_price:
                return False
            if self.max_price is not None and ad.price > self.max_price:
                return False
        
        # District match
        if self.districts and ad.district:
            if ad.district.lower() not in [d.lower() for d in self.districts]:
                return False
        
        # Feature matches
        feature_checks = [
            ('has_balcony', self.has_balcony),
            ('has_air_conditioning', self.has_air_conditioning),
            ('has_internet', self.has_internet),
            ('has_furniture', self.has_furniture),
            ('has_parking', self.has_parking),
            ('has_garden', self.has_garden),
            ('has_pool', self.has_pool),
            ('has_elevator', self.has_elevator),
            ('pets_allowed', self.pets_allowed),
            ('utilities_included', self.utilities_included)
        ]
        
        for feature, required_value in feature_checks:
            if required_value is not None:
                ad_value = getattr(ad, feature, None)
                # If filter specifies a value, ad must match exactly
                if ad_value != required_value:
                    return False
        
        return True



