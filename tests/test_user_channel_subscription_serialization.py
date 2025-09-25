#!/usr/bin/env python3
"""
Tests for user channel subscription serialization
"""
import pytest
import json
from datetime import datetime
from bson import ObjectId

from app.models.user_channel_subscription import UserChannelSubscriptionResponse
from tests.test_utils import generate_test_subscription_response


class TestUserChannelSubscriptionSerialization:
    """Test class for user channel subscription serialization"""

    def test_user_channel_subscription_response_serialization(self):
        """Test JSON serialization of UserChannelSubscriptionResponse"""
        # Create test data with random values
        subscription = generate_test_subscription_response(
            user_id=123456789,
            channel_id="-1001827102719",
            channel_username="@test_channel_1",
            topic_id=2629
        )

        # Test model_dump() method
        subscription_dict = subscription.model_dump()
        assert isinstance(subscription_dict, dict)
        assert subscription_dict["user_id"] == 123456789
        assert subscription_dict["channel_username"] == "@test_channel_1"
        assert subscription_dict["is_active"] is True

        # Test JSON serialization
        json_str = json.dumps(subscription_dict, default=str)
        assert isinstance(json_str, str)
        
        # Parse back to verify
        parsed_data = json.loads(json_str)
        assert parsed_data["user_id"] == 123456789
        assert parsed_data["channel_username"] == "@test_channel_1"

    def test_user_channel_subscription_response_with_none_values(self):
        """Test serialization with None values"""
        # Create subscription manually with None values
        subscription = UserChannelSubscriptionResponse(
            id="507f1f77bcf86cd799439011",
            user_id=123456789,
            channel_id="-1001827102719",
            channel_username="@test_channel_2",
            channel_title="Test Channel",
            channel_link="https://t.me/test_channel_2",
            topic_id=None,
            topic_title=None,
            is_active=True,
            monitor_all_topics=False,
            monitored_topics=[],
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0)
        )

        # Test serialization with None values
        subscription_dict = subscription.model_dump()
        assert subscription_dict["topic_id"] is None
        assert subscription_dict["topic_title"] is None

        # Test JSON serialization
        json_str = json.dumps(subscription_dict, default=str)
        parsed_data = json.loads(json_str)
        assert parsed_data["topic_id"] is None
        assert parsed_data["topic_title"] is None

    def test_user_channel_subscription_response_validation(self):
        """Test model validation"""
        # Valid data
        valid_data = {
            "id": "507f1f77bcf86cd799439011",
            "user_id": 123456789,
            "channel_id": "-1001827102719",
            "channel_username": "@test_channel",
            "channel_title": "Test Channel",
            "channel_link": "https://t.me/test_channel",
            "topic_id": 2629,
            "topic_title": "Test Topic",
            "is_active": True,
            "monitor_all_topics": False,
            "monitored_topics": [],
            "created_at": "2025-01-01T12:00:00",
            "updated_at": "2025-01-01T12:00:00"
        }

        subscription = UserChannelSubscriptionResponse(**valid_data)
        assert subscription.user_id == 123456789
        assert subscription.channel_username == "@test_channel"

    def test_user_channel_subscription_response_validation_errors(self):
        """Test model validation with invalid data"""
        # Invalid data - missing required fields
        invalid_data = {
            "id": "507f1f77bcf86cd799439011",
            "user_id": 123456789,
            # Missing channel_title (required field)
            "channel_username": "@test_channel",
            "channel_link": "https://t.me/test_channel",
            "topic_id": 2629,
            "topic_title": "Test Topic",
            "is_active": True,
            "monitor_all_topics": False,
            "monitored_topics": [],
            "created_at": datetime(2025, 1, 1, 12, 0, 0),
            "updated_at": datetime(2025, 1, 1, 12, 0, 0)
        }

        with pytest.raises(ValueError):
            UserChannelSubscriptionResponse(**invalid_data)

    def test_user_channel_subscription_response_from_db_doc(self):
        """Test creating response from database document"""
        # Mock database document
        db_doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": 123456789,
            "channel_id": "-1001827102719",
            "channel_username": "@test_channel",
            "channel_title": "Test Channel",
            "channel_link": "https://t.me/test_channel",
            "topic_id": 2629,
            "topic_title": "Test Topic",
            "is_active": True,
            "monitor_all_topics": False,
            "monitored_topics": [],
            "created_at": datetime(2025, 1, 1, 12, 0, 0),
            "updated_at": datetime(2025, 1, 1, 12, 0, 0)
        }

        # Test from_db_doc method
        subscription = UserChannelSubscriptionResponse.from_db_doc(db_doc)
        assert subscription.id == "507f1f77bcf86cd799439011"
        assert subscription.user_id == 123456789
        assert subscription.channel_username == "@test_channel"

    def test_user_channel_subscription_response_serialization_with_objectid(self):
        """Test serialization with ObjectId"""
        # Create subscription with ObjectId as string (since id field expects string)
        subscription = UserChannelSubscriptionResponse(
            id="507f1f77bcf86cd799439011",  # Convert ObjectId to string
            user_id=123456789,
            channel_id="-1001827102719",
            channel_username="@test_channel",
            channel_title="Test Channel",
            channel_link="https://t.me/test_channel",
            topic_id=2629,
            topic_title="Test Topic",
            is_active=True,
            monitor_all_topics=False,
            monitored_topics=[],
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0)
        )

        # Test serialization
        subscription_dict = subscription.model_dump()
        json_str = json.dumps(subscription_dict, default=str)
        parsed_data = json.loads(json_str)
        
        # ID should be string
        assert parsed_data["id"] == "507f1f77bcf86cd799439011"
