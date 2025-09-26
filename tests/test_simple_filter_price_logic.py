"""
Unit tests for SimpleFilter price filtering logic
"""

import pytest
from app.models.simple_filter import SimpleFilter
from app.models.price_filter import PriceFilter
from app.models.telegram import RealEstateAd, PropertyType, RentalType


class TestSimpleFilterPriceLogic:
    """Test price filtering logic in SimpleFilter"""

    @pytest.fixture
    def base_filter(self):
        """Create a base filter for testing"""
        return SimpleFilter(
            id="test_filter_123",
            user_id=12345,
            name="Test Filter",
            property_types=[PropertyType.APARTMENT],
            rental_types=[RentalType.LONG_TERM],
            min_rooms=2,
            max_rooms=3
        )

    @pytest.fixture
    def price_filters(self):
        """Create price filters for testing"""
        return [
            PriceFilter(
                id="price_filter_1",
                filter_id="test_filter_123",
                min_price=50000,
                max_price=150000,
                currency="AMD"
            )
        ]

    @pytest.fixture
    def multiple_price_filters(self):
        """Create multiple price filters for OR logic testing"""
        return [
            PriceFilter(
                id="price_filter_1",
                filter_id="test_filter_123",
                min_price=50000,
                max_price=100000,
                currency="AMD"
            ),
            PriceFilter(
                id="price_filter_2",
                filter_id="test_filter_123",
                min_price=200000,
                max_price=300000,
                currency="AMD"
            )
        ]

    @pytest.fixture
    def ad_with_matching_price(self):
        """Ad with price that matches price filter"""
        return RealEstateAd(
            id="ad_1",
            original_post_id=1,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=100000,
            currency="AMD"
        )

    @pytest.fixture
    def ad_with_non_matching_price(self):
        """Ad with price that doesn't match price filter"""
        return RealEstateAd(
            id="ad_2",
            original_post_id=2,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=200000,  # Too high
            currency="AMD"
        )

    @pytest.fixture
    def ad_without_price(self):
        """Ad without price information"""
        return RealEstateAd(
            id="ad_3",
            original_post_id=3,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=None,
            currency=None
        )

    @pytest.fixture
    def ad_with_different_currency(self):
        """Ad with price in different currency"""
        return RealEstateAd(
            id="ad_4",
            original_post_id=4,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=1000,  # USD
            currency="USD"
        )

    def test_filter_without_price_restrictions_passes_all_ads(self, base_filter, ad_with_matching_price, ad_without_price):
        """Test that filter without price restrictions passes all ads regardless of price"""
        # Filter without price restrictions should pass all ads
        assert base_filter.matches_with_price_filters(ad_with_matching_price, []) is True
        assert base_filter.matches_with_price_filters(ad_without_price, []) is True

    def test_filter_with_price_restrictions_matches_correct_prices(self, base_filter, price_filters, ad_with_matching_price, ad_with_non_matching_price):
        """Test that filter with price restrictions matches correct prices"""
        # Ad with matching price should pass
        assert base_filter.matches_with_price_filters(ad_with_matching_price, price_filters) is True
        
        # Ad with non-matching price should fail
        assert base_filter.matches_with_price_filters(ad_with_non_matching_price, price_filters) is False

    def test_ads_without_price_pass_through_price_filters(self, base_filter, price_filters, ad_without_price):
        """Test that ads without price pass through filters with price restrictions"""
        # Ad without price should pass (no price restriction)
        assert base_filter.matches_with_price_filters(ad_without_price, price_filters) is True

    def test_different_currency_does_not_match(self, base_filter, price_filters, ad_with_different_currency):
        """Test that ads with different currency don't match price filters"""
        # Ad with different currency should not match
        assert base_filter.matches_with_price_filters(ad_with_different_currency, price_filters) is False

    def test_multiple_price_filters_or_logic(self, base_filter, multiple_price_filters, ad_with_matching_price, ad_without_price):
        """Test that multiple price filters work with OR logic"""
        # Create ad that matches first range
        ad_first_range = RealEstateAd(
            id="ad_5",
            original_post_id=5,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=75000,  # In first range (50k-100k)
            currency="AMD"
        )
        
        # Create ad that matches second range
        ad_second_range = RealEstateAd(
            id="ad_6",
            original_post_id=6,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=250000,  # In second range (200k-300k)
            currency="AMD"
        )
        
        # Create ad that matches neither range
        ad_no_range = RealEstateAd(
            id="ad_7",
            original_post_id=7,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=150000,  # Not in any range
            currency="AMD"
        )
        
        # Both ads in ranges should pass (OR logic)
        assert base_filter.matches_with_price_filters(ad_first_range, multiple_price_filters) is True
        assert base_filter.matches_with_price_filters(ad_second_range, multiple_price_filters) is True
        
        # Ad in no range should fail
        assert base_filter.matches_with_price_filters(ad_no_range, multiple_price_filters) is False
        
        # Ad without price should still pass
        assert base_filter.matches_with_price_filters(ad_without_price, multiple_price_filters) is True

    def test_price_filter_edge_cases(self, base_filter):
        """Test edge cases for price filtering"""
        # Test with empty price filters list
        ad = RealEstateAd(
            id="ad_edge",
            original_post_id=8,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=100000,
            currency="AMD"
        )
        
        # Empty price filters should pass
        assert base_filter.matches_with_price_filters(ad, []) is True
        
        # Test with None price filters
        assert base_filter.matches_with_price_filters(ad, None) is True

    def test_price_filter_boundary_values(self, base_filter):
        """Test price filter boundary values"""
        price_filters = [
            PriceFilter(
                id="price_filter_boundary",
                filter_id="test_filter_123",
                min_price=100000,
                max_price=100000,  # Exact match
                currency="AMD"
            )
        ]
        
        # Ad with exact boundary price should match
        ad_exact = RealEstateAd(
            id="ad_exact",
            original_post_id=9,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=100000,
            currency="AMD"
        )
        
        # Ad with price just below boundary should not match
        ad_below = RealEstateAd(
            id="ad_below",
            original_post_id=10,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=99999,
            currency="AMD"
        )
        
        # Ad with price just above boundary should not match
        ad_above = RealEstateAd(
            id="ad_above",
            original_post_id=11,
            original_channel_id=-1001234567890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            price=100001,
            currency="AMD"
        )
        
        assert base_filter.matches_with_price_filters(ad_exact, price_filters) is True
        assert base_filter.matches_with_price_filters(ad_below, price_filters) is False
        assert base_filter.matches_with_price_filters(ad_above, price_filters) is False
