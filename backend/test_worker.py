#!/usr/bin/env python3
"""Test worker with mock transcript."""

import asyncio
import logging
import sys

sys.path.insert(0, "/home/wahyu/cheat-clip-pro/backend")
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test-worker")

from services.job_queue import init_database, get_pending_jobs, update_job_status, update_job_output
from services.cheat_clip_worker import start_worker, stop_worker

init_database()
start_worker()


async def test_job():
    """Create test job and process it."""
    from routers.analyze import AnalyzeRequest
    
    request = AnalyzeRequest(
        video_url="file:///home/wahyu/cheat-clip-pro/backend/test_video.mp4",
        watermark_enabled=True,
        watermark_type="image",
        watermark_image_path="/home/wahyu/cheat-clip-pro/backend/assets/watermark_logo.png",
        watermark_size=25,
        watermark_opacity=80
    )
    
    from routers.analyze import analyze_video
    async for event in analyze_video(request):
        print(f"Event: {event}")


if __name__ == "__main__":
    asyncio.run(test_job())
    stop_worker()
