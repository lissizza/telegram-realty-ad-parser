from datetime import datetime, UTC
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.telegram import PropertyType, RentalType
from app.models.price_filter import PriceFilter


class SimpleFilter(BaseModel):
    """Simplified filter model for exact field matching"""
    id: Optional[str] = None
    user_id: int  # Telegram user ID who owns this filter
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
    
    # Price criteria are now handled by separate PriceFilter models
    # This allows multiple price ranges with different currencies per filter
    
    # Location criteria
    districts: List[str] = []
    
    # Channel filtering
    channel_ids: List[str] = []  # List of channel IDs to filter by (empty = all channels)
    
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    def matches(self, ad) -> bool:
        """Check if ad matches this filter"""
        # Property type match
        if self.property_types and ad.property_type not in self.property_types:
            print(f"DEBUG: Property type mismatch - ad.property_type={ad.property_type}, filter.property_types={self.property_types}")
            return False
        
        # Rental type match
        if self.rental_types and ad.rental_type not in self.rental_types:
            print(f"DEBUG: Rental type mismatch - ad.rental_type={ad.rental_type}, filter.rental_types={self.rental_types}")
            return False
        
        # Room count match
        if ad.rooms_count is not None:
            if self.min_rooms is not None and ad.rooms_count < self.min_rooms:
                print(f"DEBUG: Room count too low - ad.rooms_count={ad.rooms_count}, filter.min_rooms={self.min_rooms}")
                return False
            if self.max_rooms is not None and ad.rooms_count > self.max_rooms:
                print(f"DEBUG: Room count too high - ad.rooms_count={ad.rooms_count}, filter.max_rooms={self.max_rooms}")
                return False
        
        # Area match
        if ad.area_sqm is not None:
            if self.min_area is not None and ad.area_sqm < self.min_area:
                return False
            if self.max_area is not None and ad.area_sqm > self.max_area:
                return False
        
        # Price matching is now handled by PriceFilter models
        # This method will be updated to work with price_filters parameter
        
        # District match
        if self.districts and ad.district:
            if ad.district.lower() not in [d.lower() for d in self.districts]:
                return False
        
        # Channel match
        if self.channel_ids:
            # Convert ad.channel_id to string for comparison
            ad_channel_id = str(ad.original_channel_id)
            if ad_channel_id not in self.channel_ids:
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
                # If filter specifies True, ad must have this feature (True)
                # If filter specifies False, ad must NOT have this feature (False or None)
                if required_value is True:
                    # Ad must have this feature (True)
                    if ad_value is not True:
                        print(f"DEBUG: Feature {feature} should be True but ad has {ad_value}")
                        return False
                elif required_value is False:
                    # Ad should not have this feature (False or None is OK)
                    if ad_value is True:
                        print(f"DEBUG: Feature {feature} should be False/None but ad has True")
                        return False
        
        return True
    
    def matches_with_price_filters(self, ad, price_filters: List[PriceFilter]) -> bool:
        """Check if ad matches this filter including price filters"""
        # First check all non-price criteria
        if not self.matches(ad):
            return False
        
        # If no price filters, skip price matching
        if not price_filters:
            return True
        
        # Check if ad price matches any of the price filters
        if ad.price is not None and ad.currency is not None:
            for price_filter in price_filters:
                if price_filter.matches_price(ad.price, ad.currency):
                    return True
            # If we have price filters but none matched, return False
            return False
        
        # If ad has no price info, it doesn't match price filters
        return False



