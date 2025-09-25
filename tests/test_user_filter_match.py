"""
Tests for UserFilterMatch architecture and multi-user filter system
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.models.user_filter_match import UserFilterMatch
from app.models.simple_filter import SimpleFilter
from app.models.telegram import PropertyType, RealEstateAd, RentalType
from app.services.user_filter_match_service import UserFilterMatchService
from app.services.simple_filter_service import SimpleFilterService


class TestUserFilterMatch:
    """Test class for UserFilterMatch functionality"""

    @pytest.fixture
    def match_service(self):
        """Create UserFilterMatchService instance for testing"""
        return UserFilterMatchService()

    @pytest.fixture
    def filter_service(self):
        """Create SimpleFilterService instance for testing"""
        return SimpleFilterService()

    @pytest.fixture
    def sample_user_filter(self):
        """Sample filter for user 123"""
        return SimpleFilter(
            id="filter_123",
            user_id=123,
            name="Test User Filter",
            description="Test filter for user 123",
            property_types=[PropertyType.APARTMENT],
            min_rooms=2,
            max_rooms=3,
            is_active=True
        )

    @pytest.fixture
    def sample_apartment_ad(self):
        """Sample apartment advertisement"""
        return RealEstateAd(
            id="ad_123",
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

    @pytest.mark.asyncio
    async def test_create_match(self, match_service):
        """Test creating a new UserFilterMatch"""
        with patch("app.services.user_filter_match_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock no existing match
            mock_db.user_filter_matches.find_one = AsyncMock(return_value=None)
            
            # Mock successful insert
            mock_insert_result = MagicMock()
            mock_insert_result.inserted_id = "match_123"
            mock_db.user_filter_matches.insert_one = AsyncMock(return_value=mock_insert_result)
            
            match_id = await match_service.create_match(
                user_id=123,
                filter_id="filter_123",
                real_estate_ad_id="ad_123"
            )
            
            assert match_id == "match_123"
            mock_db.user_filter_matches.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_match_already_exists(self, match_service):
        """Test creating a match when it already exists"""
        with patch("app.services.user_filter_match_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock existing match
            mock_db.user_filter_matches.find_one = AsyncMock(return_value={"_id": "existing_match"})
            
            match_id = await match_service.create_match(
                user_id=123,
                filter_id="filter_123",
                real_estate_ad_id="ad_123"
            )
            
            assert match_id == "existing_match"
            # Should not call insert_one if match already exists
            mock_db.user_filter_matches.insert_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_matches_for_user(self, match_service):
        """Test getting matches for a specific user"""
        with patch("app.services.user_filter_match_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock matches data
            mock_matches = [
                {
                    "_id": "match_1",
                    "user_id": 123,
                    "filter_id": "filter_123",
                    "real_estate_ad_id": "ad_123",
                    "matched_at": datetime.now(timezone.utc),
                    "forwarded": False,
                    "status": "matched"
                }
            ]
            
            # Create a mock cursor that supports .sort() and .limit()
            mock_cursor = MagicMock()
            
            async def mock_find_iterator():
                for match in mock_matches:
                    yield match
            
            mock_cursor.__aiter__ = lambda self: mock_find_iterator()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            
            mock_db.user_filter_matches.find.return_value = mock_cursor
            
            matches = await match_service.get_matches_for_user(123)
            
            assert len(matches) == 1
            assert matches[0].user_id == 123
            assert matches[0].filter_id == "filter_123"

    @pytest.mark.asyncio
    async def test_mark_as_forwarded(self, match_service):
        """Test marking a match as forwarded"""
        with patch("app.services.user_filter_match_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock successful update
            mock_update_result = MagicMock()
            mock_update_result.modified_count = 1
            mock_db.user_filter_matches.update_one = AsyncMock(return_value=mock_update_result)
            
            # Use a valid ObjectId format (24 hex characters)
            valid_object_id = "507f1f77bcf86cd799439011"
            result = await match_service.mark_as_forwarded(valid_object_id)
            
            assert result is True
            mock_db.user_filter_matches.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_unforwarded_matches(self, match_service):
        """Test getting unforwarded matches for a user"""
        with patch("app.services.user_filter_match_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock unforwarded matches
            mock_matches = [
                {
                    "_id": "match_1",
                    "user_id": 123,
                    "filter_id": "filter_123",
                    "real_estate_ad_id": "ad_123",
                    "matched_at": datetime.now(timezone.utc),
                    "forwarded": False,
                    "status": "matched"
                }
            ]
            
            # Create a mock cursor that supports .sort() and .limit()
            mock_cursor = MagicMock()
            
            async def mock_find_iterator():
                for match in mock_matches:
                    yield match
            
            mock_cursor.__aiter__ = lambda self: mock_find_iterator()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            
            mock_db.user_filter_matches.find.return_value = mock_cursor
            
            matches = await match_service.get_unforwarded_matches_for_user(123)
            
            assert len(matches) == 1
            assert matches[0].forwarded is False


class TestMultiUserFilterArchitecture:
    """Test class for multi-user filter architecture"""

    @pytest.fixture
    def filter_service(self):
        """Create SimpleFilterService instance for testing"""
        return SimpleFilterService()

    @pytest.fixture
    def sample_apartment_ad(self):
        """Sample apartment advertisement"""
        return RealEstateAd(
            id="ad_123",
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
            parsing_confidence=0.9,
        )

    @pytest.mark.asyncio
    async def test_get_filters_by_user(self, filter_service):
        """Test getting filters for a specific user"""
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock filters for user 123
            mock_filters = [
                {
                    "_id": "filter_1",
                    "user_id": 123,
                    "name": "User 123 Filter",
                    "property_types": ["apartment"],
                    "is_active": True
                }
            ]
            
            # Create a proper async iterator
            async def mock_find(query):
                # Only return filters for user 123
                if query.get("user_id") == 123:
                    for filter_data in mock_filters:
                        yield filter_data
            
            mock_cursor = mock_find({"user_id": 123, "is_active": True})
            mock_db.simple_filters.find.return_value = mock_cursor
            
            filters = await filter_service.get_active_filters(user_id=123)
            
            assert len(filters) == 1
            assert filters[0].user_id == 123
            assert filters[0].name == "User 123 Filter"

    @pytest.mark.asyncio
    async def test_get_filters_all_users(self, filter_service):
        """Test getting filters for all users (no user_id specified)"""
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock filters for multiple users
            mock_filters = [
                {
                    "_id": "filter_1",
                    "user_id": 123,
                    "name": "User 123 Filter",
                    "property_types": ["apartment"],
                    "is_active": True
                },
                {
                    "_id": "filter_2",
                    "user_id": 456,
                    "name": "User 456 Filter",
                    "property_types": ["house"],
                    "is_active": True
                }
            ]
            
            async def mock_find(query):
                for filter_data in mock_filters:
                    yield filter_data
            
            mock_db.simple_filters.find.return_value = mock_find(mock_filters)
            
            filters = await filter_service.get_active_filters(user_id=None)
            
            assert len(filters) == 2
            assert filters[0].user_id == 123
            assert filters[1].user_id == 456

    @pytest.mark.asyncio
    async def test_check_filters_with_user_id(self, filter_service, sample_apartment_ad):
        """Test checking filters with user_id creates UserFilterMatch records"""
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb, \
             patch("app.services.user_filter_match_service.UserFilterMatchService") as mock_match_service_class:
            
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock filter for user 123
            mock_filter = {
                "_id": "filter_123",
                "user_id": 123,
                "name": "User 123 Filter",
                "property_types": ["apartment"],
                "is_active": True
            }
            
            async def mock_find(query):
                if query.get("user_id") == 123:
                    yield mock_filter
            
            mock_db.simple_filters.find.return_value = mock_find(mock_filter)
            
            # Mock UserFilterMatchService
            mock_match_service = AsyncMock()
            mock_match_service.create_match.return_value = "match_123"
            mock_match_service_class.return_value = mock_match_service
            
            result = await filter_service.check_filters(sample_apartment_ad, user_id=123)
            
            # Should match the filter
            assert len(result["matching_filters"]) == 1
            assert result["should_forward"] is True
            assert "created_matches" in result
            
            # Should create UserFilterMatch record
            mock_match_service.create_match.assert_called_once_with(
                user_id=123,
                filter_id="filter_123",
                real_estate_ad_id="ad_123"
            )

    @pytest.mark.asyncio
    async def test_check_filters_without_user_id(self, filter_service, sample_apartment_ad):
        """Test checking filters without user_id doesn't create UserFilterMatch records"""
        with patch("app.services.simple_filter_service.mongodb") as mock_mongodb:
            mock_db = MagicMock()
            mock_mongodb.get_database.return_value = mock_db
            
            # Mock filter
            mock_filter = {
                "_id": "filter_123",
                "user_id": 123,
                "name": "Test Filter",
                "property_types": ["apartment"],
                "is_active": True
            }
            
            async def mock_find(query):
                yield mock_filter
            
            mock_db.simple_filters.find.return_value = mock_find(mock_filter)
            
            result = await filter_service.check_filters(sample_apartment_ad, user_id=None)
            
            # Should match the filter
            assert len(result["matching_filters"]) == 1
            assert result["should_forward"] is True
            
            # Should not create UserFilterMatch records (no user_id provided)
            assert result["created_matches"] == []


class TestUserFilterMatchModel:
    """Test class for UserFilterMatch model"""

    def test_user_filter_match_creation(self):
        """Test creating UserFilterMatch model instance"""
        match = UserFilterMatch(
            user_id=123,
            filter_id="filter_123",
            real_estate_ad_id="ad_123"
        )
        
        assert match.user_id == 123
        assert match.filter_id == "filter_123"
        assert match.real_estate_ad_id == "ad_123"
        assert match.forwarded is False
        assert match.status == "matched"
        assert match.matched_at is not None

    def test_user_filter_match_serialization(self):
        """Test UserFilterMatch model serialization"""
        match = UserFilterMatch(
            user_id=123,
            filter_id="filter_123",
            real_estate_ad_id="ad_123"
        )
        
        data = match.model_dump()
        
        assert data["user_id"] == 123
        assert data["filter_id"] == "filter_123"
        assert data["real_estate_ad_id"] == "ad_123"
        assert data["forwarded"] is False
        assert data["status"] == "matched"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
