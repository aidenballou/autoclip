"""yt-dlp utilities for YouTube video download."""
import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Optional

from app.config import settings


class YtdlpError(Exception):
    """yt-dlp related error."""
    pass


def check_ytdlp_available() -> bool:
    """Check if yt-dlp is available."""
    return shutil.which(settings.ytdlp_path) is not None


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a valid YouTube URL."""
    youtube_patterns = [
        r"^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^https?://(?:www\.)?youtube\.com/shorts/[\w-]+",
        r"^https?://youtu\.be/[\w-]+",
        r"^https?://(?:www\.)?youtube\.com/embed/[\w-]+",
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


async def get_video_info_ytdlp(url: str) -> dict:
    """
    Get video information from YouTube without downloading.
    
    Args:
        url: YouTube URL
        
    Returns:
        Dictionary with video metadata
    """
    cmd = [
        settings.ytdlp_path,
        "--dump-json",
        "--no-download",
        url
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        error_msg = stderr.decode()
        raise YtdlpError(f"Failed to get video info: {error_msg}")
    
    try:
        return json.loads(stdout.decode())
    except json.JSONDecodeError as e:
        raise YtdlpError(f"Failed to parse video info: {e}")


async def download_video(
    url: str,
    output_dir: Path,
    filename: str = "source",
    progress_callback=None
) -> Path:
    """
    Download a YouTube video with best quality.
    
    Args:
        url: YouTube URL
        output_dir: Directory to save the video
        filename: Base filename without extension
        progress_callback: Optional async callback(progress: float, message: str)
        
    Returns:
        Path to downloaded video file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_template = str(output_dir / f"{filename}.%(ext)s")
    
    # Try to get MP4 format, fallback to best available
    cmd = [
        settings.ytdlp_path,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-playlist",
        "--progress",
        "--newline",
        url
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    downloaded_path: Optional[Path] = None
    
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        
        line_str = line.decode("utf-8", errors="ignore").strip()
        
        # Parse progress
        if progress_callback:
            # Match download progress like "[download]  50.0% of 123.45MiB"
            progress_match = re.search(r"\[download\]\s+(\d+\.?\d*)%", line_str)
            if progress_match:
                progress = float(progress_match.group(1))
                await progress_callback(progress, f"Downloading: {progress:.1f}%")
            
            # Check for merger message
            elif "[Merger]" in line_str:
                await progress_callback(95, "Merging video and audio...")
            
            # Check for destination
            elif "Destination:" in line_str:
                dest_match = re.search(r"Destination:\s+(.+)", line_str)
                if dest_match:
                    downloaded_path = Path(dest_match.group(1))
            
            # Check for already downloaded
            elif "has already been downloaded" in line_str:
                await progress_callback(100, "Video already downloaded")
    
    await proc.wait()
    
    if proc.returncode != 0:
        raise YtdlpError("Download failed - check URL and try again")
    
    # Find the downloaded file
    if downloaded_path and downloaded_path.exists():
        return downloaded_path
    
    # Search for the file
    for ext in ["mp4", "mkv", "webm", "mov"]:
        potential_path = output_dir / f"{filename}.{ext}"
        if potential_path.exists():
            return potential_path
    
    # Check for any video file
    video_extensions = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
    for file in output_dir.iterdir():
        if file.suffix.lower() in video_extensions:
            return file
    
    raise YtdlpError("Download completed but video file not found")


async def extract_video_title(url: str) -> str:
    """
    Extract video title from YouTube URL.
    
    Args:
        url: YouTube URL
        
    Returns:
        Video title
    """
    try:
        info = await get_video_info_ytdlp(url)
        return info.get("title", "Untitled Video")
    except YtdlpError:
        return "Untitled Video"

