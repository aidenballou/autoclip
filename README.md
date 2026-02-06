# AutoClip

A local desktop web application that automatically splits long video compilations into individual highlight clips using scene detection. Features a modern UI for previewing, trimming, combining, and exporting clips with multi-platform publishing support.

![AutoClip Demo](docs/demo.gif)

## Features

### Core Features
- **YouTube or Local Video Import**: Download from YouTube or use local video files
- **Automatic Scene Detection**: Uses FFmpeg to detect scene changes and create clips
- **Smart Clip Generation**: Enforces 5-60 second clip lengths, automatically merging or splitting as needed
- **Interactive Editing**: Trim clip boundaries, rename clips, combine multiple clips
- **Batch Export**: Export individual clips or batches to any folder
- **Real-time Progress**: Track download, analysis, and export progress

### New in Sprint 2
- **Niche & Account Management**: Organize accounts by content category (NBA, Fitness, etc.)
- **Multi-Platform Support**: Configure accounts for YouTube Shorts, TikTok, Instagram Reels, X/Twitter, Snapchat
- **Text Overlay**: Add customizable text overlays with position, color, and size options
- **Background Audio**: Mix background music with original audio, with volume controls
- **Vertical Preset**: Auto-format clips to 9:16 (1080x1920) for shorts/reels
- **Publish Pipeline**: Export clips to per-platform folders with metadata.json
- **Direct Upload**: YouTube Shorts upload with OAuth integration (other platforms export-only)

## Prerequisites

- macOS or Windows (native PowerShell or WSL2)
- Python 3.11+
- Node.js 18+
- FFmpeg
- yt-dlp (for YouTube downloads)

### Install Dependencies

Using Homebrew:

```bash
brew install python@3.11 node ffmpeg yt-dlp
```

Windows (PowerShell):

```powershell
# winget (Windows 10/11)
winget install Python.Python.3.11 OpenJS.NodeJS.LTS Gyan.FFmpeg yt-dlp.yt-dlp

# or Chocolatey
choco install python nodejs-lts ffmpeg yt-dlp -y

# or Scoop
scoop install python nodejs ffmpeg yt-dlp
```

Verify installation:

```bash
./scripts/ensure_deps.sh
```

```powershell
.\scripts\ensure_deps.ps1
```

## Quick Start

### 1. Clone and Setup

macOS / Linux:

```bash
cd AutoClip

# Install backend dependencies
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install
```

Windows (PowerShell):

```powershell
cd AutoClip

# Install backend dependencies
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Install frontend dependencies
cd ..\frontend
npm install
```

### 2. Run Development Server

macOS / Linux:

```bash
./scripts/dev.sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

This starts:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

### 3. Use the App

1. Open http://localhost:5173
2. Click "New Project"
3. Enter a YouTube URL or local file path
4. For YouTube: Click "Download Video"
5. Click "Analyze & Split" to generate clips
6. Browse clips, edit boundaries, select clips
7. Set output folder and export!

### 4. Multi-Platform Publishing (New!)

1. Go to **Niches** in the top navigation
2. Create a niche (e.g., "NBA Highlights")
3. Add accounts for each platform you want to publish to
4. Open a project and select a clip
5. Click "Publish..." in the clip editor
6. Select niche and accounts, configure settings
7. Click "Publish" to export per-platform files with metadata

## Platform Upload Notes

| Platform | Status | Notes |
|----------|--------|-------|
| YouTube Shorts | Direct Upload | Requires OAuth setup (see below) |
| TikTok | Export Only | Use metadata.json for manual upload |
| Instagram Reels | Export Only | Use metadata.json for manual upload |
| X / Twitter | Export Only | API requires partner approval |
| Snapchat | Export Only | Use metadata.json for manual upload |

Only YouTube Shorts supports the in-app **Connect** OAuth flow. Other platforms remain export-only.

### YouTube OAuth Setup (for Direct Upload)

To enable direct uploads to YouTube Shorts:

1. Create a Google Cloud project at console.cloud.google.com
2. Enable the YouTube Data API v3
3. Create OAuth 2.0 credentials
4. Set environment variables:

```bash
export YOUTUBE_CLIENT_ID="your-client-id"
export YOUTUBE_CLIENT_SECRET="your-client-secret"
```

5. In the app, go to Niches, add a YouTube Shorts account, and click "Connect"

## Production Mode

Build and serve from a single server:

```bash
# Build frontend
./scripts/build.sh

# Run backend with static serving
cd backend
export SERVE_FRONTEND=true
python -m uvicorn app.main:app --port 8000
```

Windows (PowerShell):

```powershell
# Build frontend
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1

# Run backend with static serving
cd backend
$env:SERVE_FRONTEND=$true
python -m uvicorn app.main:app --port 8000
```

Open http://localhost:8000

## Windows Notes

- For WSL2, run the app inside your Linux distro and use Linux paths (e.g. `/mnt/c/...` for Windows files).
- For local file imports, the path must be accessible to the backend OS (native Windows paths for native, WSL paths for WSL2).

## Windows Quick Test

1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1`
2. Open http://localhost:5173
3. Create a project from a local file

## Project Structure

