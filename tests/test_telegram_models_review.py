"""
Tests for reviewed Telegram models architecture
"""

import pytest
from datetime import datetime
from app.models.incoming_message import IncomingMessage
from app.models.outgoing_post import OutgoingPost
from app.models.telegram import RealEstateAd, PropertyType, RentalType


class TestTelegramModelsReview:
    """Test the reviewed Telegram models architecture"""
    
    def test_incoming_message_creation(self):
        """Test IncomingMessage creation for received messages"""
        message = IncomingMessage(
            id=12345,
            channel_id=67890,
            channel_title="Real Estate Channel",
            message="Сдается квартира за 250000 драм",
            date=datetime.utcnow()
        )
        
        # Basic fields
        assert message.id == 12345
        assert message.channel_id == 67890
        assert message.channel_title == "Real Estate Channel"
        assert message.message == "Сдается квартира за 250000 драм"
        
        # Default values
        assert message.processing_status == "pending"
        assert message.forwarded is False
        assert message.is_spam is None
        assert message.is_real_estate is None
        assert message.real_estate_ad_id is None
    
    def test_incoming_message_processing(self):
        """Test IncomingMessage processing workflow"""
        message = IncomingMessage(
            id=12345,
            channel_id=67890,
            channel_title="Real Estate Channel",
            message="Сдается квартира за 250000 драм",
            date=datetime.utcnow()
        )
        
        # Simulate processing
        message.processing_status = "processing"
        message.is_real_estate = True
        message.real_estate_confidence = 0.9
        message.real_estate_ad_id = "ad_123"
        message.processed_at = datetime.utcnow()
        
        assert message.processing_status == "processing"
        assert message.is_real_estate is True
        assert message.real_estate_confidence == 0.9
        assert message.real_estate_ad_id == "ad_123"
        assert message.processed_at is not None
    
    def test_outgoing_post_creation(self):
        """Test OutgoingPost creation for messages we send"""
        post = OutgoingPost(
            message="🏠 Найдено подходящее объявление!\n\nТип: Квартира\nЦена: 250,000 драм",
            sent_to="user_123",
            sent_to_type="user",
            real_estate_ad_id="ad_123"
        )
        
        # Basic fields
        assert post.message == "🏠 Найдено подходящее объявление!\n\nТип: Квартира\nЦена: 250,000 драм"
        assert post.sent_to == "user_123"
        assert post.sent_to_type == "user"
        assert post.real_estate_ad_id == "ad_123"
        
        # Default values
        assert post.status == "pending"
        assert post.sent_at is None
        assert post.error_message is None
    
    def test_outgoing_post_sending(self):
        """Test OutgoingPost sending workflow"""
        post = OutgoingPost(
            message="Test message",
            sent_to="user_123",
            sent_to_type="user"
        )
        
        # Simulate sending
        post.status = "sent"
        post.sent_at = datetime.utcnow()
        
        assert post.status == "sent"
        assert post.sent_at is not None
    
    def test_outgoing_post_failure(self):
        """Test OutgoingPost sending failure"""
        post = OutgoingPost(
            message="Test message",
            sent_to="user_123",
            sent_to_type="user"
        )
        
        # Simulate failure
        post.status = "failed"
        post.error_message = "User blocked the bot"
        
        assert post.status == "failed"
        assert post.error_message == "User blocked the bot"
    
    def test_real_estate_ad_unchanged(self):
        """Test that RealEstateAd model is unchanged"""
        ad = RealEstateAd(
            original_post_id=12345,
            original_channel_id=67890,
            original_message="Test message",
            property_type=PropertyType.APARTMENT,
            rental_type=RentalType.LONG_TERM,
            price=250000.0,
            currency="AMD"
        )
        
        assert ad.property_type == PropertyType.APARTMENT
        assert ad.rental_type == RentalType.LONG_TERM
        assert ad.price == 250000.0
        assert ad.currency == "AMD"
    
    def test_model_separation(self):
        """Test that models have clear separation of concerns"""
        
        # IncomingMessage - for received messages
        incoming = IncomingMessage(
            id=1,
            channel_id=2,
            channel_title="Channel",
            message="Test",
            date=datetime.utcnow()
        )
        
        # OutgoingPost - for messages we send
        outgoing = OutgoingPost(
            message="Test",
            sent_to="user_123"
        )
        
        # RealEstateAd - for parsed real estate data
        real_estate = RealEstateAd(
            original_post_id=1,
            original_channel_id=2,
            original_message="Test"
        )
        
        # Each model should have its specific fields
        assert hasattr(incoming, 'channel_id')
        assert hasattr(incoming, 'processing_status')
        assert not hasattr(incoming, 'sent_to')
        
        assert hasattr(outgoing, 'sent_to')
        assert hasattr(outgoing, 'status')
        assert not hasattr(outgoing, 'channel_id')
        
        assert hasattr(real_estate, 'property_type')
        assert hasattr(real_estate, 'price')
        assert not hasattr(real_estate, 'sent_to')
    
    def test_model_serialization(self):
        """Test that all models can be serialized"""
        
        # Test IncomingMessage serialization
        incoming = IncomingMessage(
            id=1,
            channel_id=2,
            channel_title="Channel",
            message="Test",
            date=datetime.utcnow()
        )
        incoming_dict = incoming.model_dump()
        assert "id" in incoming_dict
        assert "processing_status" in incoming_dict
        
        # Test OutgoingPost serialization
        outgoing = OutgoingPost(
            message="Test",
            sent_to="user_123"
        )
        outgoing_dict = outgoing.model_dump()
        assert "message" in outgoing_dict
        assert "sent_to" in outgoing_dict
        
        # Test RealEstateAd serialization
        real_estate = RealEstateAd(
            original_post_id=1,
            original_channel_id=2,
            original_message="Test"
        )
        real_estate_dict = real_estate.model_dump()
        assert "original_post_id" in real_estate_dict
        assert "property_type" in real_estate_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
