"""
Channel ID utilities for consistent handling of Telegram channel IDs.

This module provides utilities to normalize and convert between different
formats of Telegram channel IDs to ensure consistency across the application.
"""

from typing import Union


def normalize_channel_id(channel_id: Union[int, str]) -> int:
    """
    Normalize a channel ID to the standard Telegram format.
    
    Args:
        channel_id: Channel ID in any format (int, str with/without -100 prefix)
        
    Returns:
        int: Normalized channel ID in Telegram format (e.g., -1001843374707)
        
    Examples:
        normalize_channel_id(1843374707) -> -1001843374707
        normalize_channel_id("1843374707") -> -1001843374707
        normalize_channel_id(-1001843374707) -> -1001843374707
        normalize_channel_id("-1001843374707") -> -1001843374707
    """
    if isinstance(channel_id, str):
        try:
            channel_id = int(channel_id)
        except ValueError:
            raise ValueError(f"Invalid channel ID format: {channel_id}")
    
    # If it's already a negative number (Telegram format), return as is
    if channel_id < 0:
        return channel_id
    
    # If it's positive, add the -100 prefix for supergroups/channels
    return -1000000000000 - channel_id


def channel_id_to_string(channel_id: Union[int, str]) -> str:
    """
    Convert channel ID to string format for database storage.
    
    Args:
        channel_id: Channel ID in any format
        
    Returns:
        str: Channel ID as string (e.g., "-1001843374707")
    """
    normalized = normalize_channel_id(channel_id)
    return str(normalized)


def channel_id_to_db_format(channel_id: Union[int, str]) -> str:
    """
    Convert channel ID to database format (without -100 prefix).
    
    Args:
        channel_id: Channel ID in any format
        
    Returns:
        str: Channel ID in database format (e.g., "1843374707")
        
    Note:
        This is used for backward compatibility with existing database records.
        New code should use channel_id_to_string() for consistency.
    """
    normalized = normalize_channel_id(channel_id)
    if normalized < 0:
        # Remove the -100 prefix
        return str(normalized)[4:]
    return str(normalized)


def is_telegram_channel_id(channel_id: Union[int, str]) -> bool:
    """
    Check if a channel ID is in Telegram format (negative number).
    
    Args:
        channel_id: Channel ID to check
        
    Returns:
        bool: True if in Telegram format, False otherwise
    """
    try:
        normalized = normalize_channel_id(channel_id)
        return normalized < 0
    except ValueError:
        return False


def get_channel_display_id(channel_id: Union[int, str]) -> str:
    """
    Get a display-friendly version of channel ID.
    
    Args:
        channel_id: Channel ID in any format
        
    Returns:
        str: Display-friendly channel ID (e.g., "-1001843374707" or "@username")
    """
    normalized = normalize_channel_id(channel_id)
    return str(normalized)
