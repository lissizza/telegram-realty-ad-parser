"""
Tests for Yandex Maps integration in Telegram messages
"""

import pytest
from unittest.mock import MagicMock

from app.services.telegram_service import TelegramService
from app.models.telegram import RealEstateAd, PropertyType, RentalType


class TestYandexMapsIntegration:
    """Test class for Yandex Maps integration"""

    @pytest.fixture
    def telegram_service(self):
        """Create TelegramService instance for testing"""
        return TelegramService()

    @pytest.fixture
    def sample_ad_with_address(self):
        """Sample real estate ad with address"""
        return RealEstateAd(
            original_post_id=1,
            original_channel_id=12345,
            original_message="Test apartment with address",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            area_sqm=60,
            price=250000,
            currency="AMD",
            district="Центр",
            city="Ереван",
            address="ул. Абовяна, 15",
            parsing_confidence=0.9,
        )

    @pytest.fixture
    def sample_ad_without_city(self):
        """Sample real estate ad without city"""
        return RealEstateAd(
            original_post_id=2,
            original_channel_id=12345,
            original_message="Test apartment without city",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=1,
            area_sqm=35,
            price=150000,
            currency="AMD",
            district="Арабкир",
            address="ул. Туманяна, 8",
            parsing_confidence=0.8,
        )

    def test_get_yandex_maps_link_with_city(self, telegram_service):
        """Test Yandex Maps link generation with city"""
        address = "ул. Абовяна, 15"
        district = "Центр"
        city = "Ереван"
        
        link = telegram_service._get_yandex_maps_link(address, district, city)
        
        assert link is not None
        assert "yandex.ru/maps" in link
        assert "text=" in link
        # Check that the link contains URL-encoded address components
        import urllib.parse
        assert urllib.parse.unquote(link).find("ул. Абовяна, 15") != -1
        assert urllib.parse.unquote(link).find("Центр") != -1
        assert urllib.parse.unquote(link).find("Ереван") != -1

    def test_get_yandex_maps_link_without_city(self, telegram_service):
        """Test Yandex Maps link generation without city (defaults to Yerevan)"""
        address = "ул. Туманяна, 8"
        district = "Арабкир"
        
        link = telegram_service._get_yandex_maps_link(address, district)
        
        assert link is not None
        assert "yandex.ru/maps" in link
        assert "text=" in link
        # Check that the link contains URL-encoded address components
        import urllib.parse
        assert urllib.parse.unquote(link).find("ул. Туманяна, 8") != -1
        assert urllib.parse.unquote(link).find("Арабкир") != -1
        assert urllib.parse.unquote(link).find("Ереван") != -1

    def test_get_yandex_maps_link_address_only(self, telegram_service):
        """Test Yandex Maps link generation with address only"""
        address = "ул. Маштоца, 25"
        
        link = telegram_service._get_yandex_maps_link(address)
        
        assert link is not None
        assert "yandex.ru/maps" in link
        assert "text=" in link
        # Check that the link contains URL-encoded address components
        import urllib.parse
        assert urllib.parse.unquote(link).find("ул. Маштоца, 25") != -1
        assert urllib.parse.unquote(link).find("Ереван") != -1  # Should default to Yerevan

    def test_get_yandex_maps_link_empty_address(self, telegram_service):
        """Test Yandex Maps link generation with empty address"""
        link = telegram_service._get_yandex_maps_link("")
        
        assert link is None

    def test_get_yandex_maps_link_none_address(self, telegram_service):
        """Test Yandex Maps link generation with None address"""
        link = telegram_service._get_yandex_maps_link(None)
        
        assert link is None

    def test_get_yandex_maps_link_special_characters(self, telegram_service):
        """Test Yandex Maps link generation with special characters"""
        address = "ул. Абовяна, д. 15, кв. 25"
        district = "Центр"
        city = "Ереван"
        
        link = telegram_service._get_yandex_maps_link(address, district, city)
        
        assert link is not None
        assert "yandex.ru/maps" in link
        # Special characters should be URL encoded
        assert "%" in link  # URL encoding should be present

    @pytest.mark.asyncio
    async def test_format_message_includes_city(self, telegram_service, sample_ad_with_address):
        """Test that formatted message includes city field"""
        message = await telegram_service._format_real_estate_message(sample_ad_with_address, None)
        
        assert "Город:" in message
        assert "Ереван" in message

    @pytest.mark.asyncio
    async def test_format_message_includes_yandex_maps_link(self, telegram_service, sample_ad_with_address):
        """Test that formatted message includes Yandex Maps link"""
        message = await telegram_service._format_real_estate_message(sample_ad_with_address, None)
        
        assert "Посмотреть на карте" in message
        assert "yandex.ru/maps" in message
        assert "text=" in message  # URL parameter should be present

    @pytest.mark.asyncio
    async def test_format_message_without_city_defaults_to_yerevan(self, telegram_service, sample_ad_without_city):
        """Test that formatted message defaults to Yerevan when city is not specified"""
        message = await telegram_service._format_real_estate_message(sample_ad_without_city, None)
        
        # Should not include city field if city is None
        assert "Город:" not in message
        # But Yandex Maps link should still work with default city
        assert "Посмотреть на карте" in message
        assert "yandex.ru/maps" in message

    @pytest.mark.asyncio
    async def test_format_message_without_address_no_map_link(self, telegram_service):
        """Test that formatted message doesn't include map link when address is missing"""
        ad_no_address = RealEstateAd(
            original_post_id=3,
            original_channel_id=12345,
            original_message="Test apartment without address",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=3,
            area_sqm=80,
            price=300000,
            currency="AMD",
            district="Центр",
            city="Ереван",
            # No address field
            parsing_confidence=0.9,
        )
        
        message = await telegram_service._format_real_estate_message(ad_no_address, None)
        
        assert "Посмотреть на карте" not in message
        assert "yandex.ru/maps" not in message
        assert "Город:" in message  # City should still be shown
