"""
RSS Manager Service
Handles RSS feed URL storage and retrieval.
"""

import os
import json
from typing import Dict, Optional

from bot.config import logger, RSS_STORAGE_FILE


def load_rss_urls() -> Dict[int, str]:
    """Load RSS URLs from JSON file."""
    try:
        if os.path.exists(RSS_STORAGE_FILE):
            with open(RSS_STORAGE_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to integers
                return {int(k): v for k, v in data.items()}
        return {}
    except Exception as e:
        logger.error(f"Error loading RSS URLs: {e}")
        return {}


def save_rss_url(chat_id: int, rss_url: str) -> None:
    """Save RSS URL for a chat ID."""
    try:
        urls = load_rss_urls()
        urls[chat_id] = rss_url
        # Convert integer keys to strings for JSON
        with open(RSS_STORAGE_FILE, 'w') as f:
            json.dump({str(k): v for k, v in urls.items()}, f, indent=2)
        logger.info(f"RSS URL saved for chat ID {chat_id}")
    except Exception as e:
        logger.error(f"Error saving RSS URL: {e}")
        raise


def delete_rss_url(chat_id: int) -> bool:
    """Delete RSS URL for a chat ID. Returns True if deleted, False if not found."""
    try:
        urls = load_rss_urls()
        if chat_id in urls:
            del urls[chat_id]
            with open(RSS_STORAGE_FILE, 'w') as f:
                json.dump({str(k): v for k, v in urls.items()}, f, indent=2)
            logger.info(f"RSS URL deleted for chat ID {chat_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting RSS URL: {e}")
        return False


def get_rss_url(chat_id: int) -> Optional[str]:
    """Get RSS URL for a chat ID."""
    urls = load_rss_urls()
    return urls.get(chat_id)
