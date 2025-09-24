"""
Real integration tests for LLM parsing - no mocking, real API calls
"""

import pytest
import asyncio
from app.services.llm_service import LLMService
from app.models.telegram import PropertyType, RentalType


class TestLLMIntegration:
    """Real integration tests that call actual LLM API"""
    
    @pytest.fixture
    def llm_service(self):
        """Create LLM service instance for testing"""
        return LLMService()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_llm_parsing_apartment(self, llm_service):
        """Test real LLM parsing of apartment advertisement"""
        test_text = """🏡 Сдается в аренду 2-х комнатная квартира
📍 Наири Зарьяна 3, рядом с бассейном Gold Gym

🔥 Отопление — Baxi 
🐾 Можно с домашними питомцами
📅 Аренда:
Долгосрочная — 260 000 драм
На месяц — 280 000 драм"""
        
        result = await llm_service.parse_with_llm(test_text, post_id=1, channel_id=12345)
        
        # These are real assertions based on what LLM should actually return
        assert result is not None, "LLM should parse this as real estate"
        assert result.is_real_estate is True
        assert result.property_type == PropertyType.APARTMENT
        assert result.rental_type == RentalType.LONG_TERM
        assert result.rooms_count == 2
        # LLM might choose either long-term (260k) or monthly (280k) price
        assert result.price in [260000, 280000]
        assert result.currency == "AMD"
        assert "Наири Зарьяна" in result.address
        assert result.pets_allowed is True
        assert result.parsing_confidence > 0.5
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_llm_parsing_studio(self, llm_service):
        """Test real LLM parsing of studio apartment"""
        test_text = """Сдаётся в аренду однокомнатная квартира на улице Хоренаци 47.  
        Рядом большой рынок, торговый центр, недалеко парк, метро 🚇. 
        Цена аренды 220.000 драм"""
        
        result = await llm_service.parse_with_llm(test_text, post_id=2, channel_id=12345)
        
        assert result is not None
        assert result.is_real_estate is True
        assert result.property_type == PropertyType.APARTMENT
        assert result.rooms_count == 1  # Studio should be 1 room
        assert result.price == 220000
        assert result.currency == "AMD"
        assert "Хоренаци" in result.address
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_llm_parsing_house(self, llm_service):
        """Test real LLM parsing of house"""
        test_text = """В районе Аван сдается дом,3 комнаты.Отопление бакси,есть место для парковки авто.Цена 180000.033040737."""
        
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
    @pytest.mark.slow
    async def test_real_llm_parsing_detailed_apartment(self, llm_service):
        """Test real LLM parsing of detailed apartment with all features"""
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
        
        result = await llm_service.parse_with_llm(test_text, post_id=4, channel_id=12345)
        
        assert result is not None
        assert result.is_real_estate is True
        assert result.property_type == PropertyType.APARTMENT
        assert result.rooms_count == 2
        assert result.area_sqm == 60
        assert result.price == 320000
        assert result.currency == "AMD"
        assert "Норашен" in result.address
        assert result.district == "Ачапняк"
        assert result.city == "Ереван"
        assert result.floor == 9
        assert result.total_floors == 16
        assert result.has_air_conditioning is True
        assert result.has_internet is True
        assert result.has_furniture is True
        assert "@gagik_estate" in result.contacts
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_llm_parsing_non_real_estate(self, llm_service):
        """Test real LLM parsing of non-real estate content"""
        test_text = "Ищу работу программистом"
        
        result = await llm_service.parse_with_llm(test_text, post_id=5, channel_id=12345)
        
        # Should return None for non-real estate content
        assert result is None
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_llm_parsing_ambiguous_cases(self, llm_service):
        """Test real LLM parsing of ambiguous cases"""
        test_cases = [
            ("Квартира с кондиционером, мебелью, парковкой. Без животных, с балконом. Лифт есть.", 
             {"has_air_conditioning": True, "has_furniture": True, "has_parking": True, 
              "pets_allowed": False, "has_balcony": True, "rooms_count": None}),
            ("Сдается 3к квартира, 5/9 этаж, 55кв.м, Москва, район Измайлово, 45000₽/мес, мебель, без животных",
             {"rooms_count": 3, "area_sqm": 55, "floor": 5, "total_floors": 9, 
              "city": "Москва", "district": "Измайлово", "has_furniture": True, "pets_allowed": False})
        ]
        
        for text, expected in test_cases:
            result = await llm_service.parse_with_llm(text, post_id=6, channel_id=12345)
            
            assert result is not None, f"Failed to parse: {text}"
            
            for field, expected_value in expected.items():
                actual_value = getattr(result, field)
                assert actual_value == expected_value, f"Field {field}: expected {expected_value}, got {actual_value} for text: {text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "slow"])
