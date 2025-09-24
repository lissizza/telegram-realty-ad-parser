import re
import logging
from typing import Optional, List

from app.core.config import settings
from app.models.telegram import RealEstateAd, PropertyType, RentalType
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ParserService:
    def __init__(self):
        self.llm_service = LLMService() if settings.ENABLE_LLM_PARSING else None
        # Keywords for property types
        self.property_keywords = {
            PropertyType.APARTMENT: [
                "квартира", "кв", "апартамент", "жилье"
            ],
            PropertyType.HOUSE: [
                "дом", "коттедж", "вилла", "таунхаус"
            ],
            PropertyType.ROOM: [
                "комната", "жилье", "кровать"
            ],
            PropertyType.HOTEL_ROOM: [
                "номер", "отель", "гостиница", "посуточно"
            ]
        }
        
        # Keywords for rental types
        self.rental_keywords = {
            RentalType.LONG_TERM: [
                "долгосрочно", "долгосрочная", "на длительный срок",
                "постоянно", "месяц", "месячная"
            ],
            RentalType.DAILY: [
                "посуточно", "по дням", "на день", "краткосрочно"
            ]
        }
        
        # District keywords
        self.district_keywords = [
            "центр", "кентрон", "арабкир", "малатия", "эребуни",
            "шахумян", "канакер-зеитун", "аван", "нор-норк",
            "давидашен", "ачапняк", "наири", "шенгавит"
        ]

    async def parse_real_estate_ad(
        self, incoming_message
    ) -> Optional[RealEstateAd]:
        """Parse text as real estate advertisement"""
        try:
            # Extract data from incoming message
            text = incoming_message.message
            post_id = incoming_message.id  # Telegram ID
            channel_id = incoming_message.channel_id
            # Get the MongoDB ID (this should be set by telegram_service.py)
            incoming_message_id = getattr(incoming_message, '_id', None)  # MongoDB ObjectId
            
            # Use LLM if available, otherwise fall back to rule-based parsing
            if self.llm_service:
                logger.info(f"Using LLM parsing for post {post_id}")
                return await self.llm_service.parse_with_llm(text, post_id, channel_id, incoming_message_id, incoming_message.topic_id)
            else:
                logger.info(f"Using rule-based parsing for post {post_id}")
                return await self._parse_with_rules(text, post_id, channel_id, incoming_message_id, incoming_message.topic_id)

        except Exception as e:
            logger.error(f"Error parsing real estate ad: {e}")
            return None
    
    async def _parse_with_rules(
        self, text: str, post_id: int, channel_id: int, incoming_message_id: str = None, topic_id: int = None
    ) -> Optional[RealEstateAd]:
        """Fallback rule-based parsing"""
        try:
            # Since we're monitoring a specific real estate subchannel,
            # we assume all messages are real estate ads
            # No need for keyword filtering

            # Create base ad object
            ad = RealEstateAd(
                incoming_message_id=incoming_message_id,
                original_post_id=post_id,
                original_channel_id=channel_id,
                original_topic_id=topic_id,
                original_message=text
            )

            # Parse different components
            ad.property_type = self._parse_property_type(text)
            ad.rental_type = self._parse_rental_type(text)
            ad.rooms_count = self._parse_rooms_count(text)
            ad.area_sqm = self._parse_area(text)
            ad.price_amd, ad.price_usd = self._parse_price(text)
            ad.district = self._parse_district(text)
            ad.address = self._parse_address(text)
            ad.contacts = self._parse_contacts(text)
            
            # Parse features
            ad.has_balcony = self._has_feature(text, ["балкон", "лоджия"])
            ad.has_air_conditioning = self._has_feature(
                text, ["кондиционер", "сплит"]
            )
            ad.has_internet = self._has_feature(text, ["интернет", "wifi", "wi-fi"])
            ad.has_furniture = self._has_feature(
                text, ["мебель", "обставлена", "оборудована"]
            )
            ad.has_parking = self._has_feature(text, ["парковка", "гараж"])
            ad.has_garden = self._has_feature(text, ["сад", "огород"])
            ad.has_pool = self._has_feature(text, ["бассейн", "пруд"])

            # Calculate confidence
            ad.parsing_confidence = self._calculate_confidence(ad)

            return ad

        except Exception as e:
            logger.error(f"Error in rule-based parsing: {e}")
            return None

    def _is_real_estate_ad(self, text: str) -> bool:
        """Check if text looks like a real estate advertisement"""
        # Since we're monitoring a specific real estate subchannel,
        # we assume all messages are real estate ads
        return True

    def _parse_property_type(self, text: str) -> Optional[PropertyType]:
        """Parse property type from text"""
        text_lower = text.lower()
        
        for prop_type, keywords in self.property_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return prop_type
        
        return None

    def _parse_rental_type(self, text: str) -> Optional[RentalType]:
        """Parse rental type from text"""
        text_lower = text.lower()
        
        for rental_type, keywords in self.rental_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return rental_type
        
        return None

    def _parse_rooms_count(self, text: str) -> Optional[int]:
        """Parse number of rooms from text"""
        # Patterns for room count
        patterns = [
            r'(\d+)[-х]?комнатн',  # 3-комнатная, 3х комнатная
            r'(\d+)\s*комнат',     # 3 комнат
            r'(\d+)\s*к',          # 3 к
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None

    def _parse_area(self, text: str) -> Optional[float]:
        """Parse area in square meters from text"""
        # Patterns for area
        patterns = [
            r'(\d+(?:\.\d+)?)\s*кв\.?м',  # 45 кв.м
            r'(\d+(?:\.\d+)?)\s*м²',      # 45 м²
            r'(\d+(?:\.\d+)?)\s*кв',      # 45 кв
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        return None

    def _parse_price(self, text: str) -> tuple[Optional[int], Optional[float]]:
        """Parse price in AMD and USD from text"""
        price_amd = None
        price_usd = None
        
        # AMD patterns
        amd_patterns = [
            r'(\d+(?:,\d+)*)\s*драм',
            r'(\d+(?:,\d+)*)\s*др',
            r'(\d+(?:,\d+)*)\s*₽',
        ]
        
        for pattern in amd_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '')
                price_amd = int(price_str)
                break
        
        # USD patterns
        usd_patterns = [
            r'\$(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*usd',
            r'(\d+(?:\.\d+)?)\s*доллар',
        ]
        
        for pattern in usd_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_usd = float(match.group(1))
                break
        
        return price_amd, price_usd

    def _parse_district(self, text: str) -> Optional[str]:
        """Parse district from text"""
        text_lower = text.lower()
        
        for district in self.district_keywords:
            if district in text_lower:
                return district.title()
        
        return None

    def _parse_address(self, text: str) -> Optional[str]:
        """Parse address from text"""
        # Look for street patterns
        patterns = [
            r'ул\.?\s*([^,\n]+)',
            r'улица\s+([^,\n]+)',
            r'адрес[:\s]+([^,\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def _parse_contacts(self, text: str) -> List[str]:
        """Parse contact information from text"""
        contacts = []
        
        # Phone number patterns
        phone_patterns = [
            r'\+374\d{8}',  # Armenian phone format
            r'0\d{8}',      # Local format
            r'\d{10}',      # 10 digits
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            contacts.extend(matches)
        
        # Telegram username patterns
        username_patterns = [
            r'@[\w_]+',
            r'telegram[:\s]+@?([\w_]+)',
        ]
        
        for pattern in username_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            contacts.extend([f"@{match}" for match in matches])
        
        return list(set(contacts))  # Remove duplicates

    def _has_feature(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains feature keywords"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)

    def _calculate_confidence(self, ad: RealEstateAd) -> float:
        """Calculate parsing confidence score"""
        confidence = 0.0
        
        # Base confidence for being a real estate ad
        confidence += 0.3
        
        # Add confidence for each parsed field
        if ad.property_type:
            confidence += 0.1
        if ad.rooms_count:
            confidence += 0.1
        if ad.price_amd or ad.price_usd:
            confidence += 0.2
        if ad.district:
            confidence += 0.1
        if ad.address:
            confidence += 0.1
        if ad.contacts:
            confidence += 0.1
        
        return min(confidence, 1.0)
    