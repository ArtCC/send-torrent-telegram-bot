"""
Authorization Utilities
Helper functions for user authorization.
"""

from bot.config import ALLOWED_CHAT_IDS


def is_authorized(chat_id: int) -> bool:
    """Check if the chat ID is authorized to use the bot."""
    return chat_id in ALLOWED_CHAT_IDS
