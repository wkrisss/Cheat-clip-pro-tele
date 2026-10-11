"""Persistent SQLite database for jobs and config."""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import threading

DB_PATH = Path(__file__).parent / "data" / "cheatclip.db"
lock = threading.Lock()


def get_conn():
    """Get thread-local database connection."""
    local = threading.local()
    if not hasattr(local, "conn"):
        local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        local.conn.row_factory = sqlite3.Row
        local.conn.execute("PRAGMA journal_mode=WAL")
    return local.conn


def init_db():
    """Initialize database schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cursor = conn.cursor()
    
    # Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            video_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            progress INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            config TEXT NOT NULL,
            metadata TEXT,
            clips_json TEXT,
            output_paths TEXT,
            error TEXT
        )
    """)
    
    # Config table for presets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_configs (
            user_id TEXT PRIMARY KEY,
            watermark_enabled INTEGER DEFAULT 1,
            watermark_size REAL DEFAULT 20.0,
            watermark_x REAL DEFAULT 50.0,
            watermark_y REAL DEFAULT 70.0,
            target_clips INTEGER DEFAULT 10,
            target_size_mb INTEGER DEFAULT 20,
            subtitle_enabled INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    
    conn.commit()


def create_job(user_id: str, video_url: str, config: Dict[str, Any]) -> str:
    """Create new job record."""
    job_id = f"job_{int(datetime.now().timestamp())}_{hash(video_url) % 10000:04d}"
    now = datetime.now().isoformat()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (id, user_id, video_url, status, created_at, updated_at, config)
        VALUES (?, ?, ?, 'queued', ?, ?, ?)
    """, (job_id, user_id, video_url, now, now, json.dumps(config)))
    conn.commit()
    return job_id


def update_job(job_id: str, **kwargs):
    """Update job fields."""
    now = datetime.now().isoformat()
    fields = ["updated_at = ?"]
    values = [now]
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(value)
    values.append(job_id)

    query = f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?"
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, values)
    conn.commit()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job by ID."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return dict(row)


def get_jobs_by_user(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get jobs for user, optionally filtered by status."""
    conn = get_conn()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM jobs WHERE user_id = ? AND status = ? ORDER BY created_at DESC", (user_id, status))
    else:
        cursor.execute("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    return [dict(row) for row in cursor.fetchall()]


def get_all_jobs() -> List[Dict[str, Any]]:
    """Get all jobs regardless of user."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    return [dict(row) for row in cursor.fetchall()]


def save_clips(job_id: str, clips: List[Dict[str, Any]]):
    """Save analyzed clips to job."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET clips_json = ?, status = 'analyzing' WHERE id = ?", (json.dumps(clips), job_id))
    conn.commit()


def save_output_paths(job_id: str, paths: List[str]):
    """Save output file paths."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET output_paths = ?, status = 'completed' WHERE id = ?", (json.dumps(paths), job_id))
    conn.commit()


def get_or_create_config(user_id: str) -> Dict[str, Any]:
    """Get user config or create with defaults."""
    defaults = {
        "user_id": user_id,
        "watermark_enabled": 1,
        "watermark_size": 20.0,
        "watermark_x": 50.0,
        "watermark_y": 75.0,
        "target_clips": 10,
        "target_size_mb": 20,
        "subtitle_enabled": 0,
        "updated_at": datetime.now().isoformat()
    }
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_configs WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    cursor.execute("""
        INSERT INTO user_configs (user_id, watermark_enabled, watermark_size, watermark_x, watermark_y, 
                                  target_clips, target_size_mb, subtitle_enabled, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (defaults["user_id"], defaults["watermark_enabled"], defaults["watermark_size"],
          defaults["watermark_x"], defaults["watermark_y"], defaults["target_clips"],
          defaults["target_size_mb"], defaults["subtitle_enabled"], defaults["updated_at"]))
    conn.commit()
    return defaults


def update_config(user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Update user config."""
    now = datetime.now().isoformat()
    conn = get_conn()
    cursor = conn.cursor()
    
    updates = []
    values = [now, user_id]
    for key in ["watermark_enabled", "watermark_size", "watermark_x", "watermark_y", 
                "target_clips", "target_size_mb", "subtitle_enabled"]:
        if key in config:
            updates.append(f"{key} = ?")
            values.insert(-1, config[key])
    
    if updates:
        values.append(now)
        values.append(user_id)
        query = f"UPDATE user_configs SET updated_at = ?, {', '.join(updates)} WHERE user_id = ?"
        cursor.execute(query, values)
        conn.commit()
    
    return get_or_create_config(user_id)


init_db()
