"""
Simple integration tests for LLM parsing using pytest
"""

import pytest
import json
from unittest.mock import patch
from app.services.llm_service import LLMService
from app.models.telegram import PropertyType, RentalType


class TestLLMParsingSimple:
    """Simple test class for LLM parsing functionality"""
    
    @pytest.fixture
    def llm_service(self):
        """Create LLM service instance for testing"""
        return LLMService()
    
    @pytest.mark.asyncio
    async def test_llm_parsing_basic_apartment(self, llm_service):
        """Test basic apartment parsing"""
        test_text = """🏡 Сдается в аренду 2-х комнатная квартира
📍 Наири Зарьяна 3, рядом с бассейном Gold Gym

🔥 Отопление — Baxi 
🐾 Можно с домашними питомцами
📅 Аренда:
Долгосрочная — 260 000 драм
На месяц — 280 000 драм"""
        
        with patch.object(llm_service, '_call_llm') as mock_llm:
            # Mock LLM response
            mock_response = {
                "is_real_estate": True,
                "parsing_confidence": 0.8,
                "property_type": "apartment",
                "rental_type": "long_term",
                "rooms_count": 2,
                "price": 260000,
                "currency": "AMD",
                "address": "Наири Зарьяна 3",
                "pets_allowed": True,
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
            
            assert result is not None, "Parsing failed"
            assert result.is_real_estate is True
            assert result.property_type == PropertyType.APARTMENT
            assert result.rental_type == RentalType.LONG_TERM
            assert result.rooms_count == 2
            assert result.price == 260000
            assert result.currency == "AMD"
            assert result.address == "Наири Зарьяна 3"
            assert result.pets_allowed is True
            assert result.parsing_confidence >= 0.5
    
    @pytest.mark.asyncio
    async def test_llm_parsing_studio(self, llm_service):
        """Test studio parsing (should be 1 room)"""
        test_text = """Сдаётся в аренду однокомнатная квартира на улице Хоренаци 47.  
        Рядом большой рынок, торговый центр, недалеко парк, метро 🚇. 
        Цена аренды 220.000 драм"""
        
        with patch.object(llm_service, '_call_llm') as mock_llm:
            mock_response = {
                "is_real_estate": True,
                "parsing_confidence": 0.8,
                "property_type": "apartment",
                "rental_type": "long_term",
                "rooms_count": 1,
                "price": 220000,
                "currency": "AMD",
                "address": "ул. Хоренаци 47",
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
            
            result = await llm_service.parse_with_llm(test_text, post_id=2, channel_id=12345)
            
            assert result is not None
            assert result.is_real_estate is True
            assert result.property_type == PropertyType.APARTMENT
            assert result.rooms_count == 1
            assert result.price == 220000
            assert result.currency == "AMD"
            assert result.address == "ул. Хоренаци 47"
    
    @pytest.mark.asyncio
    async def test_llm_parsing_house(self, llm_service):
        """Test house parsing"""
        test_text = """В районе Аван сдается дом,3 комнаты.Отопление бакси,есть место для парковки авто.Цена 180000.033040737."""
        
        with patch.object(llm_service, '_call_llm') as mock_llm:
            mock_response = {
                "is_real_estate": True,
                "parsing_confidence": 0.7,
                "property_type": "house",
                "rental_type": "long_term",
                "rooms_count": 3,
                "price": 180000,
                "currency": "AMD",
                "district": "Аван",
                "has_parking": True,
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
            
            result = await llm_service.parse_with_llm(test_text, post_id=3, channel_id=12345)
            
            assert result is not None
            assert result.is_real_estate is True
            assert result.property_type == PropertyType.HOUSE
            assert result.rooms_count == 3
            assert result.price == 180000
            assert result.currency == "AMD"
            assert result.district == "Аван"
            assert result.has_parking is True
    
    @pytest.mark.asyncio
    async def test_llm_parsing_detailed_apartment(self, llm_service):
        """Test detailed apartment with all features"""
        test_text = """🏠  #2 ком. уютнaя квартира 🔥

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
@gagik_estate"""
        
        with patch.object(llm_service, '_call_llm') as mock_llm:
            mock_response = {
                "is_real_estate": True,
                "parsing_confidence": 0.9,
                "property_type": "apartment",
                "rental_type": "long_term",
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
            
            result = await llm_service.parse_with_llm(test_text, post_id=4, channel_id=12345)
            
            assert result is not None
            assert result.is_real_estate is True
            assert result.property_type == PropertyType.APARTMENT
            assert result.rooms_count == 2
            assert result.area_sqm == 60
            assert result.price == 320000
            assert result.currency == "AMD"
            assert result.address == "Норашен 47/5"
            assert result.district == "Ачапняк"
            assert result.city == "Ереван"
            assert result.floor == 9
            assert result.total_floors == 16
            assert result.has_air_conditioning is True
            assert result.has_internet is True
            assert result.has_furniture is True
            assert "@gagik_estate" in result.contacts
    
    @pytest.mark.asyncio
    async def test_llm_parsing_non_real_estate(self, llm_service):
        """Test that non-real estate content is correctly identified"""
        test_text = "Ищу работу программистом"
        
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
            
            result = await llm_service.parse_with_llm(test_text, post_id=5, channel_id=12345)
            
            # Should return None for non-real estate content
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])