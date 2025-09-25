"""
Unit tests for PriceFilter model
"""

import pytest
from datetime import datetime, UTC

from app.models.price_filter import PriceFilter


class TestPriceFilterModel:
    """Test class for PriceFilter model"""

    def test_create_price_filter(self):
        """Test creating a price filter with valid data"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=100000.0,
            max_price=500000.0,
            currency="AMD",
            is_active=True
        )
        
        assert price_filter.filter_id == "test_filter_123"
        assert price_filter.min_price == 100000.0
        assert price_filter.max_price == 500000.0
        assert price_filter.currency == "AMD"
        assert price_filter.is_active is True
        assert isinstance(price_filter.created_at, datetime)
        assert isinstance(price_filter.updated_at, datetime)

    def test_create_price_filter_min_only(self):
        """Test creating a price filter with only min_price"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=100000.0,
            currency="USD"
        )
        
        assert price_filter.min_price == 100000.0
        assert price_filter.max_price is None
        assert price_filter.currency == "USD"
        assert price_filter.is_active is True  # Default value

    def test_create_price_filter_max_only(self):
        """Test creating a price filter with only max_price"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            max_price=1000.0,
            currency="USD"
        )
        
        assert price_filter.min_price is None
        assert price_filter.max_price == 1000.0
        assert price_filter.currency == "USD"

    def test_matches_price_exact_match(self):
        """Test price matching with exact values"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=100000.0,
            max_price=500000.0,
            currency="AMD"
        )
        
        # Exact match
        assert price_filter.matches_price(250000.0, "AMD") is True
        
        # Min boundary
        assert price_filter.matches_price(100000.0, "AMD") is True
        
        # Max boundary
        assert price_filter.matches_price(500000.0, "AMD") is True

    def test_matches_price_out_of_range(self):
        """Test price matching with out-of-range values"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=100000.0,
            max_price=500000.0,
            currency="AMD"
        )
        
        # Too low
        assert price_filter.matches_price(50000.0, "AMD") is False
        
        # Too high
        assert price_filter.matches_price(600000.0, "AMD") is False

    def test_matches_price_currency_mismatch(self):
        """Test price matching with different currency"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=100000.0,
            max_price=500000.0,
            currency="AMD"
        )
        
        # Different currency
        assert price_filter.matches_price(250000.0, "USD") is False
        assert price_filter.matches_price(250000.0, "EUR") is False

    def test_matches_price_none_values(self):
        """Test price matching with None values"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=100000.0,
            max_price=500000.0,
            currency="AMD"
        )
        
        # None price
        assert price_filter.matches_price(None, "AMD") is False
        
        # None currency
        assert price_filter.matches_price(250000.0, None) is False
        
        # Both None
        assert price_filter.matches_price(None, None) is False

    def test_matches_price_min_only_filter(self):
        """Test price matching with min_price only filter"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=200000.0,
            currency="AMD"
        )
        
        # Above min
        assert price_filter.matches_price(300000.0, "AMD") is True
        
        # At min
        assert price_filter.matches_price(200000.0, "AMD") is True
        
        # Below min
        assert price_filter.matches_price(100000.0, "AMD") is False

    def test_matches_price_max_only_filter(self):
        """Test price matching with max_price only filter"""
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            max_price=1000.0,
            currency="USD"
        )
        
        # Below max
        assert price_filter.matches_price(500.0, "USD") is True
        
        # At max
        assert price_filter.matches_price(1000.0, "USD") is True
        
        # Above max
        assert price_filter.matches_price(1500.0, "USD") is False

    def test_validation_min_price_negative(self):
        """Test validation with negative min_price"""
        with pytest.raises(ValueError):
            PriceFilter(
                filter_id="test_filter_123",
                min_price=-100.0,
                currency="AMD"
            )

    def test_validation_max_price_negative(self):
        """Test validation with negative max_price"""
        with pytest.raises(ValueError):
            PriceFilter(
                filter_id="test_filter_123",
                max_price=-100.0,
                currency="AMD"
            )

    def test_validation_min_price_greater_than_max(self):
        """Test validation when min_price > max_price"""
        # This should be allowed at model level, validation happens in business logic
        price_filter = PriceFilter(
            filter_id="test_filter_123",
            min_price=500000.0,
            max_price=100000.0,
            currency="AMD"
        )
        
        # The model allows it, but business logic should handle validation
        assert price_filter.min_price == 500000.0
        assert price_filter.max_price == 100000.0
