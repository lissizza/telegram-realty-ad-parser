#!/usr/bin/env python3
"""
Tests for user channel subscription API endpoints
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user_channel_subscription import UserChannelSubscriptionResponse
from tests.test_utils import generate_test_subscription_response, generate_random_channel_name


class TestUserChannelSubscriptionAPI:
    """Test class for user channel subscription API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_subscriptions(self):
        """Mock subscription data with random values"""
        return [
            generate_test_subscription_response(
                user_id=123456789,
                channel_id="-1001827102719",
                channel_username="@test_channel_1",
                topic_id=2629
            ),
            generate_test_subscription_response(
                user_id=123456789,
                channel_id="2141531868",
                channel_username="@test_channel_2",
                topic_id=None
            )
        ]

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.user_channel_subscriptions.get_user_channel_subscription_service')
    async def test_get_user_subscriptions_success(self, mock_service, client, mock_subscriptions):
        """Test successful retrieval of user subscriptions"""
        # Mock the service
        mock_service_instance = AsyncMock()
        mock_service_instance.get_user_subscriptions.return_value = mock_subscriptions
        mock_service.return_value = mock_service_instance

        # Make request
        response = client.get("/api/v1/user-channel-subscriptions/?user_id=123456789")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["user_id"] == 123456789
        assert data[0]["channel_username"] == "@test_channel_1"
        assert data[1]["channel_username"] == "@test_channel_2"

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.user_channel_subscriptions.get_user_channel_subscription_service')
    async def test_get_user_subscriptions_empty(self, mock_service, client):
        """Test retrieval of user subscriptions when none exist"""
        # Mock the service to return empty list
        mock_service_instance = AsyncMock()
        mock_service_instance.get_user_subscriptions.return_value = []
        mock_service.return_value = mock_service_instance

        # Make request
        response = client.get("/api/v1/user-channel-subscriptions/?user_id=123456789")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.user_channel_subscriptions.get_user_channel_subscription_service')
    async def test_get_user_subscriptions_service_error(self, mock_service, client):
        """Test handling of service errors"""
        # Mock the service to raise an exception
        mock_service_instance = AsyncMock()
        mock_service_instance.get_user_subscriptions.side_effect = Exception("Database error")
        mock_service.return_value = mock_service_instance

        # Make request
        response = client.get("/api/v1/user-channel-subscriptions/?user_id=123456789")

        # Assertions
        assert response.status_code == 500

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.user_channel_subscriptions.get_user_channel_subscription_service')
    async def test_quick_add_channel_success(self, mock_service, client):
        """Test successful channel addition"""
        # Mock the service
        mock_service_instance = AsyncMock()
        mock_service_instance.create_subscription.return_value = "new_subscription_id"
        mock_service.return_value = mock_service_instance

        # Generate random channel name for testing
        test_channel = generate_random_channel_name()

        # Make request
        response = client.post(
            "/api/v1/user-channel-subscriptions/quick-add",
            json={
                "user_id": 123456789,
                "channel_input": f"@{test_channel}",
                "topic_id": None
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Channel subscription created successfully"
        assert data["subscription_id"] == "new_subscription_id"

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.user_channel_subscriptions.get_user_channel_subscription_service')
    async def test_quick_add_channel_duplicate(self, mock_service, client):
        """Test handling of duplicate channel subscription"""
        # Mock the service to raise ValueError for duplicate
        mock_service_instance = AsyncMock()
        mock_service_instance.create_subscription.side_effect = ValueError("У вас уже есть подписка на канал Test Channel")
        mock_service.return_value = mock_service_instance

        # Generate random channel name for testing
        test_channel = generate_random_channel_name()

        # Make request
        response = client.post(
            "/api/v1/user-channel-subscriptions/quick-add",
            json={
                "user_id": 123456789,
                "channel_input": f"@{test_channel}",
                "topic_id": None
            }
        )

        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "У вас уже есть подписка на канал" in data["detail"]

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.user_channel_subscriptions.get_user_channel_subscription_service')
    async def test_quick_add_channel_not_found(self, mock_service, client):
        """Test handling of channel not found"""
        # Mock the service to raise ValueError for channel not found
        mock_service_instance = AsyncMock()
        mock_service_instance.create_subscription.side_effect = ValueError("Канал не найден. Проверьте правильность названия канала или ссылки.")
        mock_service.return_value = mock_service_instance

        # Generate random channel name that doesn't exist
        nonexistent_channel = generate_random_channel_name()

        # Make request
        response = client.post(
            "/api/v1/user-channel-subscriptions/quick-add",
            json={
                "user_id": 123456789,
                "channel_input": f"@{nonexistent_channel}",
                "topic_id": None
            }
        )

        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "Канал не найден" in data["detail"]

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.user_channel_subscriptions.get_user_channel_subscription_service')
    async def test_quick_add_channel_creation_failed(self, mock_service, client):
        """Test handling of subscription creation failure"""
        # Mock the service to return None (creation failed)
        mock_service_instance = AsyncMock()
        mock_service_instance.create_subscription.return_value = None
        mock_service.return_value = mock_service_instance

        # Generate random channel name for testing
        test_channel = generate_random_channel_name()

        # Make request
        response = client.post(
            "/api/v1/user-channel-subscriptions/quick-add",
            json={
                "user_id": 123456789,
                "channel_input": f"@{test_channel}",
                "topic_id": None
            }
        )

        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Failed to create subscription"
