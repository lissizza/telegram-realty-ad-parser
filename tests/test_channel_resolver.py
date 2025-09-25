"""
Tests for channel resolver service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.channel_resolver_service import ChannelResolverService


class TestChannelResolverService:
    """Test cases for ChannelResolverService"""

    @pytest.fixture
    def mock_client(self):
        """Mock Telegram client"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def resolver(self, mock_client):
        """Channel resolver service with mock client"""
        return ChannelResolverService(mock_client)

    @pytest.mark.asyncio
    async def test_resolve_from_username(self, resolver, mock_client):
        """Test resolving channel from username"""
        # Mock channel entity
        mock_channel = MagicMock()
        mock_channel.id = -1001827102719
        mock_channel.username = "rent_comissionfree"
        mock_channel.title = "Rent Commission Free"
        mock_channel.__class__.__name__ = "Channel"
        
        mock_client.get_entity.return_value = mock_channel
        
        result = await resolver.resolve_channel_info("rent_comissionfree")
        
        assert result is not None
        assert result["channel_id"] == -1001827102719
        assert result["channel_username"] == "@rent_comissionfree"
        assert result["channel_title"] == "Rent Commission Free"
        assert result["channel_link"] == "https://t.me/rent_comissionfree"
        assert result["topic_id"] is None

    @pytest.mark.asyncio
    async def test_resolve_from_channel_id(self, resolver, mock_client):
        """Test resolving channel from channel ID"""
        # Mock channel entity
        mock_channel = MagicMock()
        mock_channel.id = -1001827102719
        mock_channel.username = None
        mock_channel.title = "Rent Commission Free"
        mock_channel.__class__.__name__ = "Channel"
        
        mock_client.get_entity.return_value = mock_channel
        
        result = await resolver.resolve_channel_info("-1001827102719")
        
        assert result is not None
        assert result["channel_id"] == -1001827102719
        assert result["channel_username"] == "-1001827102719"
        assert result["channel_title"] == "Rent Commission Free"
        assert result["channel_link"] == "https://t.me/c/1827102719"
        assert result["topic_id"] is None

    @pytest.mark.asyncio
    async def test_resolve_from_url(self, resolver, mock_client):
        """Test resolving channel from URL"""
        # Mock channel entity
        mock_channel = MagicMock()
        mock_channel.id = -1001827102719
        mock_channel.username = "rent_comissionfree"
        mock_channel.title = "Rent Commission Free"
        mock_channel.__class__.__name__ = "Channel"
        
        mock_client.get_entity.return_value = mock_channel
        
        result = await resolver.resolve_channel_info("https://t.me/rent_comissionfree")
        
        assert result is not None
        assert result["channel_id"] == -1001827102719
        assert result["channel_username"] == "@rent_comissionfree"
        assert result["channel_title"] == "Rent Commission Free"
        assert result["channel_link"] == "https://t.me/rent_comissionfree"
        assert result["topic_id"] is None

    @pytest.mark.asyncio
    async def test_resolve_from_url_with_topic(self, resolver, mock_client):
        """Test resolving channel from URL with topic"""
        # Mock channel entity
        mock_channel = MagicMock()
        mock_channel.id = -1001827102719
        mock_channel.username = "rent_comissionfree"
        mock_channel.title = "Rent Commission Free"
        mock_channel.__class__.__name__ = "Channel"
        
        mock_client.get_entity.return_value = mock_channel
        
        result = await resolver.resolve_channel_info("https://t.me/rent_comissionfree/2629")
        
        assert result is not None
        assert result["channel_id"] == -1001827102719
        assert result["channel_username"] == "@rent_comissionfree"
        assert result["channel_title"] == "Rent Commission Free"
        assert result["channel_link"] == "https://t.me/rent_comissionfree"
        assert result["topic_id"] == 2629

    @pytest.mark.asyncio
    async def test_resolve_from_channel_id_with_topic(self, resolver, mock_client):
        """Test resolving channel from channel ID with topic"""
        # Mock channel entity
        mock_channel = MagicMock()
        mock_channel.id = -1001827102719
        mock_channel.username = "rent_comissionfree"
        mock_channel.title = "Rent Commission Free"
        mock_channel.__class__.__name__ = "Channel"
        
        mock_client.get_entity.return_value = mock_channel
        
        result = await resolver.resolve_channel_info("-1001827102719:2629")
        
        assert result is not None
        assert result["channel_id"] == -1001827102719
        assert result["channel_username"] == "@rent_comissionfree"
        assert result["channel_title"] == "Rent Commission Free"
        assert result["channel_link"] == "https://t.me/rent_comissionfree"
        assert result["topic_id"] == 2629

    @pytest.mark.asyncio
    async def test_resolve_invalid_input(self, resolver, mock_client):
        """Test resolving invalid input"""
        mock_client.get_entity.side_effect = Exception("Channel not found")
        
        result = await resolver.resolve_channel_info("invalid_channel")
        
        assert result is None

    def test_validate_channel_input(self, resolver):
        """Test channel input validation"""
        # Valid inputs
        assert resolver.validate_channel_input("@rent_comissionfree") == True
        assert resolver.validate_channel_input("rent_comissionfree") == True
        assert resolver.validate_channel_input("https://t.me/rent_comissionfree") == True
        assert resolver.validate_channel_input("https://t.me/rent_comissionfree/2629") == True
        assert resolver.validate_channel_input("https://t.me/c/1827102719") == True
        assert resolver.validate_channel_input("-1001827102719") == True
        assert resolver.validate_channel_input("-1001827102719:2629") == True
        
        # Invalid inputs
        assert resolver.validate_channel_input("") == False
        assert resolver.validate_channel_input("   ") == False
        assert resolver.validate_channel_input("invalid@format") == False
        assert resolver.validate_channel_input("https://example.com") == False
        assert resolver.validate_channel_input("123abc") == False
