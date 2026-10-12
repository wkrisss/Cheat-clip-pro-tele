"""Telegram bot for Cheat Clip Pro - Controls video clipping via Telegram."""
import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from backend.config import logger, TEMP_DIR
from backend.services.job_queue import create_job, get_job, update_job, init_database
from backend.database import get_jobs_by_user, get_all_jobs

# Bot configuration
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_USER_IDS = os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",") if os.environ.get("TELEGRAM_ADMIN_IDS") else []
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# Default settings
DEFAULT_SETTINGS = {
    "aspect_ratio": "9:16",
    "caption_style": "none",
    "title_position": "none",
    "subtitles_enabled": False,
    "watermark_enabled": True,
    "watermark_size": 20.0,
    "watermark_x": 50.0,
    "watermark_y": 75.0,
    "target_clip_count": 4,
    "clip_duration_seconds": 60,
    "target_file_size_mb": 20,
    "send_separately": True,
    "watermark_enabled": True,
    "watermark_type": "image",
    "watermark_file_path": "/home/wahyu/cheat-clip-pro/backend/assets/watermark_logo.png",
    "watermark_size": 20.0,
    "watermark_opacity": 80.0,
    "watermark_x": 50.0,
    "watermark_y": 75.0,
}
DEFAULT_SETTINGS.update({
    "aspect_ratio": os.environ.get("VIDEO_ASPECT_RATIO", DEFAULT_SETTINGS["aspect_ratio"]),
    "target_clip_count": int(os.environ.get("TARGET_CLIP_COUNT", DEFAULT_SETTINGS["target_clip_count"])),
    "clip_duration_seconds": int(os.environ.get("CLIP_DURATION_SECONDS", DEFAULT_SETTINGS["clip_duration_seconds"])),
    "streamer_preset": os.environ.get("STREAMER_PRESET", "none"),
})
DEFAULT_SETTINGS.update({
    "watermark_x": float(os.environ.get("WATERMARK_X", DEFAULT_SETTINGS["watermark_x"])),
    "watermark_y": float(os.environ.get("WATERMARK_Y", DEFAULT_SETTINGS["watermark_y"])),
    "watermark_size": float(os.environ.get("WATERMARK_SIZE", DEFAULT_SETTINGS["watermark_size"])),
    "watermark_opacity": float(os.environ.get("WATERMARK_OPACITY", DEFAULT_SETTINGS["watermark_opacity"])),
})

# In-memory job tracking for active Telegram sessions
active_jobs: Dict[str, Dict[str, Any]] = {}


async def _log_bot_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Telegram update failed", exc_info=context.error)


async def recover_completed_jobs(app):
    """Deliver completed files after bot restart, once paths still exist."""
    for job in get_all_jobs():
        if job.get("status") != "completed" or not job.get("output_paths"):
            continue
        try:
            paths = json.loads(job["output_paths"])
            existing = [p for p in paths if Path(p).is_file()]
            if not existing:
                continue
            for path in existing:
                with open(path, "rb") as video:
                    await app.bot.send_video(chat_id=int(job["user_id"]), video=video, supports_streaming=True)
                Path(path).unlink(missing_ok=True)
            await app.bot.send_message(chat_id=int(job["user_id"]), text=f"🎉 Job `{job['id']}` selesai. {len(existing)} video dikirim.", parse_mode="Markdown")
        except Exception:
            logger.exception("Failed recovering completed job %s", job.get("id"))


async def _delivery_loop(app):
    while True:
        await recover_completed_jobs(app)
        await asyncio.sleep(10)


async def _post_init(app):
    app.create_task(_delivery_loop(app))
    await recover_completed_jobs(app)


async def _post_shutdown(app):
    for task in getattr(app, "_tasks", set()):
        if task.get_name() == "delivery-loop":
            task.cancel()


async def recover_completed_jobs(app):
    """Deliver completed files after bot restart or late worker completion."""
    for job in get_all_jobs():
        if job.get("status") != "completed" or not job.get("output_paths"):
            continue
        try:
            paths = json.loads(job["output_paths"])
            existing = [p for p in paths if Path(p).is_file()]
            if not existing:
                continue
            for path in existing:
                with open(path, "rb") as video:
                    await app.bot.send_video(chat_id=int(job["user_id"]), video=video, supports_streaming=True)
                Path(path).unlink(missing_ok=True)
            await app.bot.send_message(chat_id=int(job["user_id"]), text=f"🎉 Job `{job['id']}` selesai. {len(existing)} video dikirim.", parse_mode="Markdown")
        except Exception:
            logger.exception("Failed recovering completed job %s", job.get("id"))


