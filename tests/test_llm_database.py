"""
Unit tests for LLM parsing database operations
"""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from app.services.llm_service import LLMService
from app.models.telegram import PropertyType, RentalType, RealEstateAd


class TestLLMDatabaseOperations:
    """Test class for LLM parsing database operations"""
    
    @pytest.fixture
    def llm_service(self):
        """Create LLM service instance for testing"""
        return LLMService()
    
    @pytest.fixture
    def mock_database(self):
        """Mock database for testing"""
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.real_estate_ads = mock_collection
        mock_db.llm_costs = AsyncMock()
        return mock_db
    
    @pytest.mark.asyncio
    async def test_parse_and_save_basic_apartment(self, llm_service, mock_database):
        """Test parsing and saving basic apartment to database"""
        test_text = """🏡 Сдается в аренду 2-х комнатная квартира
📍 Наири Зарьяна 3, рядом с бассейном Gold Gym

🔥 Отопление — Baxi 
🐾 Можно с домашними питомцами
📅 Аренда:
Долгосрочная — 260 000 драм
На месяц — 280 000 драм"""
        
        # Mock LLM response
        mock_llm_response = {
            "is_real_estate": True,
            "parsing_confidence": 0.9,
            "property_type": "apartment",
            "rental_type": "long_term",
            "rooms_count": 2,
            "price": 280000,  # LLM chose monthly price
            "currency": "AMD",
            "address": "Наири Зарьяна 3",
            "pets_allowed": True,
            "additional_notes": "Multiple prices mentioned: 260k long-term, 280k monthly. Chose monthly price."
        }
        
        with patch.object(llm_service, '_call_llm') as mock_llm, \
             patch('app.db.mongodb.mongodb.get_database', return_value=mock_database), \
             patch.object(llm_service, '_save_real_estate_ad') as mock_save_ad:
            
            mock_llm.return_value = {
                "response": json.dumps(mock_llm_response),
                "cost_info": {
                    "prompt_tokens": 50,
                    "completion_tokens": 50,
                    "total_tokens": 100,
                    "cost_usd": 0.01,
                    "model_name": "gpt-3.5-turbo"
                }
            }
            
            # Parse with LLM
            result = await llm_service.parse_with_llm(test_text, post_id=1, channel_id=12345)
            
            # Verify parsing result
            assert result is not None
            assert result.is_real_estate is True
            assert result.property_type == PropertyType.APARTMENT
            assert result.rental_type == RentalType.LONG_TERM
            assert result.rooms_count == 2
            assert result.price == 280000
            assert result.currency == "AMD"
            assert result.address == "Наири Зарьяна 3"
            assert result.pets_allowed is True
            assert "Multiple prices mentioned" in result.additional_notes
            assert result.parsing_confidence == 0.9
            
            # Verify database operations
            mock_save_ad.assert_called_once()
            mock_database.llm_costs.insert_one.assert_called_once()
            
            # Check what was saved to database
            saved_ad = mock_save_ad.call_args[0][0]
            assert saved_ad.original_post_id == 1
            assert saved_ad.original_channel_id == 12345
            assert saved_ad.property_type == PropertyType.APARTMENT
            assert saved_ad.rooms_count == 2
            assert saved_ad.price == 280000
            assert saved_ad.currency == "AMD"
            assert saved_ad.pets_allowed is True
            assert "Multiple prices mentioned" in saved_ad.additional_notes
    
    @pytest.mark.asyncio
    async def test_parse_and_save_studio_with_ambiguous_room_count(self, llm_service, mock_database):
        """Test parsing studio with ambiguous room count"""
        test_text = """Сдается студия на улице Хоренаци 47.  
        Рядом большой рынок, торговый центр, недалеко парк, метро 🚇. 
        Цена аренды 220.000 драм"""
        
        mock_llm_response = {
            "is_real_estate": True,
            "parsing_confidence": 0.8,
            "property_type": "apartment",
            "rental_type": "long_term",
            "rooms_count": 1,
            "price": 220000,
            "currency": "AMD",
            "address": "ул. Хоренаци 47",
            "additional_notes": "Studio apartment - treated as 1 room. Address normalized from 'улице' to 'ул.'"
        }
        
        with patch.object(llm_service, '_call_llm') as mock_llm, \
             patch('app.db.mongodb.mongodb.get_database', return_value=mock_database), \
             patch.object(llm_service, '_save_real_estate_ad') as mock_save_ad:
            
            mock_llm.return_value = {
                "response": json.dumps(mock_llm_response),
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
            assert result.rooms_count == 1
            assert result.address == "ул. Хоренаци 47"
            assert "Studio apartment" in result.additional_notes
            
            # Verify database save
            mock_save_ad.assert_called_once()
            saved_ad = mock_save_ad.call_args[0][0]
            assert saved_ad.rooms_count == 1
            assert saved_ad.address == "ул. Хоренаци 47"
            assert "Studio apartment" in saved_ad.additional_notes
    
    @pytest.mark.asyncio
    async def test_parse_and_save_detailed_apartment_with_all_fields(self, llm_service, mock_database):
        """Test parsing detailed apartment with all possible fields"""
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
        
        mock_llm_response = {
            "is_real_estate": True,
            "parsing_confidence": 0.95,
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
            "additional_notes": "New building, individual heating system. Contact via Telegram @gagik_estate"
        }
        
        with patch.object(llm_service, '_call_llm') as mock_llm, \
             patch('app.db.mongodb.mongodb.get_database', return_value=mock_database), \
             patch.object(llm_service, '_save_real_estate_ad') as mock_save_ad:
            
            mock_llm.return_value = {
                "response": json.dumps(mock_llm_response),
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
            
            # Verify all fields are saved to database
            mock_save_ad.assert_called_once()
            saved_ad = mock_save_ad.call_args[0][0]
            assert saved_ad.rooms_count == 2
            assert saved_ad.area_sqm == 60
            assert saved_ad.price == 320000
            assert saved_ad.currency == "AMD"
            assert saved_ad.address == "Норашен 47/5"
            assert saved_ad.district == "Ачапняк"
            assert saved_ad.city == "Ереван"
            assert saved_ad.floor == 9
            assert saved_ad.total_floors == 16
            assert saved_ad.has_air_conditioning is True
            assert saved_ad.has_internet is True
            assert saved_ad.has_furniture is True
            assert "@gagik_estate" in saved_ad.contacts
            assert "New building" in saved_ad.additional_notes
    
    @pytest.mark.asyncio
    async def test_parse_and_save_house_with_parking(self, llm_service, mock_database):
        """Test parsing house with parking"""
        test_text = """В районе Аван сдается дом,3 комнаты.Отопление бакси,есть место для парковки авто.Цена 180000.033040737."""
        
        mock_llm_response = {
            "is_real_estate": True,
            "parsing_confidence": 0.7,
            "property_type": "house",
            "rental_type": "long_term",
            "rooms_count": 3,
            "price": 180000,
            "currency": "AMD",
            "district": "Аван",
            "has_parking": True,
            "additional_notes": "Phone number included: 033040737. Baxi heating system mentioned."
        }
        
        with patch.object(llm_service, '_call_llm') as mock_llm, \
             patch('app.db.mongodb.mongodb.get_database', return_value=mock_database), \
             patch.object(llm_service, '_save_real_estate_ad') as mock_save_ad:
            
            mock_llm.return_value = {
                "response": json.dumps(mock_llm_response),
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
            assert result.property_type == PropertyType.HOUSE
            assert result.rooms_count == 3
            assert result.price == 180000
            assert result.currency == "AMD"
            assert result.district == "Аван"
            assert result.has_parking is True
            
            # Verify database save
            mock_save_ad.assert_called_once()
            saved_ad = mock_save_ad.call_args[0][0]
            assert saved_ad.property_type == PropertyType.HOUSE
            assert saved_ad.rooms_count == 3
            assert saved_ad.price == 180000
            assert saved_ad.currency == "AMD"
            assert saved_ad.district == "Аван"
            assert saved_ad.has_parking is True
            assert "Phone number included" in saved_ad.additional_notes
    
    @pytest.mark.asyncio
    async def test_parse_and_save_non_real_estate_returns_none(self, llm_service, mock_database):
        """Test that non-real estate content returns None and doesn't save to database"""
        test_text = "Ищу работу программистом"
        
        mock_llm_response = {
            "is_real_estate": False,
            "parsing_confidence": 0.9,
            "property_type": None,
            "rental_type": None,
            "rooms_count": None,
            "price": None,
            "currency": None,
            "additional_notes": "This is a job posting, not real estate"
        }
        
        with patch.object(llm_service, '_call_llm') as mock_llm, \
             patch('app.db.mongodb.mongodb.get_database', return_value=mock_database), \
             patch.object(llm_service, '_save_real_estate_ad') as mock_save_ad:
            
            mock_llm.return_value = {
                "response": json.dumps(mock_llm_response),
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
            
            # Should not save to database
            mock_save_ad.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_parse_with_ambiguous_room_count_documents_reasoning(self, llm_service, mock_database):
        """Test that ambiguous room count is documented in additional_notes"""
        test_text = """Квартира с кондиционером, мебелью, парковкой. 
        Без животных, с балконом. Лифт есть."""
        
        mock_llm_response = {
            "is_real_estate": True,
            "parsing_confidence": 0.6,
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
            "additional_notes": "Room count not specified in text. Only amenities mentioned. Confidence lowered due to missing key information."
        }
        
        with patch.object(llm_service, '_call_llm') as mock_llm, \
             patch('app.db.mongodb.mongodb.get_database', return_value=mock_database), \
             patch.object(llm_service, '_save_real_estate_ad') as mock_save_ad:
            
            mock_llm.return_value = {
                "response": json.dumps(mock_llm_response),
                "cost_info": {
                    "prompt_tokens": 50,
                    "completion_tokens": 50,
                    "total_tokens": 100,
                    "cost_usd": 0.01,
                    "model_name": "gpt-3.5-turbo"
                }
            }
            
            result = await llm_service.parse_with_llm(test_text, post_id=6, channel_id=12345)
            
            assert result is not None
            assert result.rooms_count is None
            assert result.has_air_conditioning is True
            assert result.has_furniture is True
            assert result.has_parking is True
            assert result.pets_allowed is False
            assert result.has_balcony is True
            assert "Room count not specified" in result.additional_notes
            assert result.parsing_confidence == 0.6
            
            # Verify database save
            mock_save_ad.assert_called_once()
            saved_ad = mock_save_ad.call_args[0][0]
            assert saved_ad.rooms_count is None
            assert saved_ad.has_air_conditioning is True
            assert saved_ad.has_furniture is True
            assert saved_ad.has_parking is True
            assert saved_ad.pets_allowed is False
            assert saved_ad.has_balcony is True
            assert "Room count not specified" in saved_ad.additional_notes
            assert saved_ad.parsing_confidence == 0.6
    
    @pytest.mark.asyncio
    async def test_llm_cost_tracking(self, llm_service, mock_database):
        """Test that LLM costs are properly tracked and saved"""
        test_text = "Сдается квартира за 100000 драм"
        
        mock_llm_response = {
            "is_real_estate": True,
            "parsing_confidence": 0.8,
            "property_type": "apartment",
            "rental_type": "long_term",
            "rooms_count": 1,
            "price": 100000,
            "currency": "AMD"
        }
        
        cost_info = {
            "prompt_tokens": 45,
            "completion_tokens": 35,
            "total_tokens": 80,
            "cost_usd": 0.008,
            "model_name": "gpt-3.5-turbo"
        }
        
        with patch.object(llm_service, '_call_llm') as mock_llm, \
             patch('app.db.mongodb.mongodb.get_database', return_value=mock_database), \
             patch.object(llm_service, '_save_real_estate_ad') as mock_save_ad:
            
            mock_llm.return_value = {
                "response": json.dumps(mock_llm_response),
                "cost_info": cost_info
            }
            
            result = await llm_service.parse_with_llm(test_text, post_id=7, channel_id=12345)
            
            assert result is not None
            
            # Verify cost tracking
            mock_database.llm_costs.insert_one.assert_called_once()
            saved_cost = mock_database.llm_costs.insert_one.call_args[0][0]
            assert saved_cost["post_id"] == 7
            assert saved_cost["channel_id"] == 12345
            assert saved_cost["prompt_tokens"] == 45
            assert saved_cost["completion_tokens"] == 35
            assert saved_cost["total_tokens"] == 80
            assert saved_cost["cost_usd"] == 0.008
            assert saved_cost["model_name"] == "gpt-3.5-turbo"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
