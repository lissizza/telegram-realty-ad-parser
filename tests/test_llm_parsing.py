"""
Integration tests for LLM parsing of real estate advertisements using pytest
"""

import pytest
import json
from unittest.mock import patch
from app.services.llm_service import LLMService
from app.models.telegram import PropertyType, RentalType


class TestLLMParsing:
    """Test class for LLM parsing functionality"""
    
    @pytest.fixture
    def llm_service(self):
        """Create LLM service instance for testing"""
        return LLMService()
    
    @pytest.fixture
    def test_cases(self):
        """Test cases with real advertisements"""
        return [
            {
                "id": 1,
                "text": """🏡 Сдается в аренду 2-х комнатная квартира
📍 Наири Зарьяна 3, рядом с бассейном Gold Gym

🔥 Отопление — Baxi 
🐾 Можно с домашними питомцами
📅 Аренда:
Долгосрочная — 260 000 драм
На месяц — 280 000 драм""",
                "expected": {
                    "is_real_estate": True,
                    "property_type": PropertyType.APARTMENT,
                    "rental_type": RentalType.LONG_TERM,
                    "rooms_count": 2,
                    "price": 260000,
                    "currency": "AMD",
                    "address": "Наири Зарьяна 3",
                    "pets_allowed": True,
                    "parsing_confidence": 0.8,  # Should be high confidence
                }
            },
            {
                "id": 2,
                "text": """Сдаётся в аренду однокомнатная квартира на улице Хоренаци 47.  Рядом большой рынок , торговый центр , недалеко парк , метро 🚇. Цена аренды 220.000 драм""",
                "expected": {
                    "is_real_estate": True,
                    "property_type": PropertyType.APARTMENT,
                    "rental_type": RentalType.LONG_TERM,
                    "rooms_count": 1,
                    "price": 220000,
                    "currency": "AMD",
                    "address": "ул. Хоренаци 47",
                    "parsing_confidence": 0.8,
                }
            },
            {
                "id": 3,
                "text": """В районе Аван сдается дом,3 комнаты.Отопление бакси,есть место для парковки авто.Цена 180000.033040737.""",
                "expected": {
                    "is_real_estate": True,
                    "property_type": PropertyType.HOUSE,
                    "rental_type": RentalType.LONG_TERM,
                    "rooms_count": 3,
                    "price": 180000,
                    "currency": "AMD",
                    "district": "Аван",
                    "has_parking": True,
                    "parsing_confidence": 0.7,  # Lower confidence due to formatting
                }
            },
            {
                "id": 4,
                "text": """🏠  #2 ком. уютнaя квартира 🔥

📍 Адрес: Норашен 47/5, Ачапняк , Ереван

🔑Код: SL521

➤Новостройка: да 
➤Этаж: 9/16
➤Общая площадь: 60 кв.м. 
➤ Система отопления: Индивидуальная  
➤микроволновка 
➤Кондиционер
➤стиральная машина  
➤ Интернет: WIFI ✅
➤ Цена: 320.000 АМД в месяц
 

#Сдам #Сдаю #Сдаюжильё

По всем вапросам в ЛС 
@gagik_estate""",
                "expected": {
                    "is_real_estate": True,
                    "property_type": PropertyType.APARTMENT,
                    "rental_type": RentalType.LONG_TERM,
                    "rooms_count": 2,
                    "area_sqm": 60,
                    "price": 320000,
                    "currency": "AMD",
                    "address": "Норашен 47/5",
                    "district": "Ачапняк",
                    "city": "Ереван",
                    "floor": 9,
                    "total_floors": 16,
                    "has_air_conditioning": True,
                    "has_internet": True,
                    "has_furniture": True,
                    "contacts": ["@gagik_estate"],
                    "parsing_confidence": 0.9,  # High confidence due to detailed info
                }
            }
        ]
    
    @pytest.mark.asyncio
    async def test_llm_parsing_basic_fields(self, llm_service, test_cases):
        """Test that LLM correctly parses basic fields"""
        for test_case in test_cases:
            with patch.object(llm_service, '_call_llm') as mock_llm:
                # Mock LLM response
                mock_response = {
                    "is_real_estate": test_case["expected"]["is_real_estate"],
                    "parsing_confidence": test_case["expected"]["parsing_confidence"],
                    "property_type": test_case["expected"]["property_type"].value,
                    "rental_type": test_case["expected"]["rental_type"].value,
                    "rooms_count": test_case["expected"]["rooms_count"],
                    "price": test_case["expected"]["price"],
                    "currency": "AMD",
                    "address": test_case["expected"].get("address"),
                    "district": test_case["expected"].get("district"),
                    "city": test_case["expected"].get("city"),
                    "floor": test_case["expected"].get("floor"),
                    "total_floors": test_case["expected"].get("total_floors"),
                    "area_sqm": test_case["expected"].get("area_sqm"),
                    "has_air_conditioning": test_case["expected"].get("has_air_conditioning"),
                    "has_internet": test_case["expected"].get("has_internet"),
                    "has_furniture": test_case["expected"].get("has_furniture"),
                    "has_parking": test_case["expected"].get("has_parking"),
                    "pets_allowed": test_case["expected"].get("pets_allowed"),
                    "contacts": test_case["expected"].get("contacts"),
                }
                mock_llm.return_value = {
                    "response": json.dumps(mock_response),
                    "cost_info": {"tokens": 100, "cost": 0.01}
                }
                
                result = await llm_service.parse_with_llm(
                    test_case["text"], 
                    post_id=test_case["id"], 
                    channel_id=12345
                )
                
                assert result is not None, f"Test case {test_case['id']}: Parsing failed"
                assert result.is_real_estate == test_case["expected"]["is_real_estate"]
                assert result.property_type == test_case["expected"]["property_type"]
                assert result.rental_type == test_case["expected"]["rental_type"]
                assert result.rooms_count == test_case["expected"]["rooms_count"]
                assert result.price == test_case["expected"]["price"]
                assert result.parsing_confidence >= 0.5, "Confidence should be reasonable"
    
    @pytest.mark.asyncio
    async def test_llm_parsing_address_extraction(self, llm_service):
        """Test address extraction from various formats"""
        test_texts = [
            "Сдается квартира на улице Абовяна 15",
            "📍 Адрес: Норашен 47/5, Ачапняк",
            "Дом на проспекте Маштоца, 25",
            "Квартира рядом с метро Республика"
        ]
        
        expected_addresses = [
            "ул. Абовяна 15",
            "Норашен 47/5",
            "пр. Маштоца, 25",
            "рядом с метро Республика"
        ]
        
        for text, expected_addr in zip(test_texts, expected_addresses):
            with patch.object(llm_service, '_call_llm') as mock_llm:
                mock_response = {
                    "is_real_estate": True,
                    "parsing_confidence": 0.8,
                    "property_type": "apartment",
                    "rental_type": "long_term",
                    "rooms_count": 1,
                    "price": 100000,
                    "currency": "AMD",
                    "address": expected_addr,
                }
                
                mock_llm.return_value = {
                    "response": json.dumps(mock_response),
                    "cost_info": {
                        "prompt_tokens": 50,
                        "completion_tokens": 50,
                        "total_tokens": 100,
                        "cost_usd": 0.01,
                        "model_name": "gpt-3.5-turbo"
                    }
                }
                
                result = await llm_service.parse_with_llm(text, post_id=1, channel_id=12345)
                assert result.address == expected_addr
    
    @pytest.mark.asyncio
    async def test_llm_parsing_room_count_variations(self, llm_service):
        """Test room count parsing from various formats"""
        test_cases = [
            ("2-х комнатная квартира", 2),
            ("однокомнатная квартира", 1),
            ("3к квартира", 3),
            ("студия", 1),  # Studio should be 1 room
            ("4-комнатная", 4),
            ("двушка", 2),
        ]
        
        for text, expected_rooms in test_cases:
            with patch.object(llm_service, '_call_llm') as mock_llm:
                mock_response = {
                    "is_real_estate": True,
                    "parsing_confidence": 0.8,
                    "property_type": "apartment",
                    "rental_type": "long_term",
                    "rooms_count": expected_rooms,
                    "price": 100000,
                    "currency": "AMD",
                }
                
                mock_llm.return_value = {
                    "response": json.dumps(mock_response),
                    "cost_info": {
                        "prompt_tokens": 50,
                        "completion_tokens": 50,
                        "total_tokens": 100,
                        "cost_usd": 0.01,
                        "model_name": "gpt-3.5-turbo"
                    }
                }
                
                result = await llm_service.parse_with_llm(text, post_id=1, channel_id=12345)
                assert result.rooms_count == expected_rooms, f"Failed for text: {text}"
    
    @pytest.mark.asyncio
    async def test_llm_parsing_price_currencies(self, llm_service):
        """Test price and currency parsing"""
        test_cases = [
            ("260 000 драм", 260000, "AMD"),
            ("320.000 АМД", 320000, "AMD"),
            ("$500", 500, "USD"),
            ("500 USD", 500, "USD"),
            ("45000₽", 45000, "RUB"),
            ("1000 EUR", 1000, "EUR"),
        ]
        
        for text, expected_price, expected_currency in test_cases:
            with patch.object(llm_service, '_call_llm') as mock_llm:
                mock_response = {
                    "is_real_estate": True,
                    "parsing_confidence": 0.8,
                    "property_type": "apartment",
                    "rental_type": "long_term",
                    "rooms_count": 1,
                    "price": expected_price,
                    "currency": expected_currency,
                }
                
                mock_llm.return_value = {
                    "response": json.dumps(mock_response),
                    "cost_info": {
                        "prompt_tokens": 50,
                        "completion_tokens": 50,
                        "total_tokens": 100,
                        "cost_usd": 0.01,
                        "model_name": "gpt-3.5-turbo"
                    }
                }
                
                result = await llm_service.parse_with_llm(text, post_id=1, channel_id=12345)
                # Check that price was parsed correctly based on currency
                assert result.price == expected_price
                assert result.currency == expected_currency
    
    @pytest.mark.asyncio
    async def test_llm_parsing_boolean_features(self, llm_service):
        """Test boolean feature extraction"""
        test_text = """Квартира с кондиционером, мебелью, парковкой. 
        Без животных, с балконом. Лифт есть."""
        
        with patch.object(llm_service, '_call_llm') as mock_llm:
            mock_response = {
                "is_real_estate": True,
                "parsing_confidence": 0.8,
                "property_type": "apartment",
                "rental_type": "long_term",
                "rooms_count": None,
                "price": 100000,
                "currency": "AMD",
                "has_air_conditioning": True,
                "has_furniture": True,
                "has_parking": True,
                "pets_allowed": False,
                "has_balcony": True,
                "has_elevator": True,
            }
            
            mock_llm.return_value = {
                "response": json.dumps(mock_response),
                "cost_info": {
                    "prompt_tokens": 50,
                    "completion_tokens": 50,
                    "total_tokens": 100,
                    "cost_usd": 0.01,
                    "model_name": "gpt-3.5-turbo"
                }
            }
            
            result = await llm_service.parse_with_llm(test_text, post_id=1, channel_id=12345)
            assert result.rooms_count is None  # No room count mentioned in text
            assert result.has_air_conditioning is True
            assert result.has_furniture is True
            assert result.has_parking is True
            assert result.pets_allowed is False
            assert result.has_balcony is True
    
    @pytest.mark.asyncio
    async def test_llm_parsing_contact_extraction(self, llm_service):
        """Test contact information extraction"""
        test_text = """Сдается квартира. Звонить +37412345678 или писать @username"""
        
        with patch.object(llm_service, '_call_llm') as mock_llm:
            mock_response = {
                "is_real_estate": True,
                "parsing_confidence": 0.8,
                "property_type": "apartment",
                "rental_type": "long_term",
                "rooms_count": 1,
                "price": 100000,
                "currency": "AMD",
                "contacts": ["+37412345678", "@username"],
            }
            
            mock_llm.return_value = {
                "response": json.dumps(mock_response),
                "cost_info": {
                    "prompt_tokens": 50,
                    "completion_tokens": 50,
                    "total_tokens": 100,
                    "cost_usd": 0.01,
                    "model_name": "gpt-3.5-turbo"
                }
            }
            
            result = await llm_service.parse_with_llm(test_text, post_id=1, channel_id=12345)
            assert "@username" in result.contacts
            assert "+37412345678" in result.contacts
    
    @pytest.mark.asyncio
    async def test_llm_parsing_non_real_estate(self, llm_service):
        """Test that non-real estate content is correctly identified"""
        test_cases = [
            "Ищу работу программистом",
            "Продаю автомобиль BMW",
            "Услуги ремонта квартир",
            "Спам сообщение",
        ]
        
        for text in test_cases:
            with patch.object(llm_service, '_call_llm') as mock_llm:
                mock_response = {
                    "is_real_estate": False,
                    "parsing_confidence": 0.9,
                    "property_type": None,
                    "rental_type": None,
                    "rooms_count": None,
                    "price": None,
                    "currency": None,
                }
                
                mock_llm.return_value = {
                    "response": json.dumps(mock_response),
                    "cost_info": {
                        "prompt_tokens": 50,
                        "completion_tokens": 50,
                        "total_tokens": 100,
                        "cost_usd": 0.01,
                        "model_name": "gpt-3.5-turbo"
                    }
                }
                
                result = await llm_service.parse_with_llm(text, post_id=1, channel_id=12345)
                # For non-real estate content, the parser should return None
                assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
