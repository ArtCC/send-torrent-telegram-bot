"""
RSS Manager Service
Handles RSS feed URL storage and retrieval.
"""

import os
import json
from typing import Dict, Optional, List, Tuple

from bot.config import logger, RSS_STORAGE_FILE

# Maximum number of RSS feeds per user
MAX_RSS_FEEDS = 10


def load_rss_data() -> Dict[int, Dict[str, str]]:
    """Load RSS data from JSON file. Returns {chat_id: {name: url}}."""
    try:
        if os.path.exists(RSS_STORAGE_FILE):
            with open(RSS_STORAGE_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to integers and handle migration
                result = {}
                for k, v in data.items():
                    chat_id = int(k)
                    # Migration: if v is a string (old format), convert to new format
                    if isinstance(v, str):
                        result[chat_id] = {"RSS Feed": v}
                    else:
                        result[chat_id] = v
                return result
        return {}
    except Exception as e:
        logger.error(f"Error loading RSS data: {e}")
        return {}


def _save_rss_data(data: Dict[int, Dict[str, str]]) -> None:
    """Save RSS data to JSON file."""
    try:
        with open(RSS_STORAGE_FILE, 'w') as f:
            json.dump({str(k): v for k, v in data.items()}, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving RSS data: {e}")
        raise


def save_rss_url(chat_id: int, name: str, rss_url: str) -> Tuple[bool, str]:
    """
    Save RSS URL for a chat ID with a name.
    Returns (success, message).
    """
    try:
        data = load_rss_data()
        
        if chat_id not in data:
            data[chat_id] = {}
        
        user_feeds = data[chat_id]
        
        # Check limit only if adding new (not updating existing)
        if name not in user_feeds and len(user_feeds) >= MAX_RSS_FEEDS:
            return False, f"Has alcanzado el límite de {MAX_RSS_FEEDS} feeds RSS"
        
        user_feeds[name] = rss_url
        _save_rss_data(data)
        logger.info(f"RSS URL '{name}' saved for chat ID {chat_id}")
        return True, "RSS guardado correctamente"
    except Exception as e:
        logger.error(f"Error saving RSS URL: {e}")
        return False, "Error al guardar el RSS"


def delete_rss_url(chat_id: int, name: str) -> bool:
    """Delete RSS URL by name for a chat ID. Returns True if deleted."""
    try:
        data = load_rss_data()
        if chat_id in data and name in data[chat_id]:
            del data[chat_id][name]
            # Clean up empty dict
            if not data[chat_id]:
                del data[chat_id]
            _save_rss_data(data)
            logger.info(f"RSS URL '{name}' deleted for chat ID {chat_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting RSS URL: {e}")
        return False


def get_rss_url(chat_id: int, name: str = None) -> Optional[str]:
    """Get RSS URL by name for a chat ID. If name is None, returns first RSS (for compatibility)."""
    data = load_rss_data()
    user_feeds = data.get(chat_id, {})
    
    if name:
        return user_feeds.get(name)
    
    # Compatibility: return first feed if exists
    if user_feeds:
        return next(iter(user_feeds.values()))
    return None


def get_all_rss(chat_id: int) -> Dict[str, str]:
    """Get all RSS feeds for a chat ID. Returns {name: url}."""
    data = load_rss_data()
    return data.get(chat_id, {})


def get_rss_count(chat_id: int) -> int:
    """Get the number of RSS feeds for a chat ID."""
    data = load_rss_data()
    return len(data.get(chat_id, {}))


def has_rss(chat_id: int) -> bool:
    """Check if user has any RSS feeds."""
    return get_rss_count(chat_id) > 0
