"""
Unit tests for TelegramService filter name display functionality
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.telegram_service import TelegramService
from app.models.telegram import RealEstateAd, PropertyType, RentalType


class TestTelegramServiceFilterDisplay:
    """Test filter name display in TelegramService"""

    @pytest.fixture
    def telegram_service(self):
        """Create TelegramService instance for testing"""
        return TelegramService()

    @pytest.fixture
    def sample_ad(self):
        """Create a sample real estate ad for testing"""
        return RealEstateAd(
            id="test_ad_123",
            original_post_id=12345,
            original_channel_id=-1001234567890,
            original_topic_id=2629,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            area_sqm=50.0,
            price=100000,
            currency="AMD",
            district="Центр",
            city="Ереван",
            address="ул. Абовяна, 15",
            contacts=["+37412345678"],
            parsing_confidence=0.95
        )

    @pytest.mark.asyncio
    async def test_format_message_with_filter_name(self, telegram_service, sample_ad):
        """Test that filter name is displayed when provided"""
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, "filter_123", "Мой тестовый фильтр"
        )
        
        assert "Мой тестовый фильтр" in message
        assert "🎯 Активный фильтр:" in message

    @pytest.mark.asyncio
    async def test_format_message_without_filter_info(self, telegram_service, sample_ad):
        """Test that no filter info is displayed when not provided"""
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, None, None
        )
        
        assert "🎯 Активный фильтр:" not in message

    @pytest.mark.asyncio
    async def test_format_message_with_unknown_filter_id(self, telegram_service, sample_ad):
        """Test that unknown filter ID is handled gracefully"""
        # Mock the _get_filter_name method to return a default name
        telegram_service._get_filter_name = AsyncMock(return_value="Неизвестный фильтр")
        
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, "unknown_filter", None
        )
        
        assert "Неизвестный фильтр" in message
        assert "🎯 Активный фильтр:" in message

    @pytest.mark.asyncio
    async def test_format_message_skips_unknown_filter_id(self, telegram_service, sample_ad):
        """Test that 'unknown' filter ID is skipped"""
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, "unknown", None
        )
        
        assert "🎯 Активный фильтр:" not in message

    @pytest.mark.asyncio
    async def test_format_message_with_clickable_address(self, telegram_service, sample_ad):
        """Test that address is clickable with Yandex Maps link"""
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, None, None
        )
        
        # Check that address is clickable (contains markdown link)
        assert "ул\\. Абовяна, 15" in message
        assert "yandex.ru/maps" in message
        assert "[" in message and "]" in message  # Markdown link format

    @pytest.mark.asyncio
    async def test_format_message_without_address(self, telegram_service):
        """Test message formatting when ad has no address"""
        ad_no_address = RealEstateAd(
            id="test_ad_no_address",
            original_post_id=12346,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=100000,
            currency="AMD"
        )
        
        message = await telegram_service._format_real_estate_message(
            ad_no_address, None, None, None
        )
        
        # Should not contain address or map link
        assert "Адрес:" not in message
        assert "yandex.ru/maps" not in message

    @pytest.mark.asyncio
    async def test_format_message_priority_filter_name_over_id(self, telegram_service, sample_ad):
        """Test that filter name takes priority over filter ID"""
        # Mock _get_filter_name to return something different
        telegram_service._get_filter_name = AsyncMock(return_value="Filter from DB")
        
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, "filter_123", "Provided Filter Name"
        )
        
        # Should use provided name, not the one from DB
        assert "Provided Filter Name" in message
        assert "Filter from DB" not in message
        # _get_filter_name should not be called when filter_name is provided
        telegram_service._get_filter_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_format_message_fallback_to_filter_id(self, telegram_service, sample_ad):
        """Test fallback to filter ID when filter name is not provided"""
        telegram_service._get_filter_name = AsyncMock(return_value="Filter from DB")
        
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, "filter_123", None
        )
        
        # Should use name from DB
        assert "Filter from DB" in message
        telegram_service._get_filter_name.assert_called_once_with("filter_123")

    @pytest.mark.asyncio
    async def test_format_message_handles_empty_strings(self, telegram_service, sample_ad):
        """Test that empty strings are handled properly"""
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, "", ""
        )
        
        # Should not display filter info for empty strings
        assert "🎯 Активный фильтр:" not in message

    @pytest.mark.asyncio
    async def test_format_message_handles_none_values(self, telegram_service, sample_ad):
        """Test that None values are handled properly"""
        message = await telegram_service._format_real_estate_message(
            sample_ad, None, None, None
        )
        
        # Should not display filter info for None values
        assert "🎯 Активный фильтр:" not in message
