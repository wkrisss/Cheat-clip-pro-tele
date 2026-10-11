#!/usr/bin/env python3
"""Telegram bot for Cheat Clip Pro - controls video clipping via backend API."""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))
from backend.config import logger
from backend.services.job_queue import get_job, get_user_config

# Environment config
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set")
    sys.exit(1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    keyboard = [
        [KeyboardButton("/clip"), KeyboardButton("/settings")],
        [KeyboardButton("/status"), KeyboardButton("/cancel")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Hello! I'm Cheat Clip Pro Bot.\n"
        "Use the buttons below or commands:\n"
        "/clip <url> — Clip a video\n"
        "/settings — View/modify settings\n"
        "/status <job_id> — Check job status\n"
        "/cancel <job_id> — Cancel a job",
        reply_markup=reply_markup,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "Commands:\n"
        "/clip <video_url> — Start clipping a YouTube/Google Drive video\n"
        "/settings — Show current clipping settings\n"
        "/status <job_id> — Check clipping job status\n"
        "/cancel <job_id> — Cancel a pending/running job\n"
        "/help — Show this help"
    )


async def clip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clip command."""
    user_id = str(update.effective_user.id)
    message = update.message.text
    
    # Extract URL from message
    url = message.replace("/clip", "").strip()
    if not url:
        await update.message.reply_text(
            "Usage: /clip <video_url>\n"
            "Example: /clip https://www.youtube.com/watch?v=abc123"
        )
        return
    
    await update.message.reply_text("Queueing job...")

    # Submit job to backend
    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BACKEND_URL}/api/jobs/submit",
                params={"video_url": url, "user_id": user_id},
                timeout=10,
            ) as resp:
                result = await resp.json()
                if resp.status == 200:
                    await update.message.reply_text(
                        f"✅ Job queued!\n"
                        f"Job ID: `{result['job_id']}`\n"
                        f"Status: `{result['status']}`\n\n"
                        f"Use `/status {result['job_id']}` to check progress.",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        f"❌ Failed: {result.get('detail', str(result))}"
                    )
        except Exception as e:
            logger.error(f"Failed to submit job: {e}")
            await update.message.reply_text(f"❌ Backend error: {str(e)}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user_id = str(update.effective_user.id)
    message = update.message.text
    
    job_id = message.replace("/status", "").strip()
    if not job_id:
        await update.message.reply_text("Usage: /status <job_id>")
        return

    await update.message.reply_text(f"Fetching status for `{job_id}`...", parse_mode="Markdown")

    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{BACKEND_URL}/api/jobs/{job_id}",
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    clips = result.get("clips", [])
                    clips_text = ""
                    if clips:
                        clip_count = min(len(clips), 5)
                        clips_text = f"\n\nClips ({len(clips)} total):\n"
                        for i, c in enumerate(clips[:clip_count]):
                            clips_text += f"  {i+1}. [{c.get('start_time', 0):.1f}s - {c.get('end_time', 0):.1f}s] {c.get('title', 'Untitled')}\n"
                        if len(clips) > 5:
                            clips_text += "  ... and more"
                    
                    outputs = result.get("outputs", [])
                    outputs_text = ""
                    if outputs:
                        outputs_text = "\n\nOutput files:\n" + "\n".join(
                            f"  - {o}" for o in outputs[:5]
                        )
                        if len(outputs) > 5:
                            outputs_text += "\n  ... and more"
                    
                    await update.message.reply_text(
                        f"Job Status: `{result['status']}`\n"
                        f"Progress: `{result['progress']}%`\n"
                        f"Video: `{result['video_url']}`\n"
                        f"Created: `{result['created_at']}`\n"
                        f"Updated: `{result['updated_at']}`"
                        f"{clips_text}"
                        f"{outputs_text}"
                        f"\n\nError: `{result.get('error', 'N/A')}`"
                        if result.get("error")
                        else "",
                        parse_mode="Markdown",
                    )
                elif resp.status == 404:
                    await update.message.reply_text("Job not found.")
                else:
                    await update.message.reply_text(f"Failed to fetch status.")
        except Exception as e:
            logger.error(f"Failed to fetch job: {e}")
            await update.message.reply_text(f"❌ Backend error: {str(e)}")


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command."""
    user_id = str(update.effective_user.id)
    
    await update.message.reply_text("Fetching settings...")

    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{BACKEND_URL}/api/jobs/settings/{user_id}",
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    await update.message.reply_text(
                        f"Current settings:\n"
                        f"```json\n{json.dumps(result, indent=2)}\n```",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        "No custom settings found. Using defaults:\n"
                        "- Subtitles: OFF\n"
                        "- Watermark: ON (20%, pos 50/70)\n"
                        "- Target clips: 10"
                    )
        except Exception as e:
            logger.error(f"Failed to fetch settings: {e}")
            await update.message.reply_text(f"❌ Backend error: {str(e)}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    user_id = str(update.effective_user.id)
    message = update.message.text
    
    job_id = message.replace("/cancel", "").strip()
    if not job_id:
        await update.message.reply_text("Usage: /cancel <job_id>")
        return

    await update.message.reply_text(f"Cancelling job `{job_id}`...", parse_mode="Markdown")

    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BACKEND_URL}/api/jobs/{job_id}/cancel",
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    await update.message.reply_text(f"✅ {result.get('message', 'Job cancelled')}")
                elif resp.status == 404:
                    await update.message.reply_text("Job not found.")
                else:
                    await update.message.reply_text(f"❌ Failed to cancel.")
        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            await update.message.reply_text(f"❌ Backend error: {str(e)}")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo any other message."""
    await update.message.reply_text("Use /help to see available commands.")


def main():
    """Start the Telegram bot."""
    logger.info("Starting Telegram bot...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("clip", clip))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()