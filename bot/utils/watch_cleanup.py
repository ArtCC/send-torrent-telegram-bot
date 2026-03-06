"""
Watch Folder Cleanup Utilities
Helpers to remove .torrent files from the watch folder after a configurable delay.
"""

import asyncio
import os

from bot.config import logger, AUTO_DELETE_WATCH_TORRENTS, WATCH_CLEANUP_DELAY_SECONDS


async def _delete_torrent_later(file_path: str, delay_seconds: float) -> None:
    """Delete the given file after the configured delay."""
    try:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info("Deleted torrent from watch folder: %s", file_path)
    except Exception as exc:
        logger.warning("Could not delete torrent file '%s': %s", file_path, exc)


def schedule_torrent_cleanup(file_path: str) -> None:
    """Schedule cleanup only when auto-delete is enabled."""
    if not AUTO_DELETE_WATCH_TORRENTS:
        return

    asyncio.create_task(_delete_torrent_later(file_path, WATCH_CLEANUP_DELAY_SECONDS))
