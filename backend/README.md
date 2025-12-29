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

AutoClip supports two segmentation pipelines:

| Pipeline | Description | Best For |
|----------|-------------|----------|
| **V2 (Default)** | Highlight-aware with quality scoring | Sports, esports, gaming, reaction videos |
| **V1** | Scene-cut based segmentation | Quick splits, montage editing |

Configure in `config.py` or via API: `segmentation_mode = "v1" | "v2"`

---

## V2 Pipeline: Highlight-Aware Segmentation

The V2 pipeline uses multi-signal analysis to detect meaningful highlight moments and select natural clip boundaries.

### Pipeline Stages

```
Video → Feature Extraction → Anchor Detection → Boundary Scoring 
      → Window Selection → Post-Filtering → Clips
```

### 1. Feature Extraction

Extracts time-series signals at fixed intervals (default: 0.5s):

**Audio Loudness (Primary excitement signal)**
```python
# Extract mono audio → compute RMS per window
audio_rms = sqrt(mean(samples^2))
audio_rms_z = z_score(audio_rms)  # Normalized
```

**Motion Score (Visual excitement proxy)**
```python
# Decode at low FPS (4fps) + downscale (160px wide)
motion_score = mean(abs(frame[t] - frame[t-1]))
motion_score_z = z_score(motion_score)
```

**Scene Cuts (Transition candidates)**
```bash
ffmpeg -vf "select='gt(scene,0.3)',showinfo" ...
```

**Fade/Freeze Detection (Boundary candidates)**
```bash
ffmpeg -vf "blackdetect=d=0.1:pix_th=0.10" ...
ffmpeg -vf "freezedetect=n=0.003:d=0.5" ...
```

### 2. Anchor Detection

Identifies highlight moments using:
- **Excitement peaks**: `loudness_z × motion_z` with non-max suppression
- **Audio-only peaks**: High loudness even with low motion (commentary/reactions)
- **Action sequences**: High motion + clustered scene cuts

### 3. Boundary Scoring

Scores each timepoint as a potential clip boundary:

```python
boundary_score = (
    0.45 × scene_strength +      # Scene cut proximity
    0.25 × audio_dip_strength +  # Quiet moment (transition)
    0.15 × fade_strength +       # Fade/black transition
    0.15 × motion_valley_strength
) - spacing_penalty
```

### 4. Window Selection

For each anchor, selects clip start/end by snapping to best boundaries:

```
Search ranges (relative to anchor):
- Start: [anchor - 14s, anchor - 2s] → fallback: anchor - 8s
- End: [anchor + 2s, anchor + 28s] → fallback: anchor + 12s
```

**Quality Score Computation:**
```python
quality = (
    0.4 × excitement_integral +
    0.2 × boundary_quality +
    0.2 × narrative_score -      # Anchor not too close to edges
    dead_time_penalty            # Penalize low-activity segments
) × anchor_boost
```

### 5. Post-Filtering

1. **Overlap Resolution**: IoU-based greedy selection (threshold: 0.35)
2. **Boring Filter**: Drop clips with mostly low activity (unless high anchor score)
3. **Deduplication**: Frame hash comparison for near-duplicates
4. **Quality Cutoff**: Reduce to target count (default: 200) by quality

### Debug Output

V2 writes detailed debug artifacts to `projects/{id}/debug/`:

**`segmentation_v2_debug.json`** contains:
- Config used
- Feature extraction summary
- All detected anchors with scores
- All boundary candidates with component scores
- Candidate windows before filtering
- Filter decisions (why clips were kept/dropped)
- Final clip list with quality breakdowns

**Reading Debug JSON:**
```python
import json
with open("segmentation_v2_debug.json") as f:
    debug = json.load(f)
    
# Top anchors
for a in sorted(debug["anchors"], key=lambda x: x["score"], reverse=True)[:5]:
    print(f"{a['time_sec']:.1f}s: score={a['score']:.2f}, reason={a['reason']}")

# Why clips were dropped
for d in debug["filter_report"]["overlap"]:
    if d["action"] == "drop_overlap":
        print(f"Dropped clip {d['clip_index']}: {d['reason']}")
```

### Tuning V2

Key parameters in `pipeline/v2/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `step_sec` | 0.5 | Feature sampling interval |
| `anchor_suppression_window_sec` | 4.0 | Min spacing between anchors |
| `pre_max` / `post_max` | 14 / 28 | Max boundary search range |
| `overlap_iou_threshold` | 0.35 | Overlap tolerance |
| `target_clip_count_soft` | 200 | Soft cap on clip count |
| `boundary_w_scene` | 0.45 | Scene cut weight in boundary score |

---

## V1 Pipeline: Scene-Based Segmentation

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
| `SEGMENTATION_MODE` | `v2` | `v1` (scene-based) or `v2` (highlight-aware) |
| `SCENE_THRESHOLD` | `0.3` | Scene detection threshold |
| `MIN_CLIP_SECONDS` | `5.0` | Minimum clip duration |
| `MAX_CLIP_SECONDS` | `60.0` | Maximum clip duration |
| `SERVE_FRONTEND` | `false` | Serve built frontend |

## Running Tests

```bash
cd backend
pytest tests/ -v

# Run only V2 pipeline tests
pytest tests/test_v2_pipeline.py -v
```

## CLI Test Harness

Analyze a video with the V2 pipeline from the command line:

```bash
# Run V2 analysis
python scripts/analyze_v2_cli.py video.mp4 --output-dir ./output

# Compare V1 and V2
python scripts/analyze_v2_cli.py video.mp4 --mode v1 -o ./v1_output
python scripts/analyze_v2_cli.py video.mp4 --mode v2 -o ./v2_output

# Output structure:
# ./output/
#   ├── v2_clips.json          # Final clips
#   ├── features/
#   │   └── features_v2.json   # Cached features
#   └── debug/
#       └── segmentation_v2_debug.json  # Full debug info
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

