# AutoClip

A local macOS web application that automatically splits long video compilations into individual highlight clips using scene detection. Features a modern UI for previewing, trimming, combining, and exporting clips.

![AutoClip Demo](docs/demo.gif)

## Features

- **YouTube or Local Video Import**: Download from YouTube or use local video files
- **Automatic Scene Detection**: Uses FFmpeg to detect scene changes and create clips
- **Smart Clip Generation**: Enforces 5-60 second clip lengths, automatically merging or splitting as needed
- **Interactive Editing**: Trim clip boundaries, rename clips, combine multiple clips
- **Batch Export**: Export individual clips or batches to any folder
- **Real-time Progress**: Track download, analysis, and export progress

## Prerequisites

- macOS (tested on Apple Silicon and Intel)
- Python 3.11+
- Node.js 18+
- FFmpeg
- yt-dlp (for YouTube downloads)

### Install Dependencies

Using Homebrew:

```bash
brew install python@3.11 node ffmpeg yt-dlp
```

Verify installation:

```bash
./scripts/ensure_deps.sh
```

## Quick Start

### 1. Clone and Setup

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

### 2. Run Development Server

```bash
./scripts/dev.sh
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

Open http://localhost:8000

## Project Structure

```
AutoClip/
├── backend/
│   ├── app/
│   │   ├── api/           # REST API routes
│   │   ├── db/            # Database setup
│   │   ├── models/        # SQLAlchemy models
│   │   ├── pipeline/      # Video processing logic
│   │   ├── services/      # Business logic
│   │   ├── utils/         # FFmpeg/yt-dlp utilities
│   │   ├── workers/       # Background job system
│   │   ├── config.py      # Settings
│   │   └── main.py        # FastAPI app
│   ├── tests/             # Unit tests
│   └── data/              # Runtime data (auto-created)
├── frontend/
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks
│   │   ├── pages/         # Page components
│   │   ├── types/         # TypeScript types
│   │   └── utils/         # Utilities
│   └── public/
└── scripts/
    ├── dev.sh             # Development launcher
    ├── build.sh           # Production build
    └── ensure_deps.sh     # Dependency checker
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

Progress is tracked in SQLite and polled by the frontend.

### Video Processing Pipeline

1. **Scene Detection**: FFmpeg `select='gt(scene,THRESH)'` filter
2. **Segment Creation**: Convert timestamps to segments
3. **Post-processing**: Split long segments (>60s), merge short ones (<5s)
4. **Thumbnail Generation**: Extract frame at clip midpoint
5. **Export**: Re-encode with H.264/AAC for compatibility

### Export Destinations (Future)

The export system is designed for extensibility. Future destinations could include:
- TikTok direct upload
- Instagram Reels
- YouTube Shorts
- X/Twitter video

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

