"""
Unit tests for PriceFilterService
"""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

import pytest

from app.models.price_filter import PriceFilter
from app.services.price_filter_service import PriceFilterService


class TestPriceFilterService:
    """Test class for PriceFilterService"""

    @pytest.fixture
    def service(self):
        """Create service instance for testing"""
        return PriceFilterService()

    @pytest.fixture
    def sample_price_filter(self):
        """Sample price filter for testing"""
        return PriceFilter(
            filter_id="test_filter_123",
            min_price=100000.0,
            max_price=500000.0,
            currency="AMD",
            is_active=True
        )

    @pytest.fixture
    def mock_database(self):
        """Mock database for testing"""
        with patch('app.services.price_filter_service.mongodb') as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            yield mock_db

    @pytest.mark.asyncio
    async def test_create_price_filter(self, service, sample_price_filter, mock_database):
        """Test creating a price filter"""
        mock_result = AsyncMock()
        mock_result.inserted_id = "new_id_123"
        mock_database.price_filters.insert_one.return_value = mock_result
        
        result = await service.create_price_filter(sample_price_filter)
        
        assert result == "new_id_123"
        mock_database.price_filters.insert_one.assert_called_once()
        
        # Check that the inserted data has timestamps
        call_args = mock_database.price_filters.insert_one.call_args[0][0]
        assert "created_at" in call_args
        assert "updated_at" in call_args

    @pytest.mark.asyncio
    async def test_get_price_filters_by_filter_id(self, service, mock_database):
        """Test getting price filters by filter ID"""
        mock_cursor = AsyncMock()
        mock_cursor.find.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__aiter__.return_value = [
            {
                "_id": "id1",
                "filter_id": "test_filter_123",
                "min_price": 100000.0,
                "max_price": 500000.0,
                "currency": "AMD",
                "is_active": True,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC)
            },
            {
                "_id": "id2",
                "filter_id": "test_filter_123",
                "min_price": 200.0,
                "max_price": 1000.0,
                "currency": "USD",
                "is_active": True,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC)
            }
        ]
        mock_database.price_filters = mock_cursor
        
        result = await service.get_price_filters_by_filter_id("test_filter_123")
        
        assert len(result) == 2
        assert all(isinstance(pf, PriceFilter) for pf in result)
        assert result[0].currency == "AMD"
        assert result[1].currency == "USD"

    @pytest.mark.asyncio
    async def test_get_price_filters_by_filter_id_empty(self, service, mock_database):
        """Test getting price filters when none exist"""
        mock_cursor = AsyncMock()
        mock_cursor.find.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__aiter__.return_value = []
        mock_database.price_filters = mock_cursor
        
        result = await service.get_price_filters_by_filter_id("test_filter_123")
        
        assert result == []

    @pytest.mark.asyncio
    async def test_update_price_filter(self, service, mock_database):
        """Test updating a price filter"""
        mock_database.price_filters.update_one.return_value.modified_count = 1
        
        update_data = {"min_price": 200000.0, "is_active": False}
        result = await service.update_price_filter("507f1f77bcf86cd799439011", update_data)  # Valid ObjectId
        
        assert result is True
        mock_database.price_filters.update_one.assert_called_once()
        
        # Check that updated_at is set
        call_args = mock_database.price_filters.update_one.call_args[0]
        assert "$set" in call_args[1]
        assert "updated_at" in call_args[1]["$set"]

    @pytest.mark.asyncio
    async def test_update_price_filter_not_found(self, service, mock_database):
        """Test updating a non-existent price filter"""
        mock_database.price_filters.update_one.return_value.modified_count = 0
        
        update_data = {"min_price": 200000.0}
        result = await service.update_price_filter("507f1f77bcf86cd799439012", update_data)  # Valid ObjectId
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_price_filter(self, service, mock_database):
        """Test deleting a price filter"""
        mock_database.price_filters.update_one.return_value.modified_count = 1
        
        result = await service.delete_price_filter("507f1f77bcf86cd799439011")  # Valid ObjectId
        
        assert result is True
        mock_database.price_filters.update_one.assert_called_once()
        
        # Check that is_active is set to False
        call_args = mock_database.price_filters.update_one.call_args[0]
        assert call_args[1]["$set"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_delete_price_filter_not_found(self, service, mock_database):
        """Test deleting a non-existent price filter"""
        mock_database.price_filters.update_one.return_value.modified_count = 0
        
        result = await service.delete_price_filter("507f1f77bcf86cd799439012")  # Valid ObjectId
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_price_filters_by_filter_id(self, service, mock_database):
        """Test deleting all price filters for a filter"""
        mock_result = AsyncMock()
        mock_result.modified_count = 3
        mock_database.price_filters.update_many.return_value = mock_result
        
        result = await service.delete_price_filters_by_filter_id("test_filter_123")
        
        assert result == 3
        mock_database.price_filters.update_many.assert_called_once()
        
        # Check that is_active is set to False
        call_args = mock_database.price_filters.update_many.call_args[0]
        assert call_args[1]["$set"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_create_price_filter_exception(self, service, sample_price_filter, mock_database):
        """Test creating a price filter with exception"""
        mock_database.price_filters.insert_one.side_effect = Exception("Database error")
        
        with pytest.raises(Exception):
            await service.create_price_filter(sample_price_filter)

    @pytest.mark.asyncio
    async def test_get_price_filters_exception(self, service, mock_database):
        """Test getting price filters with exception"""
        mock_database.price_filters.find.side_effect = Exception("Database error")
        
        result = await service.get_price_filters_by_filter_id("test_filter_123")
        
        assert result == []