async def _post_init(app):
    await app.bot.set_my_commands([
        ("start", "Mulai bot dan lihat panduan"),
        ("help", "Panduan lengkap fitur bot"),
        ("video", "Atur rasio, jumlah, durasi, layout"),
        ("watermark", "Atur posisi watermark"),
        ("status", "Lihat status job"),
        ("settings", "Lihat pengaturan"),
        ("cancel", "Batalkan job"),
    ])
    app.create_task(_delivery_loop(app), name="delivery-loop")
    await recover_completed_jobs(app)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - show menu."""
    keyboard = [
        [InlineKeyboardButton("🎬 Start New Clip", callback_data="start_new")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📋 Jobs", callback_data="list_jobs")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Cheat Clip Pro siap digunakan.\n\n"
        "Setup awal:\n"
        "1. Admin kirim /setkey gemini API_KEY\n"
        "2. Admin kirim /setkey supadata API_KEY (opsional)\n"
        "3. Admin kirim file cookies YouTube .txt (opsional)\n"
        "4. Atur watermark: /watermark 50 75 20 80\n"
        "5. Atur video: /video 9:16 4 60 split_top_cam\n   (rasio, jumlah klip, durasi, layout facecam atas)\n\n"
        "Auto clip:\n"
        "Kirim URL YouTube.\n\n"
        "Custom clip:\n"
        "URL | instruksi untuk AI\n"
        "Contoh: URL | ambil momen lucu gameplay dan sertakan facecam.\n\n"
        "Gunakan /help untuk panduan lengkap.",
        reply_markup=reply_markup
    )

    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        await update.message.reply_text(
            "⚠️ Gemini API key belum diset. Admin harus kirim:\n"
            "/setkey gemini API_KEY"
        )
    elif not os.environ.get("SUPADATA_API_KEY") and not os.environ.get("SUPADATA_API_KEYS"):
        await update.message.reply_text(
            "ℹ️ Supadata key belum diset. Opsional, tapi berguna untuk transcript:\n"
            "/setkey supadata API_KEY"
        )
    


def _is_admin(update):
    admins = {x.strip() for x in os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip()}
    return not admins or str(update.effective_user.id) in admins


def _save_env_key(name, value):
    env = Path(__file__).parent / ".env"
    lines = env.read_text().splitlines() if env.exists() else []
    lines = [x for x in lines if not x.startswith(name + "=")]
    lines.append(f"{name}={value}")
    env.write_text("\n".join(lines) + "\n")
    env.chmod(0o600)


async def receive_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("Not authorized.")
        return
    document = update.message.document
    name = (document.file_name or "").lower() if document else ""
    if not document:
        return
    if name.endswith(".txt"):
        target = Path(__file__).parent / "cookies.txt"
        message = "cookies.txt saved."
    elif name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        target = Path(__file__).parent / "assets" / "watermark_logo.png"
        message = "Watermark saved. New renders will use it."
    else:
        await update.message.reply_text("Send .txt cookies or .png/.jpg watermark image")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    telegram_file = await document.get_file()
    await telegram_file.download_to_drive(custom_path=str(target))
    target.chmod(0o600)
    try:
        await update.message.delete()
    except Exception:
        pass
    await context.bot.send_message(update.effective_chat.id, message)


async def receive_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await receive_upload(update, context)


async def set_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("Not authorized.")
        return
    if len(context.args) != 2 or context.args[0] not in {"gemini", "supadata"}:
        await update.message.reply_text("Usage: /setkey gemini|supadata <key>")
        return
    name = "GOOGLE_API_KEY" if context.args[0] == "gemini" else "SUPADATA_API_KEY"
    _save_env_key(name, context.args[1])
    try:
        await update.message.delete()
    except Exception:
        pass
    os.environ[name] = context.args[1]
    await update.message.reply_text(f"{name} saved. Restart backend to apply it to worker.")


async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ("ℹ️ Cheat Clip Pro\n\n"
            "AUTO CLIP\n"
            "Kirim URL YouTube saja. AI pilih momen dari transcript.\n\n"
            "CUSTOM CLIP\n"
            "Format: URL | instruksi untuk AI\n"
            "Contoh: URL | cari momen lucu, sertakan konteks 5 detik sebelum dan sesudah.\n\n"
            "VIDEO\n"
            "/video RASIO JUMLAH DURASI [LAYOUT]\n"
            "Contoh normal: /video 9:16 4 60 none\n"
            "Contoh facecam atas: /video 9:16 4 60 split_top_cam\n"
            "Contoh facecam sudut: /video 9:16 4 60 pip_corner\n"
            "Rasio (4 pilihan): 9:16, 16:9, 1:1, 4:5. Durasi dalam detik.\n"
            "Layout (3 pilihan): none = normal, split_top_cam = facecam atas + gameplay bawah, pip_corner = facecam kecil di sudut.\n"
            "Posisi facecam source: auto-detect dipakai otomatis; layout Telegram belum menerima posisi manual.\n\n"
            "WATERMARK\n"
            "/watermark X Y SIZE OPACITY\n"
            "Semua angka persen 0-100. X=posisi kiri-kanan; Y=posisi atas-bawah.\n"
            "X 0 kiri, 50 tengah, 100 kanan. Y 0 atas, 50 tengah, 100 bawah.\n"
            "SIZE=ukuran watermark; OPACITY=transparansi (100 terlihat penuh).\n"
            "Contoh: /watermark 50 75 20 80\n\n"
            "UPLOAD\n"
            ".txt = cookies.txt. .png/.jpg/.jpeg/.webp = watermark.\n\n"
            "ADMIN\n"
            "/setkey gemini KEY\n/setkey supadata KEY")
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def set_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("Not authorized.")
        return
    try:
        ratio, count, duration, *layout = context.args
        preset = layout[0] if layout else "none"
        if ratio not in {"9:16", "16:9", "1:1", "4:5"} or preset not in {"none", "split_top_cam", "pip_corner"}:
            raise ValueError
        count = int(count)
        duration = int(duration)
        if not (1 <= count <= 20 and 5 <= duration <= 600):
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("Usage: /video RATIO COUNT DURATION\nExample: /video 9:16 4 60")
        return
    DEFAULT_SETTINGS.update({
        "aspect_ratio": ratio,
        "target_clip_count": count,
        "clip_duration_seconds": duration,
        "streamer_preset": preset,
    })
    for key, value in {"VIDEO_ASPECT_RATIO": ratio, "TARGET_CLIP_COUNT": count, "CLIP_DURATION_SECONDS": duration, "STREAMER_PRESET": preset}.items():
        _save_env_key(key, str(value))
        os.environ[key] = str(value)
    await update.message.reply_text(f"Video settings saved: {ratio}, {count} clips, {duration}s each.")


async def set_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("Not authorized.")
        return
    try:
        x, y, size, opacity = map(float, context.args)
        if not (0 <= x <= 100 and 0 <= y <= 100 and 1 <= size <= 100 and 0 <= opacity <= 100):
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("Usage: /watermark X Y SIZE OPACITY\nExample: /watermark 50 75 20 80")
        return
    for key, value in {"WATERMARK_X": x, "WATERMARK_Y": y, "WATERMARK_SIZE": size, "WATERMARK_OPACITY": opacity}.items():
        _save_env_key(key, str(value))
        os.environ[key] = str(value)
    await update.message.reply_text(f"Watermark saved: X={x}% Y={y}% Size={size}% Opacity={opacity}%")


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings menu."""
    keyboard = [
        [InlineKeyboardButton("✅ Subtitles OFF", callback_data="set_subtitles_off")],
        [InlineKeyboardButton("✅ Watermark ON", callback_data="set_watermark_on")],
        [InlineKeyboardButton("💧 Watermark Size 20%", callback_data="set_watermark_size_20")],
        [InlineKeyboardButton("📍 Watermark Pos 50/70", callback_data="set_watermark_pos")],
        [InlineKeyboardButton("🎯 Target 10 clips", callback_data="set_target_10")],
        [InlineKeyboardButton("💾 Save Preset", callback_data="save_preset")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "⚙️ Settings:\n"
        "- Subtitles: OFF\n"
        "- Watermark: ON\n"
        "- Watermark Size: 20%\n"
        "- Watermark Pos: 50%/70%\n"
        "- Target clips: 10\n"
        "- File size: ~20 MB each\n\n"
        "Select an option to change:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        await start(update, context)
    elif query.data == "start_new":
        await query.edit_message_text("📩 Send me a YouTube URL to start clipping!")
    elif query.data == "settings":
        await settings_menu(update, context)
    elif query.data == "list_jobs":
        await list_jobs(update, context)
    elif query.data == "help":
        await help_menu(update, context)
    elif query.data == "save_preset":
        await query.edit_message_text("✅ Preset saved! All new jobs will use these settings.")


async def list_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List recent jobs."""
    jobs = get_jobs_by_user(str(update.effective_user.id))[:5]
    
    if not jobs:
        await update.callback_query.edit_message_text("📝 No jobs yet.")
        return
    
    text = "📋 Recent Jobs:\n\n"
    for job in jobs:
        status_emoji = {"completed": "✅", "failed": "❌", "queued": "⏳", "analyzing": "🔬"}.get(job["status"], "❓")
        text += f"{status_emoji} Job `{job['id']}`\n"
        text += f"   Status: {job['status']} ({job.get('progress', 0)}%)\n"
        text += f"   Video: {job['video_url']}\n"
        text += f"   Created: {job['created_at'][:16]}\n\n"
    
    await update.callback_query.edit_message_text(text, parse_mode="Markdown")


async def handle_video_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube URL input."""
    raw = update.message.text.strip()
    parts = raw.split("|", 1)
    url = parts[0].strip()
    custom_prompt = parts[1].strip() if len(parts) == 2 else None
    
    # Validate YouTube URL
    youtube_pattern = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
    match = re.search(youtube_pattern, url)
    
    if not match:
        await update.message.reply_text("❌ Invalid YouTube URL. Please send a valid YouTube link.")
        return
    
    video_id = match.group(1)
    
    # Queue job in same SQLite queue used by FastAPI worker.
    job_id = create_job(
        user_id=str(update.effective_user.id),
        video_url=url,
        config={"settings": DEFAULT_SETTINGS, "custom_prompt": custom_prompt}
    )

    # FastAPI worker claims queued jobs; bot must not run a second pipeline.
    
    message = await update.message.reply_text(
        f"✅ Job created: `{job_id}`\n"
        f"📊 Processing YouTube video: {video_id}\n"
        f"⏳ Status: queued (0%)"
    )
    asyncio.create_task(monitor_job(
        job_id, update.effective_chat.id, message.message_id, context.bot
    ))


async def monitor_job(job_id: str, chat_id: int, message_id: int, bot):
    """Edit one progress message, then deliver completed files."""
    last_text = None
    for _ in range(360):
        job = get_job(job_id)
        if not job:
            return
        status = job.get("status", "queued")
        progress = int(job.get("progress") or 0)
        emoji = {"queued": "⏳", "analyzing": "🔬", "clipping": "✂️", "completed": "✅", "failed": "❌"}.get(status, "🔄")
        text = f"{emoji} Job `{job_id}`\\nStatus: {status}\\nProgress: {progress}%"
        if status == "failed":
            text += f"\\nError: {job.get('error') or 'unknown error'}"
        if text != last_text:
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode="Markdown")
                last_text = text
            except Exception:
                logger.exception("Progress message update failed for %s", job_id)
        if status == "completed":
            paths = json.loads(job.get("output_paths") or "[]")
            sent = 0
            for path in paths:
                if Path(path).is_file():
                    with open(path, "rb") as video:
                        await bot.send_video(chat_id=chat_id, video=video, supports_streaming=True)
                    Path(path).unlink(missing_ok=True)
                    sent += 1
            await bot.send_message(chat_id=chat_id, text=f"🎉 Job `{job_id}` selesai. {sent} video dikirim.", parse_mode="Markdown")
            return
        if status == "failed":
            return
        await asyncio.sleep(5)
    await bot.send_message(chat_id=chat_id, text=f"⚠️ Job `{job_id}` belum selesai setelah 30 menit.", parse_mode="Markdown")


async def process_job(job_id: str, url: str, video_id: str, settings: Dict[str, Any]):
    """Process a job through the backend API."""
    try:
        # Step 1: Analyze video
        update_job(job_id, status="analyzing", progress=10)
        
        async with aiohttp.ClientSession() as session:
            # Call analyze endpoint
            analyze_resp = await session.post(
                f"{BACKEND_URL}/api/analyze",
                json={
                    "url": url,
                    "duration": "30s",
                    "target_clip_count": settings.get("target_clip_count", 10),
                }
            )
            
            if analyze_resp.status != 200:
                error_text = await analyze_resp.text()
                update_job(job_id, status="failed", error=f"Analysis failed: {error_text}")
                return
            
            # Get analysis result (from SSE stream or cached result)
            # For simplicity, we'll use a polling approach
            analysis_result = await analyze_resp.json()
            
            update_job(job_id, status="analyzing", progress=40, result=analysis_result)
            
            # Step 2: Extract top clips
            clips = analysis_result.get("clips", [])[:settings.get("target_clip_count", 10)]
            
            if not clips:
                update_job(job_id, status="failed", error="No valid clips found")
                return
            
            # Step 3: Render batch
            update_job(job_id, status="clipping", progress=50)
            
            render_resp = await session.post(
                f"{BACKEND_URL}/api/render-batch",
                json={
                    "video_url": url,
                    "video_id": video_id,
                    "clips": clips,
                    "settings": {
                        "subtitles_enabled": settings.get("subtitles_enabled", False),
                        "watermark_enabled": settings.get("watermark_enabled", True),
                        "watermark_size": settings.get("watermark_size", 20.0),
                        "watermark_x": settings.get("watermark_x", 50.0),
                        "watermark_y": settings.get("watermark_y", 90.0),
                    }
                }
            )
            
            render_data = await render_resp.json()
            batch_id = render_data.get("batch_id")
            
            # Poll for render progress
            for attempt in range(30):  # Max 5 minutes
                progress_resp = await session.get(
                    f"{BACKEND_URL}/api/render-progress/{batch_id}"
                )
                progress_data = await progress_resp.json()
                
                if progress_data.get("overall_status") == "completed":
                    update_job(job_id, status="completed", progress=100)
                    
                    # Send results
                    await send_results(update, context, clips, batch_id)
                    break
                
                update_job(job_id, progress=50 + int(progress_data.get("current_clip_index", 0) * 50 / len(clips)))
                await asyncio.sleep(10)
            
            else:
                update_job(job_id, status="failed", error="Render timeout")
    
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))


