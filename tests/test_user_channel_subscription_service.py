from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user_channel_subscription import (
    UserChannelSubscriptionCreate,
    UserChannelSubscriptionResponse,
)
from app.services.user_channel_subscription_service import (
    UserChannelSubscriptionService,
)


class TestUserChannelSubscriptionService:
    """Test cases for UserChannelSubscriptionService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = UserChannelSubscriptionService()

    def test_parse_channel_input_tme_url_with_topic(self):
        """Test parsing t.me URL with topic"""
        channel_input = "https://t.me/rent_comissionfree/2629"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username == "rent_comissionfree"
        assert topic_id == 2629
        assert link == "https://t.me/rent_comissionfree/2629"
        assert channel_id is None
        assert topic_title is None

    def test_parse_channel_input_tme_url_without_topic(self):
        """Test parsing t.me URL without topic"""
        channel_input = "https://t.me/rent_comissionfree"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username == "rent_comissionfree"
        assert topic_id is None
        assert link == "https://t.me/rent_comissionfree"
        assert channel_id is None
        assert topic_title is None

    def test_parse_channel_input_short_url(self):
        """Test parsing short t.me URL"""
        channel_input = "t.me/channel_name"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username == "channel_name"
        assert topic_id is None
        assert link == "https://t.me/channel_name"
        assert channel_id is None
        assert topic_title is None

    def test_parse_channel_input_username_with_at(self):
        """Test parsing username with @ prefix"""
        channel_input = "@channel_name"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username == "channel_name"
        assert topic_id is None
        assert link == "https://t.me/channel_name"
        assert channel_id is None
        assert topic_title is None

    def test_parse_channel_input_username_without_at(self):
        """Test parsing username without @ prefix"""
        channel_input = "channel_name"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username == "channel_name"
        assert topic_id is None
        assert link == "https://t.me/channel_name"
        assert channel_id is None
        assert topic_title is None

    def test_parse_channel_input_channel_id(self):
        """Test parsing channel ID"""
        channel_input = "-1001827102719"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username is None
        assert topic_id is None
        assert link is None
        assert channel_id == -1001827102719
        assert topic_title is None

    def test_parse_channel_input_channel_id_with_topic(self):
        """Test parsing channel ID with topic"""
        channel_input = "-1001827102719:2629"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username is None
        assert topic_id == 2629
        assert link is None
        assert channel_id == -1001827102719
        assert topic_title is None

    def test_parse_channel_input_positive_channel_id(self):
        """Test parsing positive channel ID"""
        channel_input = "1001827102719"
        
        username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
        
        assert username is None
        assert topic_id is None
        assert link is None
        assert channel_id == 1001827102719
        assert topic_title is None

    @pytest.mark.asyncio
    async def test_create_subscription_success_with_username(self):
        """Test successful subscription creation with username"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock find_one to return None (no existing subscription)
        mock_collection.find_one.return_value = None
        
        # Mock insert_one to return success
        mock_result = MagicMock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        mock_collection.insert_one.return_value = mock_result
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            subscription_data = UserChannelSubscriptionCreate(
                user_id=123,
                channel_input="@test_channel"
            )
            
            result = await self.service.create_subscription(subscription_data)
            
            assert result == "507f1f77bcf86cd799439011"
            mock_collection.find_one.assert_called_once()
            mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subscription_success_with_channel_id(self):
        """Test successful subscription creation with channel ID"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock find_one to return None (no existing subscription)
        mock_collection.find_one.return_value = None
        
        # Mock insert_one to return success
        mock_result = MagicMock()
        mock_result.inserted_id = "507f1f77bcf86cd799439012"
        mock_collection.insert_one.return_value = mock_result
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            subscription_data = UserChannelSubscriptionCreate(
                user_id=123,
                channel_input="-1001827102719"
            )
            
            result = await self.service.create_subscription(subscription_data)
            
            assert result == "507f1f77bcf86cd799439012"
            mock_collection.find_one.assert_called_once()
            mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subscription_existing_subscription(self):
        """Test creating subscription when one already exists"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock find_one to return existing subscription
        existing_subscription = {"_id": "507f1f77bcf86cd799439011", "user_id": 123}
        mock_collection.find_one.return_value = existing_subscription
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            subscription_data = UserChannelSubscriptionCreate(
                user_id=123,
                channel_input="@test_channel"
            )
            
            result = await self.service.create_subscription(subscription_data)
            
            assert result == "507f1f77bcf86cd799439011"
            mock_collection.find_one.assert_called_once()
            mock_collection.insert_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_input(self):
        """Test creating subscription with invalid input"""
        with patch.object(self.service, '_get_db', side_effect=Exception("Database error")):
            subscription_data = UserChannelSubscriptionCreate(
                user_id=123,
                channel_input=""
            )
            
            result = await self.service.create_subscription(subscription_data)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_subscriptions_success(self):
        """Test getting user subscriptions successfully"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock cursor with subscriptions
        mock_subscriptions = [
            {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": 123,
                "channel_username": "test_channel",
                "channel_title": "Test Channel",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # Create async iterator for cursor
        class MockCursor:
            def __init__(self, docs):
                self.docs = docs
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if not self.docs:
                    raise StopAsyncIteration
                return self.docs.pop(0)
        
        mock_collection.find.return_value = MockCursor(mock_subscriptions.copy())
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            result = await self.service.get_user_subscriptions(123)
            
            assert len(result) == 1
            assert isinstance(result[0], UserChannelSubscriptionResponse)
            assert result[0].id == "507f1f77bcf86cd799439011"
            assert result[0].user_id == 123

    @pytest.mark.asyncio
    async def test_get_active_user_subscriptions(self):
        """Test getting active user subscriptions"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock cursor with active subscriptions
        mock_subscriptions = [
            {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": 123,
                "channel_username": "test_channel",
                "channel_title": "Test Channel",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # Create async iterator for cursor
        class MockCursor:
            def __init__(self, docs):
                self.docs = docs
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if not self.docs:
                    raise StopAsyncIteration
                return self.docs.pop(0)
        
        mock_collection.find.return_value = MockCursor(mock_subscriptions.copy())
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            result = await self.service.get_active_user_subscriptions(123)
            
            assert len(result) == 1
            assert result[0].is_active is True

    @pytest.mark.asyncio
    async def test_toggle_subscription_active_success(self):
        """Test toggling subscription active status"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock find_one to return subscription
        existing_subscription = {
            "_id": "507f1f77bcf86cd799439011",
            "is_active": True,
            "user_id": 123
        }
        mock_collection.find_one.return_value = existing_subscription
        
        # Mock update_one to return success
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            result = await self.service.toggle_subscription_active("507f1f77bcf86cd799439011")
            
            assert result is True
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_subscription_not_found(self):
        """Test toggling non-existent subscription"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock find_one to return None (subscription not found)
        mock_collection.find_one.return_value = None
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            result = await self.service.toggle_subscription_active("507f1f77bcf86cd799439011")
            
            assert result is False
            mock_collection.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_subscription_success(self):
        """Test deleting subscription successfully"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock delete_one to return success
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_collection.delete_one.return_value = mock_result
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            result = await self.service.delete_subscription("507f1f77bcf86cd799439011")
            
            assert result is True
            mock_collection.delete_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_subscription_invalid_id(self):
        """Test deleting subscription with invalid ID"""
        result = await self.service.delete_subscription("invalid_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_active_subscriptions(self):
        """Test getting all active subscriptions"""
        # Mock database
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_db.user_channel_subscriptions = mock_collection
        
        # Mock cursor with active subscriptions
        mock_subscriptions = [
            {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": 123,
                "channel_id": -1001827102719,
                "channel_title": "Test Channel",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "user_id": 456,
                "channel_username": "another_channel",
                "channel_title": "Another Channel",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # Create async iterator for cursor
        class MockCursor:
            def __init__(self, docs):
                self.docs = docs
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if not self.docs:
                    raise StopAsyncIteration
                return self.docs.pop(0)
        
        mock_collection.find.return_value = MockCursor(mock_subscriptions.copy())
        
        with patch.object(self.service, '_get_db', return_value=mock_db):
            result = await self.service.get_all_active_subscriptions()
            
            assert len(result) == 2
            assert all(isinstance(sub, UserChannelSubscriptionResponse) for sub in result)
            assert all(sub.is_active for sub in result)
