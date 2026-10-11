"""Job queue service using SQLite backend."""
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.database import (
    init_db, create_job, update_job, get_job, get_jobs_by_user,
    save_clips, save_output_paths, get_or_create_config, update_config
)

logger = logging.getLogger(__name__)


def init_database():
    """Initialize database - wrapper for backend compatibility."""
    init_db()


def get_pending_jobs() -> List[Dict[str, Any]]:
    """Get all pending/running jobs."""
    from backend.database import get_all_jobs
    jobs = get_all_jobs()
    # Only queued jobs are claimable. Analyzing jobs belong to an existing worker task.
    return [j for j in jobs if j["status"] == "queued"]


def get_user_config(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user config."""
    return get_or_create_config(user_id)


def create_or_update_user_config(user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update user config."""
    return update_config(user_id, config)


def get_job_clips(job_id: str) -> List[Dict[str, Any]]:
    """Get clips for job."""
    job = get_job(job_id)
    if not job or not job.get("clips_json"):
        return []
    try:
        return json.loads(job["clips_json"])
    except Exception:
        return []


def get_job_output_paths(job_id: str) -> List[str]:
    """Get output paths for job."""
    job = get_job(job_id)
    if not job or not job.get("output_paths"):
        return []
    try:
        return json.loads(job["output_paths"])
    except Exception:
        return []