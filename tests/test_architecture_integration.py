"""
Integration tests for the new architecture with queue and status tracking
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.models.telegram import RealEstateAd, PropertyType, RentalType
from app.models.simple_filter import SimpleFilter
from app.models.message_queue import QueuedMessage, ProcessingStatus
from app.services.message_queue_service import MessageQueueService


class TestArchitectureIntegration:
    """Test the new architecture with queue processing"""
    
    @pytest.fixture
    def sample_real_estate_ad(self):
        """Sample real estate ad with new fields"""
        return RealEstateAd(
            original_post_id=1,
            original_channel_id=12345,
            original_message="Test apartment message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            rooms_count=2,
            area_sqm=60.0,
            price=250000.0,
            currency="AMD",
            district="Центр",
            city="Ереван",
            has_balcony=True,
            has_air_conditioning=True,
            has_elevator=True,
            pets_allowed=True,
            utilities_included=False,
            processing_status="completed",
            llm_processed=True,
            llm_cost=0.01,
            parsing_confidence=0.9
        )
    
    @pytest.fixture
    def sample_filter(self):
        """Sample filter with new fields"""
        return SimpleFilter(
            name="2-3 Room Apartment in Center",
            property_types=[PropertyType.APARTMENT],
            rental_types=[RentalType.LONG_TERM],
            min_rooms=2,
            max_rooms=3,
            districts=["Центр"],
            min_price=200000.0,
            max_price=300000.0,
            price_currency="AMD",
            has_balcony=True,
            has_air_conditioning=True,
            is_active=True
        )
    
    def test_real_estate_ad_new_fields(self, sample_real_estate_ad):
        """Test RealEstateAd with new price/currency fields"""
        assert sample_real_estate_ad.price == 250000.0
        assert sample_real_estate_ad.currency == "AMD"
        assert sample_real_estate_ad.has_elevator is True
        assert sample_real_estate_ad.pets_allowed is True
        assert sample_real_estate_ad.utilities_included is False
        assert sample_real_estate_ad.processing_status == "completed"
        assert sample_real_estate_ad.llm_processed is True
        assert sample_real_estate_ad.llm_cost == 0.01
    
    def test_simple_filter_new_fields(self, sample_filter):
        """Test SimpleFilter with new price/currency fields"""
        assert sample_filter.min_price == 200000.0
        assert sample_filter.max_price == 300000.0
        assert sample_filter.price_currency == "AMD"
        assert sample_filter.has_elevator is None  # Not set
        assert sample_filter.pets_allowed is None  # Not set
        assert sample_filter.utilities_included is None  # Not set
    
    def test_filter_matching_with_new_fields(self, sample_real_estate_ad, sample_filter):
        """Test filter matching with new price/currency fields"""
        # Should match all criteria
        assert sample_filter.matches(sample_real_estate_ad) is True
        
        # Test currency mismatch
        sample_real_estate_ad.currency = "USD"
        assert sample_filter.matches(sample_real_estate_ad) is False
        
        # Test price range
        sample_real_estate_ad.currency = "AMD"
        sample_real_estate_ad.price = 150000.0  # Below min
        assert sample_filter.matches(sample_real_estate_ad) is False
        
        sample_real_estate_ad.price = 350000.0  # Above max
        assert sample_filter.matches(sample_real_estate_ad) is False
        
        sample_real_estate_ad.price = 250000.0  # Back to valid range
        assert sample_filter.matches(sample_real_estate_ad) is True
    
    def test_queued_message_creation(self):
        """Test QueuedMessage creation and status updates"""
        message = QueuedMessage(
            original_post_id=1,
            original_channel_id=12345,
            original_message="Test message"
        )
        
        assert message.status == ProcessingStatus.PENDING
        assert message.llm_processed is False
        assert message.llm_cost is None
        assert message.processing_errors == []
    
    @pytest.mark.asyncio
    async def test_message_queue_service_initialization(self):
        """Test MessageQueueService initialization"""
        with patch('app.services.message_queue_service.redis.from_url') as mock_redis:
            mock_redis.return_value = AsyncMock()
            
            service = MessageQueueService()
            redis_client = await service.get_redis_client()
            
            assert redis_client is not None
            mock_redis.assert_called_once()
    
    def test_processing_status_enum(self):
        """Test ProcessingStatus enum values"""
        assert ProcessingStatus.PENDING == "pending"
        assert ProcessingStatus.PROCESSING == "processing"
        assert ProcessingStatus.COMPLETED == "completed"
        assert ProcessingStatus.FAILED == "failed"
        assert ProcessingStatus.SKIPPED == "skipped"
    
    def test_model_serialization(self, sample_real_estate_ad, sample_filter):
        """Test that models can be serialized to JSON"""
        # Test RealEstateAd serialization
        ad_dict = sample_real_estate_ad.model_dump()
        assert "price" in ad_dict
        assert "currency" in ad_dict
        assert "has_elevator" in ad_dict
        assert "processing_status" in ad_dict
        assert "llm_processed" in ad_dict
        assert "llm_cost" in ad_dict
        
        # Test SimpleFilter serialization
        filter_dict = sample_filter.model_dump()
        assert "min_price" in filter_dict
        assert "max_price" in filter_dict
        assert "price_currency" in filter_dict
        assert "has_elevator" in filter_dict
        assert "pets_allowed" in filter_dict
        assert "utilities_included" in filter_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
