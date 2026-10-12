"""Background worker for Cheat Clip Pro that processes jobs without browser dependency."""
import asyncio
import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys

from backend.config import (
    TEMP_DIR,
    EXPORTS_DIR,
    logger,
)
from backend.services.job_queue import (
    get_job, update_job, save_clips, save_output_paths,
    get_pending_jobs, get_user_config, create_or_update_user_config
)
from backend.routers.analyze import analyze_video_internal
from backend.schemas.analyze import AnalyzeRequest, ViralClipGemini, VideoAnalysis
from backend.services.render_service import process_batch_rendering, RENDER_BATCHES
from backend.schemas.render import RenderBatchRequest, RenderSettingsModel

# In-memory cache (lightweight, not used for persistence)
_active_jobs: Dict[str, Dict[str, Any]] = {}


def get_active_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job from in-memory cache."""
    return _active_jobs.get(job_id)


def set_active_job(job_id: str, data: Dict[str, Any]):
    """Set job in in-memory cache."""
    _active_jobs[job_id] = data


def remove_active_job(job_id: str):
    """Remove job from in-memory cache."""
    if job_id in _active_jobs:
        del _active_jobs[job_id]


def _mock_video_analysis(video_url: str) -> VideoAnalysis:
    """Create mock video analysis for worker testing."""
    # Extract video ID from URL
    video_id = video_url.split("youtu.be/")[-1].split("?")[0] if "youtu.be" in video_url else ""
    video_id = video_url.split("v=")[-1].split("&")[0] if "v=" in video_url and not video_id else video_id
    video_id = video_id[:11] if video_id else "test1234567"
    
    return VideoAnalysis(
        summary=f"Test video analysis for {video_url}. Contains engaging highlights.",
        clips=[
            ViralClipGemini(
                title="Hook Moment",
                start_time=0.0,
                end_time=60.0,
                hook_time=3.0,
                virality_score=85,
                key_quotes=["This is an amazing moment you don't want to miss"],
                title_suggestion="Must Watch Clip",
                caption_suggestion="You won't believe what happens next!",
                hashtag_suggestion="#viral #trending #test"
            ),
            ViralClipGemini(
                title="Key Insight",
                start_time=0.0,
                end_time=60.0,
                hook_time=32.0,
                virality_score=72,
                key_quotes=["This changes everything about how we see this"],
                title_suggestion="Game Changer",
                caption_suggestion="This insight will blow your mind",
                hashtag_suggestion="#insight #deepdive #test"
            )
        ]
    )


async def process_job(job_id: str):
    """
    Process a job from queue.
    1. Load job config from database
    2. Analyze video
    3. Render clips
    4. Save results to database
    """
    job = get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    user_id = job.get("user_id", "default")
    video_url = job.get("video_url", "")
    config = json.loads(job.get("config", "{}"))
    
    logger.info(f"[Worker] Processing job {job_id} for user {user_id}")
    update_job(job_id, status="analyzing", progress=10)
    
    try:
        # Step 1: Analyze transcript with Gemini in-process.
        settings = config.get("settings", {})
        target_count = int(settings.get("target_clip_count", 4))
        clip_duration = int(settings.get("clip_duration_seconds", 60))
        analysis = await analyze_video_internal(AnalyzeRequest(
            url=video_url,
            duration=f"{clip_duration}s",
            target_clip_count=target_count,
            custom_prompt=config.get("custom_prompt"),
            api_key=(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        ))
        clips_data = analysis.get("clips", [])[:max(1, target_count)]
        # Preserve exciting lead-in and payoff: expand AI range by 5s each side.
        for clip in clips_data:
            clip["start_time"] = max(0.0, float(clip.get("start_time", 0)) - 5.0)
            clip["end_time"] = float(clip.get("end_time", 60)) + 5.0
        if not clips_data:
            raise RuntimeError("Gemini returned no clip candidates")
        # Save AI-selected timestamps; renderer cuts exactly these ranges.
        save_clips(job_id, clips_data)
        update_job(job_id, status="analyzed", progress=30)
        
        # Step 2: Render clips
        # Extract video_id from URL
        video_id = video_url.split("youtu.be/")[-1].split("?")[0] if "youtu.be" in video_url else ""
        video_id = video_url.split("v=")[-1].split("&")[0] if "v=" in video_url and not video_id else video_id
        if not video_id:
            video_id = f"test_{job_id[-4:]}"
        
        # Initialize batch in RENDER_BATCHES (required by process_batch_rendering)
        RENDER_BATCHES[job_id] = {
            "clips": [{"status": "pending"} for _ in clips_data],
            "overall_status": "pending",
            "current_clip_index": 0
        }
        
        render_settings = dict(config.get("render_settings", config.get("settings", {})))
        # Worker jobs created before aspect-ratio support lack this field.
        render_settings["aspect_ratio"] = settings.get("aspect_ratio", "9:16")
        render_settings["streamer_preset"] = settings.get("streamer_preset", os.environ.get("STREAMER_PRESET", "none"))
        render_settings["render_mode"] = settings.get("render_mode", os.environ.get("RENDER_MODE", "separate"))
        render_settings["caption_style"] = "none"
        render_settings["title_position"] = "none"
        render_request = RenderBatchRequest(
            video_url=video_url,
            video_id=video_id,
            clips=clips_data,
            settings=RenderSettingsModel(**render_settings),
            transcript=config.get("transcript", [])
        )
        
        output_paths = await process_batch_rendering(job_id, render_request)
        
        # Clean up batch after rendering
        RENDER_BATCHES.pop(job_id, None)
        
        if not output_paths:
            raise Exception("Render failed: no output files")
        
        # Save output paths
        save_output_paths(job_id, output_paths)
        update_job(job_id, status="completed", progress=100)
        
        # Clean up cache
        remove_active_job(job_id)
        
        logger.info(f"[Worker] Job {job_id} completed with {len(output_paths)} clips")
        
    except Exception:
        logger.exception("[Worker] Job %s failed", job_id)
        RENDER_BATCHES.pop(job_id, None)
        update_job(job_id, status="failed", error="Worker processing failed; see traceback in server log", progress=0)
        remove_active_job(job_id)


async def worker_loop():
    """
    Background worker loop that processes queued jobs.
    Runs as a background task.
    """
    logger.info("[Worker] Worker loop started")
    logger.info("[Worker] Checking for pending jobs...")
    
    while True:
        try:
            pending_jobs = get_pending_jobs()
            
            if pending_jobs:
                logger.info(f"[Worker] Found {len(pending_jobs)} pending job(s)")
                for job in pending_jobs:
                    job_id = job["id"]
                    if job_id in _active_jobs:
                        continue  # Already processing
                    set_active_job(job_id, {"status": "processing"})
                    logger.info(f"[Worker] Processing job {job_id} exclusively")
                    await process_job(job_id)
            else:
                logger.debug("[Worker] No pending jobs, sleeping 2s")
            
            await asyncio.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            logger.error(f"[Worker] Loop error: {e}")
            await asyncio.sleep(5)


# Worker instance
_worker_task: Optional[asyncio.Task] = None


def start_worker():
    """Start one worker loop for current FastAPI process."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.info("[Worker] Worker already running")
        return
    _worker_task = asyncio.create_task(worker_loop())
    logger.info("[Worker] Worker started (task created)")


def stop_worker():
    """Stop background worker."""
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        _worker_task = None
        logger.info("[Worker] Worker stopped")
