from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field

from app.models.telegram import PropertyType, RentalType


class SearchMode(str, Enum):
    """Search mode enumeration"""
    NATURAL_LANGUAGE = "natural_language"  # Произвольный запрос
    STRUCTURED = "structured"  # Структурированный поиск


class SearchSettings(BaseModel):
    """Model for search settings"""
    id: Optional[str] = None
    name: str
    mode: SearchMode = SearchMode.STRUCTURED
    
    # Natural language search
    natural_language_query: Optional[str] = None
    
    # Structured search criteria
    property_types: List[PropertyType] = []
    rental_types: List[RentalType] = []
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    min_price_amd: Optional[int] = None
    max_price_amd: Optional[int] = None
    min_price_usd: Optional[float] = None
    max_price_usd: Optional[float] = None
    districts: List[str] = []
    
    # Additional criteria
    keywords: List[str] = []
    exclude_keywords: List[str] = []
    
    # LLM settings for this search
    llm_prompt_template: Optional[str] = None
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Status
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_llm_prompt(self) -> str:
        """Generate LLM prompt based on search settings"""
        if self.mode == SearchMode.NATURAL_LANGUAGE:
            return self._generate_natural_language_prompt()
        else:
            return self._generate_structured_prompt()
    
    def _generate_natural_language_prompt(self) -> str:
        """Generate prompt for natural language search"""
        base_prompt = f"""
Parse the following real estate advertisement and check if it matches this search criteria:

SEARCH QUERY: {self.natural_language_query}

Extract the following information and return as JSON:
{{
    "matches_search": boolean,
    "match_confidence": number (0.0-1.0),
    "property_type": "apartment|house|room|hotel_room",
    "rental_type": "long_term|daily",
    "rooms_count": number,
    "area_sqm": number,
    "price_amd": number,
    "price_usd": number,
    "district": "string",
    "address": "string",
    "contacts": ["phone1", "phone2", "@username"],
    "has_balcony": boolean,
    "has_air_conditioning": boolean,
    "has_internet": boolean,
    "has_furniture": boolean,
    "has_parking": boolean,
    "has_garden": boolean,
    "has_pool": boolean,
    "parsing_confidence": number (0.0-1.0)
}}

Rules:
- If information is not available, use null
- For boolean fields, use true/false
- For arrays, use empty array [] if no data
- Extract phone numbers in format +374XXXXXXXXX or 0XXXXXXXX
- Extract Telegram usernames as @username
- For districts, use standard Yerevan district names
- Be conservative with confidence scores
- Only return matches_search=true if the ad clearly matches the search criteria
"""
        return base_prompt
    
    def _generate_structured_prompt(self) -> str:
        """Generate prompt for structured search"""
        criteria_parts = []
        
        if self.property_types:
            types_str = "|".join([pt.value for pt in self.property_types])
            criteria_parts.append(f"Property type: {types_str}")
        
        if self.rental_types:
            rental_str = "|".join([rt.value for rt in self.rental_types])
            criteria_parts.append(f"Rental type: {rental_str}")
        
        if self.min_rooms is not None or self.max_rooms is not None:
            room_criteria = []
            if self.min_rooms is not None:
                room_criteria.append(f"at least {self.min_rooms} rooms")
            if self.max_rooms is not None:
                room_criteria.append(f"at most {self.max_rooms} rooms")
            criteria_parts.append(f"Rooms: {' and '.join(room_criteria)}")
        
        if self.min_area is not None or self.max_area is not None:
            area_criteria = []
            if self.min_area is not None:
                area_criteria.append(f"at least {self.min_area} sqm")
            if self.max_area is not None:
                area_criteria.append(f"at most {self.max_area} sqm")
            criteria_parts.append(f"Area: {' and '.join(area_criteria)}")
        
        if self.min_price_amd is not None or self.max_price_amd is not None:
            price_criteria = []
            if self.min_price_amd is not None:
                price_criteria.append(f"at least {self.min_price_amd} AMD")
            if self.max_price_amd is not None:
                price_criteria.append(f"at most {self.max_price_amd} AMD")
            criteria_parts.append(f"Price (AMD): {' and '.join(price_criteria)}")
        
        if self.min_price_usd is not None or self.max_price_usd is not None:
            price_criteria = []
            if self.min_price_usd is not None:
                price_criteria.append(f"at least ${self.min_price_usd}")
            if self.max_price_usd is not None:
                price_criteria.append(f"at most ${self.max_price_usd}")
            criteria_parts.append(f"Price (USD): {' and '.join(price_criteria)}")
        
        if self.districts:
            criteria_parts.append(f"Districts: {', '.join(self.districts)}")
        
        if self.keywords:
            criteria_parts.append(f"Must contain: {', '.join(self.keywords)}")
        
        if self.exclude_keywords:
            criteria_parts.append(f"Must NOT contain: {', '.join(self.exclude_keywords)}")
        
        criteria_text = "\n".join(criteria_parts) if criteria_parts else "No specific criteria"
        
        prompt = f"""
Parse the following real estate advertisement and check if it matches these search criteria:

SEARCH CRITERIA:
{criteria_text}

Extract the following information and return as JSON:
{{
    "matches_search": boolean,
    "match_confidence": number (0.0-1.0),
    "property_type": "apartment|house|room|hotel_room",
    "rental_type": "long_term|daily",
    "rooms_count": number,
    "area_sqm": number,
    "price_amd": number,
    "price_usd": number,
    "district": "string",
    "address": "string",
    "contacts": ["phone1", "phone2", "@username"],
    "has_balcony": boolean,
    "has_air_conditioning": boolean,
    "has_internet": boolean,
    "has_furniture": boolean,
    "has_parking": boolean,
    "has_garden": boolean,
    "has_pool": boolean,
    "parsing_confidence": number (0.0-1.0)
}}

Rules:
- If information is not available, use null
- For boolean fields, use true/false
- For arrays, use empty array [] if no data
- Extract phone numbers in format +374XXXXXXXXX or 0XXXXXXXX
- Extract Telegram usernames as @username
- For districts, use standard Yerevan district names
- Be conservative with confidence scores
- Only return matches_search=true if the ad clearly matches ALL specified criteria
- match_confidence should reflect how well the ad matches the criteria (0.0-1.0)
"""
        return prompt

