import pytest

from app.services.user_channel_subscription_service import (
    UserChannelSubscriptionService,
)


class TestChannelParsing:
    """Test cases for channel input parsing functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = UserChannelSubscriptionService()

    def test_parse_tme_url_with_topic(self):
        """Test parsing t.me URL with topic ID"""
        test_cases = [
            ("https://t.me/rent_comissionfree/2629", "rent_comissionfree", 2629, "https://t.me/rent_comissionfree/2629"),
            ("http://t.me/channel_name/123", "channel_name", 123, "https://t.me/channel_name/123"),
            ("t.me/test_channel/456", "test_channel", 456, "https://t.me/test_channel/456"),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id is None
            assert topic_title is None

    def test_parse_tme_url_without_topic(self):
        """Test parsing t.me URL without topic ID"""
        test_cases = [
            ("https://t.me/rent_comissionfree", "rent_comissionfree", None, "https://t.me/rent_comissionfree"),
            ("http://t.me/channel_name", "channel_name", None, "https://t.me/channel_name"),
            ("t.me/test_channel", "test_channel", None, "https://t.me/test_channel"),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id is None
            assert topic_title is None

    def test_parse_username_with_at_prefix(self):
        """Test parsing username with @ prefix"""
        test_cases = [
            ("@rent_comissionfree", "rent_comissionfree", None, "https://t.me/rent_comissionfree"),
            ("@channel_name", "channel_name", None, "https://t.me/channel_name"),
            ("@test_channel", "test_channel", None, "https://t.me/test_channel"),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id is None
            assert topic_title is None

    def test_parse_username_without_at_prefix(self):
        """Test parsing username without @ prefix"""
        test_cases = [
            ("rent_comissionfree", "rent_comissionfree", None, "https://t.me/rent_comissionfree"),
            ("channel_name", "channel_name", None, "https://t.me/channel_name"),
            ("test_channel", "test_channel", None, "https://t.me/test_channel"),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id is None
            assert topic_title is None

    def test_parse_channel_id_negative(self):
        """Test parsing negative channel ID"""
        test_cases = [
            ("-1001827102719", None, None, None, -1001827102719),
            ("-1001234567890", None, None, None, -1001234567890),
            ("-1009876543210", None, None, None, -1009876543210),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link, expected_channel_id in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id == expected_channel_id, f"Failed for input: {channel_input}"
            assert topic_title is None

    def test_parse_channel_id_positive(self):
        """Test parsing positive channel ID"""
        test_cases = [
            ("1001827102719", None, None, None, 1001827102719),
            ("1001234567890", None, None, None, 1001234567890),
            ("1009876543210", None, None, None, 1009876543210),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link, expected_channel_id in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id == expected_channel_id, f"Failed for input: {channel_input}"
            assert topic_title is None

    def test_parse_channel_id_with_topic(self):
        """Test parsing channel ID with topic"""
        test_cases = [
            ("-1001827102719:2629", None, 2629, None, -1001827102719),
            ("-1001234567890:123", None, 123, None, -1001234567890),
            ("1009876543210:456", None, 456, None, 1009876543210),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link, expected_channel_id in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id == expected_channel_id, f"Failed for input: {channel_input}"
            assert topic_title is None

    def test_parse_edge_cases(self):
        """Test parsing edge cases"""
        test_cases = [
            # Empty string
            ("", "", None, "https://t.me/"),
            
            # Whitespace
            ("  @channel  ", "channel", None, "https://t.me/channel"),
            
            # Complex usernames
            ("channel_with_underscores", "channel_with_underscores", None, "https://t.me/channel_with_underscores"),
            ("channel-with-dashes", "channel-with-dashes", None, "https://t.me/channel-with-dashes"),
            ("channel123numbers", "channel123numbers", None, "https://t.me/channel123numbers"),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: '{channel_input}'"
            assert topic_id == expected_topic, f"Failed for input: '{channel_input}'"
            assert link == expected_link, f"Failed for input: '{channel_input}'"
            assert channel_id is None
            assert topic_title is None

    def test_parse_invalid_formats(self):
        """Test parsing invalid formats (should fallback gracefully)"""
        test_cases = [
            # Invalid URLs
            ("https://example.com/channel", "https://example.com/channel", None, "https://t.me/https://example.com/channel"),
            
            # Mixed formats (after removing @ prefix)
            ("@channel/123", "channel/123", None, "https://t.me/channel/123"),
            
            # Special characters
            ("channel@domain.com", "channel@domain.com", None, "https://t.me/channel@domain.com"),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link in test_cases:
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            # These should fall back to default parsing (treat as username)
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id is None
            assert topic_title is None

    def test_parse_real_world_examples(self):
        """Test parsing real-world examples"""
        real_examples = [
            # Real channel examples
            ("https://t.me/rent_comissionfree/2629", "rent_comissionfree", 2629, "https://t.me/rent_comissionfree/2629"),
            ("@rent_comissionfree", "rent_comissionfree", None, "https://t.me/rent_comissionfree"),
            ("-1001827102719", None, None, None, -1001827102719),
            ("-1001827102719:2629", None, 2629, None, -1001827102719),
            
            # Other common formats
            ("t.me/realestate_armenia", "realestate_armenia", None, "https://t.me/realestate_armenia"),
            ("https://t.me/apartment_yerevan/123", "apartment_yerevan", 123, "https://t.me/apartment_yerevan/123"),
        ]
        
        for channel_input, expected_username, expected_topic, expected_link, *expected_channel_id in real_examples:
            if expected_channel_id:
                expected_channel_id = expected_channel_id[0]
            else:
                expected_channel_id = None
                
            username, topic_id, link, channel_id, topic_title = self.service._parse_channel_input(channel_input)
            
            assert username == expected_username, f"Failed for input: {channel_input}"
            assert topic_id == expected_topic, f"Failed for input: {channel_input}"
            assert link == expected_link, f"Failed for input: {channel_input}"
            assert channel_id == expected_channel_id, f"Failed for input: {channel_input}"
            assert topic_title is None