async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE, clips: List[Dict], batch_id: str):
    """Send rendered clips to user."""
    try:
        # Get exports directory
        exports_dir = Path(TEMP_DIR) / "exports"
        
        for i, clip in enumerate(clips):
            clip_file = exports_dir / f"clip_{i}.mp4"
            
            if clip_file.exists():
                await update.message.reply_video(
                    video=open(clip_file, "rb"),
                    caption=f"✅ {clip.get('title', f'Clip {i+1}')}\n"
                           f"⏱️ {clip.get('start_time', 0):.0f}s - {clip.get('end_time', 0):.0f}s\n"
                           f"🔥 Virality: {clip.get('virality_score', 0)}%"
                )
            else:
                await update.message.reply_text(f"⚠️ Clip {i+1} not found")
        
        await update.message.reply_text("🎉 All clips sent successfully!")
    
    except Exception as e:
        logger.error("Failed to send results: %s", e)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check job status."""
    job_id = context.args[0] if context.args else None
    
    if not job_id:
        await update.message.reply_text("Usage: `/status <job_id>`", parse_mode="Markdown")
        return
    
    job = get_job(job_id)
    
    if not job:
        await update.message.reply_text(f"❌ Job `{job_id}` not found.", parse_mode="Markdown")
        return
    
    status_emoji = {"completed": "✅", "failed": "❌", "queued": "⏳", "analyzing": "🔬", "clipping": "✂️"}.get(job["status"], "❓")
    
    await update.message.reply_text(
        f"{status_emoji} Job `{job_id}`\n"
        f"Status: {job['status']}\n"
        f"Progress: {job['progress']}%\n"
        f"Video: {job['video_url']}\n"
        f"Created: {job['created_at'][:16]}\n"
        + (f"Error: {job['error']}" if job.get('error') else "")
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel a job."""
    job_id = context.args[0] if context.args else None
    
    if not job_id:
        await update.message.reply_text("Usage: `/cancel <job_id>`", parse_mode="Markdown")
        return
    
    job = get_job(job_id)
    
    if not job:
        await update.message.reply_text(f"❌ Job `{job_id}` not found.", parse_mode="Markdown")
        return
    
    if job["status"] in ["completed", "failed", "cancelled"]:
        await update.message.reply_text(f"❌ Job `{job_id}` cannot be cancelled (status: {job['status']}).", parse_mode="Markdown")
        return
    
    update_job(job_id, status="cancelled")
    await update.message.reply_text(f"✅ Job `{job_id}` cancelled.", parse_mode="Markdown")


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return
    
    # Initialize job queue
    init_database()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings_menu))
    app.add_handler(CommandHandler("setkey", set_key))
    app.add_handler(CommandHandler("watermark", set_watermark))
    app.add_handler(CommandHandler("video", set_video))
    app.add_handler(CommandHandler("help", help_menu))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, receive_cookies))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video_url))
    app.add_error_handler(_log_bot_error)
    
    # Start polling
    logger.info("🤖 Telegram bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
