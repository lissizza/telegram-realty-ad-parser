#!/usr/bin/env python3
"""
Tests for user channel subscription service
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.user_channel_subscription_service import UserChannelSubscriptionService
from app.models.user_channel_subscription import UserChannelSubscriptionCreate, UserChannelSubscriptionResponse
from tests.test_utils import generate_test_subscription_data, generate_test_channel_info, generate_random_channel_name


class TestUserChannelSubscriptionService:
    """Test class for user channel subscription service"""

    @pytest.fixture
    def service(self):
        """Create service instance"""
        return UserChannelSubscriptionService()

    @pytest.fixture
    def mock_db(self):
        """Mock database"""
        mock_db = MagicMock()
        mock_db.user_channel_subscriptions = MagicMock()
        return mock_db

    @pytest.fixture
    def mock_subscription_data(self):
        """Mock subscription data with random values"""
        return generate_test_subscription_data(
            user_id=123456789,
            channel_id="-1001827102719",
            channel_username="@test_channel_1",
            topic_id=2629
        )

    @pytest.fixture
    def mock_channel_info(self):
        """Mock channel info from resolver with random values"""
        return generate_test_channel_info(
            channel_id=-1001827102719,
            channel_username="@test_channel_1",
            topic_id=2629
        )

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_get_all_active_subscriptions_success(self, mock_mongodb, service, mock_db, mock_subscription_data):
        """Test successful retrieval of all active subscriptions"""
        # Mock database
        mock_mongodb.get_database.return_value = mock_db
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = [mock_subscription_data]
        mock_db.user_channel_subscriptions.find.return_value = mock_cursor

        # Call method
        result = await service.get_all_active_subscriptions()

        # Assertions
        assert len(result) == 1
        assert isinstance(result[0], UserChannelSubscriptionResponse)
        assert result[0].user_id == 123456789
        assert result[0].channel_username == "@test_channel_1"

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_get_all_active_subscriptions_empty(self, mock_mongodb, service, mock_db):
        """Test retrieval of active subscriptions when none exist"""
        # Mock database
        mock_mongodb.get_database.return_value = mock_db
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = []
        mock_db.user_channel_subscriptions.find.return_value = mock_cursor

        # Call method
        result = await service.get_all_active_subscriptions()

        # Assertions
        assert result == []

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_get_all_active_subscriptions_database_error(self, mock_mongodb, service, mock_db):
        """Test handling of database errors"""
        # Mock database to raise exception
        mock_mongodb.get_database.return_value = mock_db
        mock_db.user_channel_subscriptions.find.side_effect = Exception("Database error")

        # Call method
        result = await service.get_all_active_subscriptions()

        # Assertions
        assert result == []

    @patch('app.services.user_channel_subscription_service.mongodb')
    @patch.object(UserChannelSubscriptionService, '_resolve_channel_info')
    @patch.object(UserChannelSubscriptionService, '_get_topic_title')
    async def test_create_subscription_success(self, mock_get_topic_title, mock_resolve_channel_info, 
                                             mock_mongodb, service, mock_db, mock_channel_info):
        """Test successful subscription creation"""
        # Mock dependencies
        mock_mongodb.get_database.return_value = mock_db
        mock_resolve_channel_info.return_value = mock_channel_info
        mock_get_topic_title.return_value = "Test Topic"
        
        # Mock database operations
        mock_db.user_channel_subscriptions.find_one.return_value = None  # No existing subscription
        mock_db.user_channel_subscriptions.insert_one.return_value = MagicMock(inserted_id="new_id")

        # Generate random channel name for testing
        test_channel = generate_random_channel_name()
        
        # Create subscription data
        subscription_data = UserChannelSubscriptionCreate(
            user_id=123456789,
            channel_input=f"@{test_channel}",
            topic_id=None
        )

        # Call method
        result = await service.create_subscription(subscription_data)

        # Assertions
        assert result == "new_id"
        mock_resolve_channel_info.assert_called_once_with(f"@{test_channel}")
        mock_get_topic_title.assert_called_once_with(-1001827102719, 2629)

    @patch('app.services.user_channel_subscription_service.mongodb')
    @patch.object(UserChannelSubscriptionService, '_resolve_channel_info')
    async def test_create_subscription_duplicate(self, mock_resolve_channel_info, mock_mongodb, 
                                               service, mock_db, mock_channel_info):
        """Test handling of duplicate subscription"""
        # Mock dependencies
        mock_mongodb.get_database.return_value = mock_db
        mock_resolve_channel_info.return_value = mock_channel_info
        
        # Mock database to return existing subscription
        mock_db.user_channel_subscriptions.find_one.return_value = {"_id": "existing_id"}

        # Generate random channel name for testing
        test_channel = generate_random_channel_name()
        
        # Create subscription data
        subscription_data = UserChannelSubscriptionCreate(
            user_id=123456789,
            channel_input=f"@{test_channel}",
            topic_id=None
        )

        # Call method and expect ValueError
        with pytest.raises(ValueError, match="У вас уже есть подписка на канал"):
            await service.create_subscription(subscription_data)

    @patch('app.services.user_channel_subscription_service.mongodb')
    @patch.object(UserChannelSubscriptionService, '_resolve_channel_info')
    async def test_create_subscription_channel_not_found(self, mock_resolve_channel_info, mock_mongodb, service):
        """Test handling of channel not found"""
        # Mock dependencies
        mock_resolve_channel_info.return_value = None

        # Create subscription data
        subscription_data = UserChannelSubscriptionCreate(
            user_id=123456789,
            channel_input="@nonexistent_channel",
            topic_id=None
        )

        # Call method
        result = await service.create_subscription(subscription_data)

        # Assertions
        assert result is None

    @patch('app.services.user_channel_subscription_service.mongodb')
    @patch.object(UserChannelSubscriptionService, '_resolve_channel_info')
    async def test_create_subscription_resolve_error(self, mock_resolve_channel_info, mock_mongodb, service):
        """Test handling of channel resolution error"""
        # Mock dependencies
        mock_resolve_channel_info.side_effect = ValueError("Канал не найден")

        # Generate random channel name for testing
        test_channel = generate_random_channel_name()
        
        # Create subscription data
        subscription_data = UserChannelSubscriptionCreate(
            user_id=123456789,
            channel_input=f"@{test_channel}",
            topic_id=None
        )

        # Call method and expect ValueError to be re-raised
        with pytest.raises(ValueError, match="Канал не найден"):
            await service.create_subscription(subscription_data)

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_get_user_subscriptions_success(self, mock_mongodb, service, mock_db, mock_subscription_data):
        """Test successful retrieval of user subscriptions"""
        # Mock database
        mock_mongodb.get_database.return_value = mock_db
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = [mock_subscription_data]
        mock_db.user_channel_subscriptions.find.return_value = mock_cursor

        # Call method
        result = await service.get_user_subscriptions(123456789)

        # Assertions
        assert len(result) == 1
        assert isinstance(result[0], UserChannelSubscriptionResponse)
        assert result[0].user_id == 123456789

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_get_user_subscriptions_database_error(self, mock_mongodb, service, mock_db):
        """Test handling of database errors in get_user_subscriptions"""
        # Mock database to raise exception
        mock_mongodb.get_database.return_value = mock_db
        mock_db.user_channel_subscriptions.find.side_effect = Exception("Database error")

        # Call method
        result = await service.get_user_subscriptions(123456789)

        # Assertions
        assert result == []

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_toggle_subscription_active_success(self, mock_mongodb, service, mock_db):
        """Test successful subscription status toggle"""
        # Mock database
        mock_mongodb.get_database.return_value = mock_db
        mock_db.user_channel_subscriptions.update_one.return_value = MagicMock(modified_count=1)

        # Call method
        result = await service.toggle_subscription_active("507f1f77bcf86cd799439011")

        # Assertions
        assert result is True
        mock_db.user_channel_subscriptions.update_one.assert_called_once()

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_toggle_subscription_active_not_found(self, mock_mongodb, service, mock_db):
        """Test subscription status toggle when subscription not found"""
        # Mock database
        mock_mongodb.get_database.return_value = mock_db
        mock_db.user_channel_subscriptions.update_one.return_value = MagicMock(modified_count=0)

        # Call method
        result = await service.toggle_subscription_active("507f1f77bcf86cd799439011")

        # Assertions
        assert result is False

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_delete_subscription_success(self, mock_mongodb, service, mock_db):
        """Test successful subscription deletion"""
        # Mock database
        mock_mongodb.get_database.return_value = mock_db
        mock_db.user_channel_subscriptions.delete_one.return_value = MagicMock(deleted_count=1)

        # Call method
        result = await service.delete_subscription("507f1f77bcf86cd799439011")

        # Assertions
        assert result is True
        mock_db.user_channel_subscriptions.delete_one.assert_called_once()

    @patch('app.services.user_channel_subscription_service.mongodb')
    async def test_delete_subscription_not_found(self, mock_mongodb, service, mock_db):
        """Test subscription deletion when subscription not found"""
        # Mock database
        mock_mongodb.get_database.return_value = mock_db
        mock_db.user_channel_subscriptions.delete_one.return_value = MagicMock(deleted_count=0)

        # Call method
        result = await service.delete_subscription("507f1f77bcf86cd799439011")

        # Assertions
        assert result is False