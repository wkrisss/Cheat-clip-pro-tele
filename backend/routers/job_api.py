"""Job API router for Telegram bot integration.
Uses SQLite job queue for persistence, bypasses browser dependency."""
import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from pathlib import Path

from backend.config import TEMP_DIR, EXPORTS_DIR, logger
from backend.services.job_queue import (
    create_job, get_job, get_job_clips, get_job_output_paths, 
    update_job, get_pending_jobs, get_user_config, create_or_update_user_config
)
from backend.services.cheat_clip_worker import start_worker, stop_worker
from backend.routers.analyze import analyze_video

router = APIRouter(prefix="/api/jobs", tags=["job queue"])


@router.post("/submit")
async def submit_job(
    video_url: str = Form(...),
    config: Optional[str] = Form(None),
    user_id: str = Form("default"),
    background_tasks: BackgroundTasks = None
):
    """Submit a new clipping job. Returns job_id immediately."""
    try:
        config_data = json.loads(config) if config else {}
        
        job_id = create_job(
            user_id=user_id,
            video_url=video_url,
            config=config_data
        )
        
        # Start worker if not running
        start_worker()
        
        return {"status": "queued", "job_id": job_id, "message": "Job queued for processing"}
    except Exception as e:
        logger.error(f"Failed to submit job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and progress."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    clips = get_job_clips(job_id)
    outputs = get_job_output_paths(job_id)
    
    return {
        "id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "video_url": job["video_url"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "clips": clips,
        "outputs": outputs,
        "error": job.get("error")
    }


@router.get("/user/{user_id}")
async def list_user_jobs(user_id: str, limit: int = 20):
    """List jobs for a specific user."""
    import sqlite3
    conn = sqlite3.connect(Path(__file__).parent.parent / "cheat_clip_jobs.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, status, progress, video_url, created_at, updated_at, error
        FROM jobs WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?""", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    return {
        "jobs": [
            {
                "id": r[0], "status": r[1], "progress": r[2],
                "video_url": r[3], "created_at": r[4], "updated_at": r[5],
                "error": r[6]
            }
            for r in rows
        ]
    }


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a pending/running job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] in ["completed", "failed"]:
        return {"status": job["status"], "message": "Cannot cancel completed/failed job"}
    
    update_job(job_id, status="cancelled", progress=0)
    return {"status": "cancelled", "message": "Job cancelled"}


@router.get("/settings/{user_id}")
async def get_user_settings(user_id: str):
    """Get user's clipping settings."""
    config = get_user_config(user_id)
    return config or {}


@router.post("/settings/{user_id}")
async def set_user_settings(user_id: str, settings: dict):
    """Update user's clipping settings."""
    create_or_update_user_config(user_id, settings)
    return {"status": "ok", "message": "Settings saved"}


# Worker control endpoints
@router.post("/worker/start")
async def start_background_worker():
    """Start the background worker."""
    start_worker()
    return {"status": "ok", "message": "Worker started"}


@router.post("/worker/stop")
async def stop_background_worker():
    """Stop the background worker."""
    stop_worker()
    return {"status": "ok", "message": "Worker stopped"}


@router.get("/worker/status")
async def get_worker_status():
    """Get background worker status."""
    from backend.services.cheat_clip_worker import _worker_task
    return {"running": _worker_task is not None}