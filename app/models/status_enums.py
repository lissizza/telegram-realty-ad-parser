"""
Centralized status enums for different entities
"""

from enum import Enum


class IncomingMessageStatus(str, Enum):
    """Status for incoming message processing"""
    PENDING = "pending"              # Message received, waiting for processing
    PROCESSING = "processing"        # Currently being processed by LLM
    PARSED = "parsed"               # Successfully parsed as real estate ad
    NOT_REAL_ESTATE = "not_real_estate"  # Not identified as real estate
    SPAM_FILTERED = "spam_filtered"  # Filtered as spam
    MEDIA_ONLY = "media_only"       # Message contains only media without text
    ERROR = "error"                 # Error during processing
    DUPLICATE = "duplicate"         # Duplicate message (same content)
    SKIPPED = "skipped"             # Skipped for other reasons


class RealEstateAdStatus(str, Enum):
    """Status for real estate ad processing"""
    PENDING = "pending"             # Ad created, waiting for processing
    PROCESSING = "processing"       # Currently being processed
    COMPLETED = "completed"         # Successfully processed and ready
    FORWARDED = "forwarded"         # Ad has been forwarded to users (no more forwards)
    FAILED = "failed"              # Processing failed
    INVALID = "invalid"            # Invalid or malformed ad data


class OutgoingPostStatus(str, Enum):
    """Status for outgoing post delivery"""
    PENDING = "pending"             # Post created, waiting to be sent
    SENDING = "sending"            # Currently being sent
    SENT = "sent"                  # Successfully sent
    FAILED = "failed"              # Failed to send
    DELIVERED = "delivered"        # Delivered to recipient
    READ = "read"                  # Read by recipient (if supported)


class FilterMatchStatus(str, Enum):
    """Status for filter matching"""
    PENDING = "pending"            # Waiting for filter check
    MATCHED = "matched"            # Matched user filters
    NOT_MATCHED = "not_matched"    # Did not match any filters
    ERROR = "error"               # Error during filter check
