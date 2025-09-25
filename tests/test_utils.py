#!/usr/bin/env python3
"""
Test utilities for generating test data
"""
import random
import string
from datetime import datetime
from typing import Dict, Any

from app.models.user_channel_subscription import UserChannelSubscriptionResponse


def generate_random_channel_name(length: int = 12) -> str:
    """Generate a random channel name that's unlikely to exist"""
    # Use timestamp + random string to ensure uniqueness
    timestamp = str(int(datetime.now().timestamp()))[-6:]  # Last 6 digits of timestamp
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"test_channel_{timestamp}_{random_part}"


def generate_random_user_id() -> int:
    """Generate a random user ID"""
    return random.randint(100000000, 999999999)


def generate_random_channel_id() -> str:
    """Generate a random channel ID (negative for supergroups)"""
    return f"-{random.randint(1000000000000, 9999999999999)}"


def generate_test_subscription_data(
    user_id: int = None,
    channel_id: str = None,
    channel_username: str = None,
    topic_id: int = None,
    is_active: bool = True
) -> Dict[str, Any]:
    """Generate test subscription data with random values"""
    if user_id is None:
        user_id = generate_random_user_id()
    if channel_id is None:
        channel_id = generate_random_channel_id()
    if channel_username is None:
        channel_username = f"@{generate_random_channel_name()}"
    if topic_id is None:
        topic_id = random.randint(1000, 9999) if random.choice([True, False]) else None

    return {
        "_id": f"test_id_{random.randint(100000, 999999)}",
        "user_id": user_id,
        "channel_id": channel_id,
        "channel_username": channel_username,
        "channel_title": f"Test Channel {random.randint(1000, 9999)}",
        "channel_link": f"https://t.me/{channel_username[1:]}",
        "topic_id": topic_id,
        "topic_title": f"Test Topic {random.randint(100, 999)}" if topic_id else None,
        "is_active": is_active,
        "monitor_all_topics": False,
        "monitored_topics": [],
        "created_at": datetime(2025, 1, 1, 12, 0, 0),
        "updated_at": datetime(2025, 1, 1, 12, 0, 0)
    }


def generate_test_subscription_response(
    user_id: int = None,
    channel_id: str = None,
    channel_username: str = None,
    topic_id: int = None,
    is_active: bool = True
) -> UserChannelSubscriptionResponse:
    """Generate test subscription response with random values"""
    data = generate_test_subscription_data(
        user_id=user_id,
        channel_id=channel_id,
        channel_username=channel_username,
        topic_id=topic_id,
        is_active=is_active
    )
    
    return UserChannelSubscriptionResponse(
        id=data["_id"],
        user_id=data["user_id"],
        channel_id=data["channel_id"],
        channel_username=data["channel_username"],
        channel_title=data["channel_title"],
        channel_link=data["channel_link"],
        topic_id=data["topic_id"],
        topic_title=data["topic_title"],
        is_active=data["is_active"],
        monitor_all_topics=data["monitor_all_topics"],
        monitored_topics=data["monitored_topics"],
        created_at=data["created_at"],
        updated_at=data["updated_at"]
    )


def generate_test_channel_info(
    channel_id: int = None,
    channel_username: str = None,
    topic_id: int = None
) -> Dict[str, Any]:
    """Generate test channel info with random values"""
    if channel_id is None:
        channel_id = random.randint(-1000000000000, -100000000000)
    if channel_username is None:
        channel_username = f"@{generate_random_channel_name()}"
    if topic_id is None:
        topic_id = random.randint(1000, 9999) if random.choice([True, False]) else None

    return {
        "channel_id": channel_id,
        "channel_username": channel_username,
        "channel_title": f"Test Channel {random.randint(1000, 9999)}",
        "channel_link": f"https://t.me/{channel_username[1:]}",
        "topic_id": topic_id
    }
