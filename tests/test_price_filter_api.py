"""
Tests for Price Filter API endpoints
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.price_filter import PriceFilter


class TestPriceFilterAPI:
    """Test class for Price Filter API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def sample_price_filter_data(self):
        """Sample price filter data for testing"""
        return {
            "filter_id": "test_filter_123",
            "min_price": 100000.0,
            "max_price": 500000.0,
            "currency": "AMD",
            "is_active": True
        }

    @pytest.fixture
    def sample_price_filter_response(self):
        """Sample price filter response for testing"""
        return {
            "id": "price_filter_123",
            "filter_id": "test_filter_123",
            "min_price": 100000.0,
            "max_price": 500000.0,
            "currency": "AMD",
            "is_active": True,
            "created_at": "2025-09-25T10:00:00.000000",
            "updated_at": "2025-09-25T10:00:00.000000"
        }

    @pytest.mark.asyncio
    async def test_get_price_filters_by_filter_id(self, client, sample_price_filter_response):
        """Test getting price filters by filter ID"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # Mock the service response
            mock_price_filter = PriceFilter(
                id="price_filter_123",
                filter_id="test_filter_123",
                min_price=100000.0,
                max_price=500000.0,
                currency="AMD",
                is_active=True
            )
            mock_service.get_price_filters_by_filter_id.return_value = [mock_price_filter]
            
            response = client.get("/api/v1/price-filters/filters/test_filter_123/price-filters")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["currency"] == "AMD"
            assert data[0]["min_price"] == 100000.0

    @pytest.mark.asyncio
    async def test_get_price_filters_by_filter_id_empty(self, client):
        """Test getting price filters when none exist"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_price_filters_by_filter_id.return_value = []
            
            response = client.get("/api/v1/price-filters/filters/test_filter_123/price-filters")
            
            assert response.status_code == 200
            data = response.json()
            assert data == []

    @pytest.mark.asyncio
    async def test_create_price_filter(self, client, sample_price_filter_data):
        """Test creating a price filter"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.create_price_filter.return_value = "new_price_filter_id"
            
            response = client.post(
                "/api/v1/price-filters/price-filters",
                json=sample_price_filter_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "new_price_filter_id"
            assert "message" in data

    @pytest.mark.asyncio
    async def test_create_price_filter_validation_error(self, client):
        """Test creating a price filter with validation error"""
        invalid_data = {
            "filter_id": "test_filter_123",
            "min_price": 500000.0,
            "max_price": 100000.0,  # min > max
            "currency": "AMD"
        }
        
        response = client.post(
            "/api/v1/price-filters/price-filters",
            json=invalid_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "min_price cannot be greater than max_price" in data["detail"]

    @pytest.mark.asyncio
    async def test_create_price_filter_no_price_specified(self, client):
        """Test creating a price filter with no price specified"""
        invalid_data = {
            "filter_id": "test_filter_123",
            "currency": "AMD"
            # No min_price or max_price
        }
        
        response = client.post(
            "/api/v1/price-filters/price-filters",
            json=invalid_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "At least one of min_price or max_price must be specified" in data["detail"]

    @pytest.mark.asyncio
    async def test_update_price_filter(self, client):
        """Test updating a price filter"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.update_price_filter.return_value = True
            
            update_data = {
                "min_price": 200000.0,
                "is_active": False
            }
            
            response = client.put(
                "/api/v1/price-filters/price-filters/price_filter_123",
                json=update_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_update_price_filter_not_found(self, client):
        """Test updating a non-existent price filter"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.update_price_filter.return_value = False
            
            update_data = {
                "min_price": 200000.0
            }
            
            response = client.put(
                "/api/v1/price-filters/price-filters/nonexistent_id",
                json=update_data
            )
            
            assert response.status_code == 404
            data = response.json()
            assert "Price filter not found" in data["detail"]

    @pytest.mark.asyncio
    async def test_update_price_filter_validation_error(self, client):
        """Test updating a price filter with validation error"""
        invalid_data = {
            "min_price": 500000.0,
            "max_price": 100000.0  # min > max
        }
        
        response = client.put(
            "/api/v1/price-filters/price-filters/price_filter_123",
            json=invalid_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "min_price cannot be greater than max_price" in data["detail"]

    @pytest.mark.asyncio
    async def test_delete_price_filter(self, client):
        """Test deleting a price filter"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.delete_price_filter.return_value = True
            
            response = client.delete("/api/v1/price-filters/price-filters/price_filter_123")
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_delete_price_filter_not_found(self, client):
        """Test deleting a non-existent price filter"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.delete_price_filter.return_value = False
            
            response = client.delete("/api/v1/price-filters/price-filters/nonexistent_id")
            
            assert response.status_code == 404
            data = response.json()
            assert "Price filter not found" in data["detail"]

    @pytest.mark.asyncio
    async def test_create_price_filter_service_error(self, client, sample_price_filter_data):
        """Test creating a price filter with service error"""
        with patch('app.api.v1.endpoints.price_filters.PriceFilterService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.create_price_filter.side_effect = Exception("Database error")
            
            response = client.post(
                "/api/v1/price-filters/price-filters",
                json=sample_price_filter_data
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "Error creating price filter" in data["detail"]
