#!/usr/bin/env python3
"""Standalone worker process for Cheat Clip Pro."""

import asyncio
import logging
import sys

from backend.services.cheat_clip_worker import start_worker

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cheat-clip-pro")


async def main():
    """Start worker and run indefinitely."""
    logger.info("[Worker] Starting standalone worker...")
    start_worker()
    logger.info("[Worker] Worker started. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("[Worker] Shutdown requested.")


if __name__ == "__main__":
    asyncio.run(main())
