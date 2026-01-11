"""
Bot Models
Data classes and type definitions.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class TorrentFile:
    """Represents a torrent file to be processed."""
    name: str
    size: float  # in KB
    success: bool
    error: str = ""


# Batch processing state
batch_queues: Dict[int, List[TorrentFile]] = {}
batch_tasks: Dict[int, asyncio.Task] = {}
