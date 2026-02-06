"""Application configuration."""
import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    # App settings
    app_name: str = "AutoClip"
    debug: bool = True
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/autoclip.db"
    
    # Data directories
    data_dir: Path = Path("./data")
    projects_dir: Path = Path("./data/projects")
    
    # Segmentation pipeline
    segmentation_mode: Literal["v1", "v2"] = "v2"  # v1=scene-based, v2=highlight-aware
    
    # Video processing (used by both v1 and v2)
    scene_threshold: float = 0.3  # FFmpeg scene detection threshold
    min_clip_seconds: float = 5.0  # Minimum clip duration
    max_clip_seconds: float = 60.0  # Maximum clip duration
    target_max_clips: int = 300  # Soft limit for number of clips
    
    # FFmpeg settings
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    
    # yt-dlp settings
    ytdlp_path: str = "yt-dlp"
    
    # Export settings
    export_video_codec: str = "libx264"
    export_video_preset: str = "veryfast"
    export_video_crf: int = 18
    export_audio_codec: str = "aac"
    export_audio_bitrate: str = "192k"
    
    # Vertical video preset (9:16 for shorts/reels/tiktok)
    vertical_width: int = 1080
    vertical_height: int = 1920
    vertical_fps: int = 30
    vertical_framing: Literal["fit", "fill", "blur"] = "fill"
    vertical_resolution: Literal["fixed_1080", "limit_upscale", "match_source"] = "limit_upscale"
    vertical_max_upscale: float = 1.35
    # For limit_upscale: base tier width for 9:16 output (720 -> 720x1280)
    vertical_min_height: int = 720
    vertical_blur_sigma: int = 20
    vertical_blur_dim: float = 0.15
    
    # Text overlay defaults
    default_font_path: str = "/System/Library/Fonts/Helvetica.ttc"  # macOS default
    default_font_size: int = 48
    default_font_color: str = "white"
    default_text_border_color: str = "black"
    default_text_border_width: int = 2
    
    # Thumbnail settings
    thumbnail_width: int = 320
    thumbnail_height: int = 180
    thumbnail_format: str = "jpg"
    
    # Frontend
    frontend_url: str = "http://localhost:5173"
    serve_frontend: bool = False
    frontend_build_dir: Path = Path("../frontend/dist")
    
    # YouTube OAuth (for direct uploads)
    youtube_client_id: str = ""
    youtube_client_secret: str = ""


settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.projects_dir.mkdir(parents=True, exist_ok=True)
