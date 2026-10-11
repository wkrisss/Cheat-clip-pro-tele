-- Jobs table for persistent background processing
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued', -- queued, analyzing, downloading, clipping, completed, failed, cancelled
    job_type TEXT NOT NULL, -- analyze, render_batch, render_single, download_raw
    video_url TEXT,
    video_id TEXT,
    config JSON,
    result JSON,
    progress INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT,
    user_id TEXT, -- for Telegram bot multi-user support
    message_id TEXT -- Telegram message ID for progress updates
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
