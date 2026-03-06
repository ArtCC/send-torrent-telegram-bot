"""
Bot Configuration
Environment variables and global settings.
"""

import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Reduce httpx logging verbosity (suppress polling requests)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(",")
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "/watch")
RSS_STORAGE_FILE = os.getenv("RSS_STORAGE_FILE", "rss_urls.json")
AUTO_DELETE_WATCH_TORRENTS = os.getenv("AUTO_DELETE_WATCH_TORRENTS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

try:
    WATCH_CLEANUP_DELAY_SECONDS = max(0.0, float(os.getenv("WATCH_CLEANUP_DELAY_SECONDS", "30")))
except ValueError:
    WATCH_CLEANUP_DELAY_SECONDS = 30.0

# Batch processing configuration
BATCH_TIMEOUT = 2.0  # seconds to wait for more files

# Validate configuration
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

if not ALLOWED_CHAT_IDS or ALLOWED_CHAT_IDS == [""]:
    raise ValueError("ALLOWED_CHAT_IDS environment variable is required")

# Convert chat IDs to integers and filter empty strings
ALLOWED_CHAT_IDS = [int(chat_id.strip()) for chat_id in ALLOWED_CHAT_IDS if chat_id.strip()]

# Ensure watch folder exists
Path(WATCH_FOLDER).mkdir(parents=True, exist_ok=True)

logger.info(f"Bot configured with {len(ALLOWED_CHAT_IDS)} allowed chat ID(s)")
logger.info(f"Watch folder: {WATCH_FOLDER}")
logger.info(
    "Auto cleanup in watch folder: %s (delay: %ss)",
    "enabled" if AUTO_DELETE_WATCH_TORRENTS else "disabled",
    WATCH_CLEANUP_DELAY_SECONDS,
)
