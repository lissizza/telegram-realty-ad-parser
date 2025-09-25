"""
Unit tests for SimpleFilterService with price filters integration
"""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

import pytest

from app.models.simple_filter import SimpleFilter
from app.models.telegram import PropertyType, RealEstateAd, RentalType
from app.models.price_filter import PriceFilter
from app.services.simple_filter_service import SimpleFilterService


class TestSimpleFilterServiceWithPriceFilters:
    """Test class for SimpleFilterService with price filters"""

    @pytest.fixture
    def service(self):
        """Create service instance for testing"""
        return SimpleFilterService()

    @pytest.fixture
    def sample_apartment_ad(self):
        """Sample apartment advertisement for testing"""
        return RealEstateAd(
            original_post_id=1,
            original_channel_id=12345,
            original_message="Test apartment",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            area_sqm=60,
            price=250000,
            currency="AMD",
            district="Центр",
            city="Ереван",
            has_balcony=True,
            has_air_conditioning=True,
            has_internet=True,
            has_furniture=True,
            pets_allowed=True,
            parsing_confidence=0.9,
        )

    @pytest.fixture
    def sample_filter(self):
        """Sample filter for testing"""
        return SimpleFilter(
            id="test_filter_123",
            name="Test Filter",
            user_id=123456789,
            property_types=[PropertyType.APARTMENT],
            rental_types=[RentalType.LONG_TERM],
            min_rooms=2,
            max_rooms=3,
            is_active=True
        )

    @pytest.fixture
    def sample_price_filters(self):
        """Sample price filters for testing"""
        return [
            PriceFilter(
                id="price_filter_1",
                filter_id="test_filter_123",
                min_price=200000.0,
                max_price=300000.0,
                currency="AMD",
                is_active=True
            ),
            PriceFilter(
                id="price_filter_2",
                filter_id="test_filter_123",
                min_price=200.0,
                max_price=1000.0,
                currency="USD",
                is_active=True
            )
        ]

    @pytest.mark.asyncio
    async def test_check_filters_with_price_filters_matching(self, service, sample_apartment_ad, sample_filter, sample_price_filters):
        """Test check_filters when price filters match"""
        with patch.object(service, 'get_active_filters', return_value=[sample_filter]), \
             patch.object(service.price_filter_service, 'get_price_filters_by_filter_id', return_value=sample_price_filters), \
             patch('app.services.simple_filter_service.UserFilterMatchService') as mock_match_service:
            
            mock_match_service.return_value.create_match.return_value = "match_id_123"
            
            result = await service.check_filters(sample_apartment_ad, user_id=123456789)
            
            assert result["should_forward"] is True
            assert len(result["matching_filters"]) == 1
            assert "test_filter_123" in result["matching_filters"]
            assert len(result["created_matches"]) == 1

    @pytest.mark.asyncio
    async def test_check_filters_with_price_filters_non_matching(self, service, sample_apartment_ad, sample_filter):
        """Test check_filters when price filters don't match"""
        # Price filter that doesn't match the ad (250k AMD)
        non_matching_price_filters = [
            PriceFilter(
                id="price_filter_1",
                filter_id="test_filter_123",
                min_price=500000.0,
                max_price=600000.0,
                currency="AMD",
                is_active=True
            )
        ]
        
        with patch.object(service, 'get_active_filters', return_value=[sample_filter]), \
             patch.object(service.price_filter_service, 'get_price_filters_by_filter_id', return_value=non_matching_price_filters), \
             patch('app.services.simple_filter_service.UserFilterMatchService') as mock_match_service:
            
            result = await service.check_filters(sample_apartment_ad, user_id=123456789)
            
            assert result["should_forward"] is False
            assert len(result["matching_filters"]) == 0
            assert len(result["created_matches"]) == 0

    @pytest.mark.asyncio
    async def test_check_filters_without_price_filters(self, service, sample_apartment_ad, sample_filter):
        """Test check_filters when no price filters exist"""
        with patch.object(service, 'get_active_filters', return_value=[sample_filter]), \
             patch.object(service.price_filter_service, 'get_price_filters_by_filter_id', return_value=[]), \
             patch('app.services.simple_filter_service.UserFilterMatchService') as mock_match_service:
            
            mock_match_service.return_value.create_match.return_value = "match_id_123"
            
            result = await service.check_filters(sample_apartment_ad, user_id=123456789)
            
            assert result["should_forward"] is True
            assert len(result["matching_filters"]) == 1
            assert "test_filter_123" in result["matching_filters"]

    @pytest.mark.asyncio
    async def test_check_filters_multiple_currencies_one_matches(self, service, sample_apartment_ad, sample_filter):
        """Test check_filters with multiple currency filters where one matches"""
        multiple_currency_filters = [
            PriceFilter(
                id="price_filter_1",
                filter_id="test_filter_123",
                min_price=500000.0,
                max_price=600000.0,
                currency="AMD",  # Won't match
                is_active=True
            ),
            PriceFilter(
                id="price_filter_2",
                filter_id="test_filter_123",
                min_price=200.0,
                max_price=300.0,
                currency="USD",  # Won't match
                is_active=True
            ),
            PriceFilter(
                id="price_filter_3",
                filter_id="test_filter_123",
                min_price=200000.0,
                max_price=300000.0,
                currency="AMD",  # Will match
                is_active=True
            )
        ]
        
        with patch.object(service, 'get_active_filters', return_value=[sample_filter]), \
             patch.object(service.price_filter_service, 'get_price_filters_by_filter_id', return_value=multiple_currency_filters), \
             patch('app.services.simple_filter_service.UserFilterMatchService') as mock_match_service:
            
            mock_match_service.return_value.create_match.return_value = "match_id_123"
            
            result = await service.check_filters(sample_apartment_ad, user_id=123456789)
            
            assert result["should_forward"] is True
            assert len(result["matching_filters"]) == 1

    @pytest.mark.asyncio
    async def test_check_filters_no_price_in_ad(self, service, sample_filter, sample_price_filters):
        """Test check_filters when ad has no price information"""
        # Create ad without price
        ad_no_price = RealEstateAd(
            original_post_id=1,
            original_channel_id=12345,
            original_message="Test apartment",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            area_sqm=60,
            price=None,  # No price
            currency=None,  # No currency
            district="Центр",
            city="Ереван",
            has_balcony=True,
            parsing_confidence=0.9,
        )
        
        with patch.object(service, 'get_active_filters', return_value=[sample_filter]), \
             patch.object(service.price_filter_service, 'get_price_filters_by_filter_id', return_value=sample_price_filters), \
             patch('app.services.simple_filter_service.UserFilterMatchService') as mock_match_service:
            
            result = await service.check_filters(ad_no_price, user_id=123456789)
            
            assert result["should_forward"] is False
            assert len(result["matching_filters"]) == 0

    @pytest.mark.asyncio
    async def test_check_filters_filter_doesnt_match_other_criteria(self, service, sample_apartment_ad, sample_price_filters):
        """Test check_filters when filter doesn't match other criteria"""
        # Filter that doesn't match property type
        non_matching_filter = SimpleFilter(
            id="test_filter_123",
            name="Test Filter",
            user_id=123456789,
            property_types=[PropertyType.HOUSE],  # Different property type
            rental_types=[RentalType.LONG_TERM],
            min_rooms=2,
            max_rooms=3,
            is_active=True
        )
        
        with patch.object(service, 'get_active_filters', return_value=[non_matching_filter]), \
             patch.object(service.price_filter_service, 'get_price_filters_by_filter_id', return_value=sample_price_filters), \
             patch('app.services.simple_filter_service.UserFilterMatchService') as mock_match_service:
            
            result = await service.check_filters(sample_apartment_ad, user_id=123456789)
            
            assert result["should_forward"] is False
            assert len(result["matching_filters"]) == 0

    @pytest.mark.asyncio
    async def test_check_filters_inactive_price_filter(self, service, sample_apartment_ad, sample_filter):
        """Test check_filters with inactive price filter"""
        inactive_price_filters = [
            PriceFilter(
                id="price_filter_1",
                filter_id="test_filter_123",
                min_price=200000.0,
                max_price=300000.0,
                currency="AMD",
                is_active=False  # Inactive
            )
        ]
        
        with patch.object(service, 'get_active_filters', return_value=[sample_filter]), \
             patch.object(service.price_filter_service, 'get_price_filters_by_filter_id', return_value=inactive_price_filters), \
             patch('app.services.simple_filter_service.UserFilterMatchService') as mock_match_service:
            
            result = await service.check_filters(sample_apartment_ad, user_id=123456789)
            
            # Should match based on other criteria since price filter is inactive
            assert result["should_forward"] is True
            assert len(result["matching_filters"]) == 1

    @pytest.mark.asyncio
    async def test_check_filters_exception_handling(self, service, sample_apartment_ad):
        """Test check_filters exception handling"""
        with patch.object(service, 'get_active_filters', side_effect=Exception("Database error")):
            
            result = await service.check_filters(sample_apartment_ad, user_id=123456789)
            
            assert result["should_forward"] is False
            assert len(result["matching_filters"]) == 0
            assert len(result["created_matches"]) == 0
