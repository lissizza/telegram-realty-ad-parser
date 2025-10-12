from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user_channel_subscription import (
    UserChannelSubscriptionCreate,
    UserChannelSubscriptionResponse,
)


class TestUserChannelSubscriptionAPI:
    """Test cases for UserChannelSubscription API endpoints"""

    def setup_method(self):
        """Set up test fixtures"""
        self.client = TestClient(app)

    @pytest.mark.asyncio
    async def test_get_user_subscriptions_with_user_id(self):
        """Test GET /api/v1/user-channel-subscriptions/ with user_id parameter"""
        mock_subscriptions = [
            UserChannelSubscriptionResponse(
                id="507f1f77bcf86cd799439011",
                user_id=123,
                channel_username="test_channel",
                channel_title="Test Channel",
                is_active=True,
                monitor_all_topics=False,
                monitored_topics=[],
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00"
            )
        ]
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.get_user_subscriptions") as mock_get:
            mock_get.return_value = mock_subscriptions
            
            response = self.client.get("/api/v1/user-channel-subscriptions/?user_id=123")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["user_id"] == 123
            assert data[0]["channel_username"] == "test_channel"
            mock_get.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_get_user_subscriptions_without_user_id(self):
        """Test GET /api/v1/user-channel-subscriptions/ without user_id parameter"""
        mock_subscriptions = [
            UserChannelSubscriptionResponse(
                id="507f1f77bcf86cd799439011",
                user_id=123,
                channel_username="test_channel",
                channel_title="Test Channel",
                is_active=True,
                monitor_all_topics=False,
                monitored_topics=[],
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00"
            )
        ]
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.get_all_active_subscriptions") as mock_get:
            mock_get.return_value = mock_subscriptions
            
            response = self.client.get("/api/v1/user-channel-subscriptions/")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_subscriptions_active_only(self):
        """Test GET /api/v1/user-channel-subscriptions/ with active_only parameter"""
        mock_subscriptions = [
            UserChannelSubscriptionResponse(
                id="507f1f77bcf86cd799439011",
                user_id=123,
                channel_username="test_channel",
                channel_title="Test Channel",
                is_active=True,
                monitor_all_topics=False,
                monitored_topics=[],
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00"
            )
        ]
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.get_active_user_subscriptions") as mock_get:
            mock_get.return_value = mock_subscriptions
            
            response = self.client.get("/api/v1/user-channel-subscriptions/?user_id=123&active_only=true")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["is_active"] is True
            mock_get.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_create_user_subscription_success(self):
        """Test POST /api/v1/user-channel-subscriptions/ with valid data"""
        subscription_data = {
            "user_id": 123,
            "channel_input": "@test_channel"
        }
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.create_subscription") as mock_create:
            mock_create.return_value = "507f1f77bcf86cd799439011"
            
            response = self.client.post("/api/v1/user-channel-subscriptions/", json=subscription_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Subscription created successfully"
            assert data["subscription_id"] == "507f1f77bcf86cd799439011"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_subscription_failure(self):
        """Test POST /api/v1/user-channel-subscriptions/ with invalid data"""
        subscription_data = {
            "user_id": 123,
            "channel_input": ""
        }
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.create_subscription") as mock_create:
            mock_create.return_value = None
            
            response = self.client.post("/api/v1/user-channel-subscriptions/", json=subscription_data)
            
            assert response.status_code == 400
            data = response.json()
            assert "Failed to create subscription" in data["detail"]

    @pytest.mark.asyncio
    async def test_quick_add_channel_success(self):
        """Test POST /api/v1/user-channel-subscriptions/quick-add with valid data"""
        request_data = {
            "user_id": 123,
            "channel_input": "https://t.me/test_channel/123"
        }
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.create_subscription") as mock_create:
            mock_create.return_value = "507f1f77bcf86cd799439011"
            
            response = self.client.post("/api/v1/user-channel-subscriptions/quick-add", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Channel subscription created successfully"
            assert data["subscription_id"] == "507f1f77bcf86cd799439011"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_quick_add_channel_with_topic(self):
        """Test POST /api/v1/user-channel-subscriptions/quick-add with topic"""
        request_data = {
            "user_id": 123,
            "channel_input": "@test_channel",
            "topic_id": 456
        }
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.create_subscription") as mock_create:
            mock_create.return_value = "507f1f77bcf86cd799439011"
            
            response = self.client.post("/api/v1/user-channel-subscriptions/quick-add", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Channel subscription created successfully"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_subscription_success(self):
        """Test PUT /api/v1/user-channel-subscriptions/{subscription_id} with valid data"""
        subscription_id = "507f1f77bcf86cd799439011"
        updates = {"is_active": False}
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.update_subscription") as mock_update:
            mock_update.return_value = True
            
            response = self.client.put(f"/api/v1/user-channel-subscriptions/{subscription_id}", json=updates)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Subscription updated successfully"
            mock_update.assert_called_once_with(subscription_id, updates)

    @pytest.mark.asyncio
    async def test_update_subscription_not_found(self):
        """Test PUT /api/v1/user-channel-subscriptions/{subscription_id} with non-existent subscription"""
        subscription_id = "507f1f77bcf86cd799439011"
        updates = {"is_active": False}
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.update_subscription") as mock_update:
            mock_update.return_value = False
            
            response = self.client.put(f"/api/v1/user-channel-subscriptions/{subscription_id}", json=updates)
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_toggle_subscription_success(self):
        """Test POST /api/v1/user-channel-subscriptions/{subscription_id}/toggle"""
        subscription_id = "507f1f77bcf86cd799439011"
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.toggle_subscription_active") as mock_toggle:
            mock_toggle.return_value = True
            
            response = self.client.post(f"/api/v1/user-channel-subscriptions/{subscription_id}/toggle")
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Subscription status toggled successfully"
            mock_toggle.assert_called_once_with(subscription_id)

    @pytest.mark.asyncio
    async def test_toggle_subscription_not_found(self):
        """Test POST /api/v1/user-channel-subscriptions/{subscription_id}/toggle with non-existent subscription"""
        subscription_id = "507f1f77bcf86cd799439011"
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.toggle_subscription_active") as mock_toggle:
            mock_toggle.return_value = False
            
            response = self.client.post(f"/api/v1/user-channel-subscriptions/{subscription_id}/toggle")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_subscription_success(self):
        """Test DELETE /api/v1/user-channel-subscriptions/{subscription_id}"""
        subscription_id = "507f1f77bcf86cd799439011"
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.delete_subscription") as mock_delete:
            mock_delete.return_value = True
            
            response = self.client.delete(f"/api/v1/user-channel-subscriptions/{subscription_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Subscription deleted successfully"
            mock_delete.assert_called_once_with(subscription_id)

    @pytest.mark.asyncio
    async def test_delete_subscription_not_found(self):
        """Test DELETE /api/v1/user-channel-subscriptions/{subscription_id} with non-existent subscription"""
        subscription_id = "507f1f77bcf86cd799439011"
        
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.delete_subscription") as mock_delete:
            mock_delete.return_value = False
            
            response = self.client.delete(f"/api/v1/user-channel-subscriptions/{subscription_id}")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_cors_options_request(self):
        """Test OPTIONS request for CORS preflight"""
        response = self.client.options("/api/v1/user-channel-subscriptions/")
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_cors_options_request_with_id(self):
        """Test OPTIONS request for CORS preflight with subscription ID"""
        subscription_id = "507f1f77bcf86cd799439011"
        response = self.client.options(f"/api/v1/user-channel-subscriptions/{subscription_id}")
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test API error handling when service raises exception"""
        with patch("app.api.v1.endpoints.user_channel_subscriptions.UserChannelSubscriptionService.get_user_subscriptions") as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            response = self.client.get("/api/v1/user-channel-subscriptions/?user_id=123")
            
            assert response.status_code == 500
            data = response.json()
            assert "Database error" in data["detail"]







