# AutoClip Backend

Python FastAPI backend for video processing, scene detection, and clip management.

## Architecture

```
backend/
├── app/
│   ├── api/           # REST API routes and schemas
│   ├── db/            # Database connection and session management
│   ├── models/        # SQLAlchemy models
│   ├── pipeline/      # Video processing algorithms
│   ├── services/      # Business logic layer
│   ├── utils/         # FFmpeg and yt-dlp utilities
│   ├── workers/       # Background job system
│   ├── config.py      # Application configuration
│   └── main.py        # FastAPI application entry point
├── tests/             # Unit tests
├── data/              # Runtime data (created automatically)
│   ├── projects/      # Project files and thumbnails
│   └── autoclip.db    # SQLite database
└── requirements.txt   # Python dependencies
```

## Video Processing Pipeline

### Scene Detection

Uses FFmpeg's `select` filter with scene detection:

```bash
ffmpeg -i input.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null -
```

- Threshold: `0.3` (configurable in `config.py`)
- Lower threshold = more sensitive = more scene changes detected
- Output is parsed to extract `pts_time` values

### Clip Generation Algorithm

1. **Create raw segments** from scene detection timestamps
2. **Split long segments** (>60s) into equal parts
3. **Merge short segments** (<5s) with neighbors
4. **Adaptive merging** if clip count exceeds soft limit (300)

### Thumbnail Generation

Extracts a single frame at the clip midpoint:

```bash
ffmpeg -ss {midpoint} -i input.mp4 -vframes 1 \
  -vf "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2" \
  -q:v 2 output.jpg
```

### Export Commands

**Single clip:**
```bash
ffmpeg -y -ss {start} -i source.mp4 -t {duration} \
  -c:v libx264 -preset veryfast -crf 18 \
  -c:a aac -b:a 192k -movflags +faststart \
  output.mp4
```

**Compound clip (multiple segments):**
Uses FFmpeg filter_complex with `trim`, `atrim`, and `concat`:

```bash
ffmpeg -i source.mp4 -filter_complex \
  "[0:v]trim=start=10:end=20,setpts=PTS-STARTPTS[v0];
   [0:a]atrim=start=10:end=20,asetpts=PTS-STARTPTS[a0];
   [0:v]trim=start=30:end=40,setpts=PTS-STARTPTS[v1];
   [0:a]atrim=start=30:end=40,asetpts=PTS-STARTPTS[a1];
   [v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]" \
  -map "[outv]" -map "[outa]" \
  -c:v libx264 -preset veryfast -crf 18 \
  -c:a aac -b:a 192k -movflags +faststart \
  output.mp4
```

## Background Job System

Uses asyncio-based background tasks without external dependencies:

- Jobs are tracked in SQLite with progress updates
- Each job type has a registered handler
- Progress callbacks allow real-time status updates
- Jobs can be cancelled

**Job Types:**
- `download` - Download YouTube video
- `analyze` - Scene detection + clip generation + thumbnails
- `export` - Single clip or compound clip export
- `export_batch` - Multiple clips export

## API Endpoints

### Projects
- `POST /api/projects/youtube` - Create from YouTube URL
- `POST /api/projects/local` - Create from local file
- `POST /api/projects/upload` - Upload video file
- `GET /api/projects` - List all projects
- `GET /api/projects/{id}` - Get project details
- `DELETE /api/projects/{id}` - Delete project
- `POST /api/projects/{id}/download` - Start download job
- `POST /api/projects/{id}/analyze` - Start analysis job
- `POST /api/projects/{id}/output-folder` - Set output folder

### Clips
- `GET /api/projects/{id}/clips` - List clips
- `GET /api/clips/{id}` - Get clip details
- `PATCH /api/clips/{id}` - Update clip (trim, rename)
- `DELETE /api/clips/{id}` - Delete clip

### Compound Clips
- `POST /api/projects/{id}/compound-clips` - Create compound clip
- `GET /api/projects/{id}/compound-clips` - List compound clips
- `GET /api/compound-clips/{id}` - Get compound clip
- `DELETE /api/compound-clips/{id}` - Delete compound clip

### Exports
- `POST /api/projects/{id}/exports` - Export clip or compound
- `POST /api/projects/{id}/exports/batch` - Batch export

### Jobs
- `GET /api/jobs/{id}` - Get job status
- `GET /api/projects/{id}/jobs` - List project jobs

### Static Files
- `GET /api/projects/{id}/video` - Stream source video
- `GET /api/projects/{id}/thumbnails/{clip_id}` - Get thumbnail

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `true` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/autoclip.db` | Database URL |
| `SCENE_THRESHOLD` | `0.3` | Scene detection threshold |
| `MIN_CLIP_SECONDS` | `5.0` | Minimum clip duration |
| `MAX_CLIP_SECONDS` | `60.0` | Maximum clip duration |
| `SERVE_FRONTEND` | `false` | Serve built frontend |

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with hot reload
python -m uvicorn app.main:app --reload --port 8000
```

## Export Destinations Interface

The export system is designed with extensibility in mind. To add a new export destination:

1. Create a new handler in `app/workers/handlers.py`
2. Implement the destination-specific logic (API calls, authentication, etc.)
3. Add a new job type in `app/models/job.py`
4. Create API endpoints in `app/api/routes.py`

Future destinations could include:
- Direct upload to TikTok
- Instagram Reels
- YouTube Shorts
- X/Twitter video posts