```
AutoClip/
├── backend/
│   ├── app/
│   │   ├── api/           # REST API routes
│   │   ├── db/            # Database setup
│   │   ├── models/        # SQLAlchemy models (Project, Clip, Niche, Account)
│   │   ├── pipeline/      # Video processing logic
│   │   ├── services/      # Business logic (clip, niche, publish, upload)
│   │   ├── utils/         # FFmpeg/yt-dlp utilities
│   │   ├── workers/       # Background job system
│   │   ├── config.py      # Settings
│   │   └── main.py        # FastAPI app
│   ├── tests/             # Unit tests
│   └── data/              # Runtime data (auto-created)
├── frontend/
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # React components (ClipEditor, PublishModal, etc.)
│   │   ├── hooks/         # Custom hooks
│   │   ├── pages/         # Page components (Projects, Niches)
│   │   ├── types/         # TypeScript types
│   │   └── utils/         # Utilities
│   └── public/
└── scripts/
    ├── dev.sh             # Development launcher
    ├── dev.ps1            # Development launcher (Windows)
    ├── build.sh           # Production build
    ├── build.ps1          # Production build (Windows)
    ├── ensure_deps.sh     # Dependency checker
    └── ensure_deps.ps1    # Dependency checker (Windows)
```

## Configuration

Create `backend/.env` to customize settings:

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Video Processing
SCENE_THRESHOLD=0.3      # Lower = more sensitive (0.1-0.5)
MIN_CLIP_SECONDS=5       # Minimum clip duration
MAX_CLIP_SECONDS=60      # Maximum clip duration

# Export Quality
EXPORT_VIDEO_CRF=18      # Lower = better quality (18-28)
EXPORT_AUDIO_BITRATE=192k

# Vertical Preset (for shorts/reels)
VERTICAL_WIDTH=1080
VERTICAL_HEIGHT=1920
VERTICAL_FPS=30

# YouTube Upload (optional)
YOUTUBE_CLIENT_ID=your-client-id
YOUTUBE_CLIENT_SECRET=your-client-secret
```

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/youtube` | POST | Create project from YouTube URL |
| `/api/projects/local` | POST | Create project from local file |
| `/api/projects/{id}/download` | POST | Start YouTube download |
| `/api/projects/{id}/analyze` | POST | Start scene detection |
| `/api/projects/{id}/clips` | GET | List all clips |
| `/api/clips/{id}` | PATCH | Update clip (trim, rename) |
| `/api/projects/{id}/compound-clips` | POST | Create compound clip |
| `/api/projects/{id}/exports` | POST | Export clip(s) |
| `/api/projects/{id}/publish` | POST | Publish to multiple platforms |
| `/api/niches` | GET/POST | List/create niches |
| `/api/niches/{id}` | GET/PATCH/DELETE | Manage niche |
| `/api/accounts` | GET/POST | List/create accounts |
| `/api/accounts/{id}` | GET/PATCH/DELETE | Manage account |
| `/api/platforms` | GET | List supported platforms |
| `/api/jobs/{id}` | GET | Get job status |

Full API documentation: http://localhost:8000/docs

## Troubleshooting

### "ffmpeg not found"

```bash
brew install ffmpeg
```

### "yt-dlp not found"

```bash
brew install yt-dlp
```

### YouTube download fails

1. Update yt-dlp: `yt-dlp -U`
2. Check the URL is valid and public
3. Some videos may be geo-restricted

### Video won't play in browser

The browser may not support the video codec. The app will still export correctly to MP4.

### Export fails with permission error

Ensure the output folder exists and you have write permission:

```bash
mkdir -p ~/Desktop/clips
chmod 755 ~/Desktop/clips
```

### Scene detection produces too many/few clips

Adjust `SCENE_THRESHOLD` in `.env`:
- Lower (0.1-0.2): More sensitive, more clips
- Higher (0.4-0.5): Less sensitive, fewer clips

### Text overlay not appearing

- Ensure the font path in config is valid for your OS
- macOS: `/System/Library/Fonts/Helvetica.ttc`
- Linux: `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## Architecture Notes

### Background Jobs

Uses asyncio-based background tasks for long-running operations:
- Download jobs
- Analysis jobs (scene detection + thumbnail generation)
- Export jobs (single clip, compound clip, batch)
- Publish jobs (multi-platform export with overlays)
- Upload jobs (direct platform upload)

Progress is tracked in SQLite and polled by the frontend.

### Video Processing Pipeline

1. **Scene Detection**: FFmpeg `select='gt(scene,THRESH)'` filter
2. **Segment Creation**: Convert timestamps to segments
3. **Post-processing**: Split long segments (>60s), merge short ones (<5s)
4. **Thumbnail Generation**: Extract frame at clip midpoint
5. **Export**: Re-encode with H.264/AAC for compatibility
6. **Overlays** (optional): Text overlay, background audio mixing
7. **Vertical Format** (optional): Scale/pad to 9:16 aspect ratio

### Multi-Platform Publishing

1. Select clip and target accounts
2. Configure caption, hashtags, overlays
3. System exports to per-platform folders:
   ```
   output_folder/
   ├── youtube_shorts/
   │   ├── clip_name_youtube_shorts.mp4
   │   └── clip_name_metadata.json
   ├── tiktok/
   │   ├── clip_name_tiktok.mp4
   │   └── clip_name_metadata.json
   └── ...
   ```
4. metadata.json includes caption, hashtags, platform specs for manual upload

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request
