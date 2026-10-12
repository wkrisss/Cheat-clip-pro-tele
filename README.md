# Cheat Clip Pro Tele

AI-powered Telegram bot that turns YouTube videos into short vertical clips.

This repository is the maintained Telegram release by `wkrisss`. Backend and frontend are included in this same repository; no separate backend download is required.

## Ringkasan Bahasa Indonesia

Repo ini berisi backend dan frontend dalam satu paket. Tidak perlu download backend dari repo lain. Clone repo ini, jalankan `./install.sh`, lalu jalankan `./start-bot.sh`. Setup awal hanya meminta Telegram bot token. Gemini dan Supadata key dapat diatur lewat Telegram setelah bot aktif.

Mode penggunaan:

- **Auto clip:** kirim URL YouTube saja.
- **Custom clip:** kirim `URL | instruksi untuk AI`.
- **Atur video:** `/video 9:16 4 60 none`.
- **Layout facecam:** `/video 9:16 4 60 split_top_cam`.
- **Atur watermark:** `/watermark 50 75 20 80`.
- **Upload cookies:** kirim file `.txt`; bot menyimpannya sebagai `backend/cookies.txt`.
- **Upload watermark:** kirim `.png`, `.jpg`, `.jpeg`, atau `.webp`.
- **Web UI:** jalankan `npm run dev`, lalu buka `http://localhost:5173`. Web UI sudah termasuk repo ini.

Lihat bagian instalasi dan referensi command untuk detail lengkap.

English documentation follows below.


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

Do not create or commit `backend/.env` manually. Run the bot launcher once; setup asks only for the Telegram bot token and creates `backend/.env` with restrictive permissions:

```bash
./start-bot.sh
```

Set Gemini and Supadata keys later from a private Telegram chat with the admin commands below. `BACKEND_URL` defaults to `http://127.0.0.1:8000` and can be set in the local `.env` if needed.

Never commit `backend/.env`, API keys, Telegram tokens, cookies, databases, logs, or rendered videos.

### YouTube cookies from Telegram

Export your own YouTube cookies in Netscape format and rename the file exactly:

```text
cookies.txt
```

Send any `.txt` document directly to the bot as an admin. The bot automatically renames it to `backend/cookies.txt`. Send a `.png`, `.jpg`, `.jpeg`, or `.webp` document to update `backend/assets/watermark_logo.png`. Telegram messages are deleted after upload. New renders use the uploaded watermark. Never upload cookies in a group or commit the file.

### Telegram command reference

Send `/help` to see this inside Telegram. Admin commands:

```text
/video RATIO COUNT DURATION [LAYOUT]
/video 9:16 4 60 none
/video 9:16 4 60 split_top_cam
```

`none` keeps normal portrait layout. `split_top_cam` puts detected facecam on top and gameplay/reaction below. It works best when facecam is a distinct region in the source video.

Watermark:

```text
/watermark X Y SIZE OPACITY
/watermark 50 75 20 80
```

All values use percent `0-100`. `X` controls left-to-right position (`0` left, `50` center, `100` right). `Y` controls top-to-bottom position (`0` top, `50` center, `100` bottom). `SIZE` controls watermark size. `OPACITY` controls visibility (`100` fully visible, `0` invisible).

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

Web UI sudah termasuk dalam repo ini. Jalankan dari root project:

```bash
npm run dev
```

Buka `http://localhost:5173`.

Referensi web UI/original project:
https://github.com/galihjuansaputra/cheat-clip-pro

Repo asli hanya untuk referensi sumber. Untuk instalasi versi Telegram ini, clone repo `wkrisss` di atas.

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

## Attribution

This project is based on the original Cheat Clip Pro codebase by `galihjuansaputra`:

- Original repository: https://github.com/galihjuansaputra/cheat-clip-pro
- Telegram release and deployment changes: `wkrisss`

Changes in this repository include Telegram-first setup, Telegram API-key configuration, cookie and watermark uploads, Telegram video settings, split facecam layout support, queue/worker integration, and installation documentation. Original notices and license terms remain in `LICENSE`.

## License

MIT. See `LICENSE`.

Third-party services and downloaded content remain subject to their own terms. Users are responsible for copyright, platform rules, campaign briefs, and API usage.
