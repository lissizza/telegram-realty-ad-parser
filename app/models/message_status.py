from enum import Enum

class MessageStatus(str, Enum):
    """Message processing status"""
    RECEIVED = "received"  # Message received from channel
    MEDIA_ONLY = "media_only"  # Message contains only media without text
    SPAM_FILTERED = "spam_filtered"  # Filtered as spam
    NOT_REAL_ESTATE = "not_real_estate"  # Not identified as real estate
    PARSING = "parsing"  # Currently being parsed by LLM
    PARSED = "parsed"  # Successfully parsed as real estate ad
    FILTERED = "filtered"  # Matched user filters
    FORWARDED = "forwarded"  # Forwarded to user
    ERROR = "error"  # Error during processing
