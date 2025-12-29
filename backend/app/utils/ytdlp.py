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
        # Enable remote JS challenge solver for YouTube signature decryption
        "--remote-components", "ejs:github",
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
    import logging
    logger = logging.getLogger(__name__)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean up any partial downloads first
    for partial in output_dir.glob("*.part"):
        try:
            partial.unlink()
        except Exception:
            pass
    for temp in output_dir.glob("*.ytdl"):
        try:
            temp.unlink()
        except Exception:
            pass
    
    output_template = str(output_dir / f"{filename}.%(ext)s")
    
    # More robust format selection:
    # bv* = best video (required), ba = best audio
    # The key is to ALWAYS require video (bv) not just best (b)
    # Format priority:
    # 1. Best video (mp4) + best audio (m4a) - ideal for MP4 output
    # 2. Best video (mp4) + best audio (any) 
    # 3. Best video (any) + best audio (any)
    # 4. Best single format that contains video (NOT audio-only)
    cmd = [
        settings.ytdlp_path,
        # CRITICAL: bv* requires video stream, won't select audio-only
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/bv*[ext=mp4]+ba/bv*+ba/bv*",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-playlist",
        "--progress",
        "--newline",
        # Force overwrite
        "--force-overwrites",
        # Embed metadata
        "--embed-metadata",
        # Enable remote JS challenge solver for YouTube signature decryption
        "--remote-components", "ejs:github",
        url
    ]
    
    logger.info(f"Running yt-dlp command: {' '.join(cmd)}")
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    downloaded_path: Optional[Path] = None
    merged_path: Optional[Path] = None
    output_lines = []
    
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        
        line_str = line.decode("utf-8", errors="ignore").strip()
        output_lines.append(line_str)
        
        # Parse progress
        if progress_callback:
            # Match download progress like "[download]  50.0% of 123.45MiB"
            progress_match = re.search(r"\[download\]\s+(\d+\.?\d*)%", line_str)
            if progress_match:
                progress = float(progress_match.group(1))
                await progress_callback(progress * 0.9, f"Downloading: {progress:.1f}%")  # Leave room for merge
            
            # Check for merger message
            elif "[Merger]" in line_str:
                await progress_callback(92, "Merging video and audio...")
            
            # Check for ffmpeg merge
            elif "Merging formats" in line_str:
                await progress_callback(90, "Merging formats...")
            
            # Check for already downloaded
            elif "has already been downloaded" in line_str:
                await progress_callback(95, "Video already downloaded")
        
        # Track the merged output path (more reliable than Destination)
        if "Merging formats into" in line_str:
            merge_match = re.search(r'Merging formats into "(.+)"', line_str)
            if merge_match:
                merged_path = Path(merge_match.group(1))
                logger.info(f"Merge output: {merged_path}")
        
        # Track destination (fallback)
        elif "Destination:" in line_str:
            dest_match = re.search(r"Destination:\s+(.+)", line_str)
            if dest_match:
                downloaded_path = Path(dest_match.group(1))
        
        # Track final output
        elif line_str.startswith("[download]") and "has already been downloaded" in line_str:
            # Extract path from "... /path/to/file.mp4 has already been downloaded"
            path_match = re.search(r'\[download\]\s+(.+\.(?:mp4|mkv|webm|mov))\s+has already been downloaded', line_str)
            if path_match:
                merged_path = Path(path_match.group(1))
    
    await proc.wait()
    
    if proc.returncode != 0:
        # Log all output for debugging
        logger.error(f"yt-dlp failed with output:\n" + "\n".join(output_lines[-20:]))
        raise YtdlpError("Download failed - check URL and try again")
    
    if progress_callback:
        await progress_callback(95, "Verifying download...")
    
    # Priority order for finding the file:
    # 1. Merged path from logs
    # 2. Downloaded path from logs
    # 3. Search for the file
    
    final_path = None
    
    if merged_path and merged_path.exists():
        final_path = merged_path
        logger.info(f"Using merged path: {final_path}")
    elif downloaded_path and downloaded_path.exists():
        final_path = downloaded_path
        logger.info(f"Using downloaded path: {final_path}")
    else:
        # Search for the file (prefer .mp4)
        for ext in ["mp4", "mkv", "webm", "mov"]:
            potential_path = output_dir / f"{filename}.{ext}"
            if potential_path.exists():
                # Make sure it's not a partial file
                if potential_path.stat().st_size > 1000:  # At least 1KB
                    final_path = potential_path
                    logger.info(f"Found file: {final_path}")
                    break
        
        # Last resort: any video file that's not a partial
        if not final_path:
            video_extensions = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
            for file in output_dir.iterdir():
                if file.suffix.lower() in video_extensions and not file.name.endswith('.part'):
                    if file.stat().st_size > 1000:
                        final_path = file
                        logger.info(f"Found video file: {final_path}")
                        break
    
    if not final_path:
        logger.error(f"No video file found in {output_dir}. Contents: {list(output_dir.iterdir())}")
        logger.error(f"Last yt-dlp output:\n" + "\n".join(output_lines[-20:]))
        raise YtdlpError("Download completed but video file not found")
    
    # Verify the file has a video stream using ffprobe
    verify_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(final_path)
    ]
    
    try:
        verify_proc = await asyncio.create_subprocess_exec(
            *verify_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await verify_proc.communicate()
        
        if b"video" not in stdout:
            logger.error(f"Downloaded file has no video stream: {final_path}")
            logger.error(f"File size: {final_path.stat().st_size} bytes")
            raise YtdlpError(f"Downloaded file has no video stream. The video may be unavailable or restricted.")
    except FileNotFoundError:
        # ffprobe not found, skip verification
        logger.warning("ffprobe not found, skipping video stream verification")
    
    return final_path


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

