# Cheat Clip Pro Tele

AI-powered Telegram bot that turns YouTube videos into short vertical clips.

Features:

- Automatic AI clip selection from transcript/script
- Custom AI instructions per link
- Four clip candidates by default
- 9:16 output at 1080x1920
- Full 16:9 source preserved with black padding; no crop or zoom
- Watermark support
- Telegram progress updates and automatic delivery
- SQLite queue with background worker
- FFmpeg rendering

## Custom clip instructions

Send one message to the Telegram bot:

```text
https://www.youtube.com/watch?v=VIDEO_ID | find the funniest gameplay moment and include the facecam
```

Without `| instruction`, the bot uses automatic viral-moment selection.

The instruction guides AI. AI still reads transcript/context and returns timestamps.

## Requirements

- Linux, macOS, or Windows
- Python 3.11+
- Node.js 18+ (web UI)
- FFmpeg
- Git
- Telegram bot token
- Gemini API key
- Optional Supadata API key for transcript fallback
- Optional YouTube `cookies.txt` for restricted videos

## Installation

### 1. Clone

```bash
git clone https://github.com/wkrisss/Cheat-clip-pro-tele.git
cd Cheat-clip-pro-tele
```

### 2. Install FFmpeg

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv nodejs npm
```

macOS:

```bash
brew install ffmpeg python node
```

Windows: install FFmpeg and add it to `PATH`.

### 3. Install backend

```bash
python3 -m venv backend_venv
source backend_venv/bin/activate
pip install -r backend/requirements.txt
```

Windows PowerShell:

```powershell
py -m venv backend_venv
.\backend_venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### 4. Install web UI

```bash
npm install
```

### 5. Configure environment

```bash
cp backend/.env.template backend/.env
```

Set values in `backend/.env`:

```env
GOOGLE_API_KEY=your_gemini_key
# or GEMINI_API_KEY=your_gemini_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
BACKEND_URL=http://127.0.0.1:8000

# Optional transcript provider
SUPADATA_API_KEY=your_supadata_key
```

Never commit `backend/.env`, API keys, Telegram tokens, cookies, databases, logs, or rendered videos.

### YouTube cookies from Telegram

Export your own YouTube cookies in Netscape format and rename the file exactly:

```text
cookies.txt
```

Send any `.txt` document directly to the bot as an admin. The bot automatically renames it to `backend/cookies.txt`. Send a `.png`, `.jpg`, `.jpeg`, or `.webp` document to update `backend/assets/watermark_logo.png`. Telegram messages are deleted after upload. New renders use the uploaded watermark. Never upload cookies in a group or commit the file.

### Video settings from Telegram

Admin can change output ratio, clip count, and duration without editing server files:

```text
/video 9:16 4 60
```

Format: `/video RATIO COUNT DURATION_SECONDS`.
Supported ratios: `9:16`, `16:9`, `1:1`, `4:5`. Count supports `1-20`; duration supports `5-600` seconds. Settings persist in `backend/.env` and apply to new jobs.

The cookies belong to your own account. Use them only where you have permission.

```text
/status
```

The bot does not reveal cookie contents.


### 6. First-run Telegram setup

Run the bot launcher once. It asks only for the Telegram token, then saves it to local `backend/.env`. Gemini and Supadata keys are added later from Telegram:

```bash
./start-bot.sh
```

After setup, admins can update keys from Telegram:

```text
/setkey gemini YOUR_GEMINI_KEY
/setkey supadata YOUR_SUPADATA_KEY
```

Set `TELEGRAM_ADMIN_IDS` in `backend/.env` to restrict this command. The bot deletes key messages after receiving them. Never share keys in groups.

### 7. Start backend

From project root:

```bash
backend_venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend
```

### 7. Start Telegram bot

In another terminal, from project root:

```bash
./start-bot.sh
```

The bot must run as `python -m backend.bot` from project root. Run only one bot instance; multiple polling processes cause Telegram `Conflict` errors.

### 8. Start web UI (optional)

```bash
npm run dev
```

Open `http://localhost:5173`.

## Output defaults

- 4 clips
- 60 seconds target duration
- 9:16 portrait
- 1080x1920
- Full 16:9 source centered with black padding
- No automatic crop or zoom
- Watermark X: 50%
- Watermark Y: 75%
- Watermark size: 20%
- Watermark opacity: 80%
- Captions and titles disabled in Telegram pipeline

## Project layout

```text
backend/                 FastAPI API, Telegram bot, worker, renderer
backend/routers/         API routes and AI analysis
backend/services/        queue, transcript, rendering, worker services
backend/video_engine.py  FFmpeg rendering pipeline
backend/data/            local SQLite data; ignored by Git
backend/assets/          watermark assets
src/                     web UI
start-bot.sh             Telegram bot launcher
backend/.env.template    environment template
```

## Troubleshooting

Check backend:

```bash
curl http://127.0.0.1:8000/health
```

Check worker logs:

```bash
tail -f /tmp/uvicorn.log
```

Check Telegram bot logs:

```bash
tail -f /tmp/telegram-bot.log
```

If a job stays queued, verify one backend process is alive and one worker is running. If Telegram reports `Conflict`, stop duplicate bot processes and start one bot only.

If YouTube blocks downloads, provide a valid `cookies.txt` locally. Do not commit it.

## Development checks

```bash
backend_venv/bin/python -m py_compile backend/bot.py backend/services/cheat_clip_worker.py backend/video_engine.py
npm run build
```

## License

MIT. See `LICENSE`.

Third-party services and downloaded content remain subject to their own terms. Users are responsible for copyright, platform rules, campaign briefs, and API usage.
# Cheat-clip-pro-tele
