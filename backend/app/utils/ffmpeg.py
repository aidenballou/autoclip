"""FFmpeg and ffprobe utilities."""
import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import settings


@dataclass
class VideoInfo:
    """Video metadata container."""
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: Optional[str]
    format_name: str
    bit_rate: Optional[int]


class FFmpegError(Exception):
    """FFmpeg related error."""
    pass


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which(settings.ffmpeg_path) is not None


def check_ffprobe_available() -> bool:
    """Check if ffprobe is available."""
    return shutil.which(settings.ffprobe_path) is not None


async def get_video_info(video_path: str | Path) -> VideoInfo:
    """
    Get video metadata using ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        VideoInfo with video metadata
        
    Raises:
        FFmpegError: If ffprobe fails
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FFmpegError(f"Video file not found: {video_path}")
    
    cmd = [
        settings.ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path)
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise FFmpegError(f"ffprobe failed: {stderr.decode()}")
        
        data = json.loads(stdout.decode())
        
        # Find video stream
        video_stream = None
        audio_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream
        
        if not video_stream:
            raise FFmpegError("No video stream found")
        
        # Parse frame rate
        fps_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) > 0 else 30.0
        else:
            fps = float(fps_str)
        
        # Get duration
        duration = float(data.get("format", {}).get("duration", 0))
        if duration == 0:
            duration = float(video_stream.get("duration", 0))
        
        return VideoInfo(
            duration=duration,
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=fps,
            video_codec=video_stream.get("codec_name", "unknown"),
            audio_codec=audio_stream.get("codec_name") if audio_stream else None,
            format_name=data.get("format", {}).get("format_name", "unknown"),
            bit_rate=int(data.get("format", {}).get("bit_rate", 0)) or None
        )
    except json.JSONDecodeError as e:
        raise FFmpegError(f"Failed to parse ffprobe output: {e}")
    except Exception as e:
        if isinstance(e, FFmpegError):
            raise
        raise FFmpegError(f"ffprobe error: {e}")


async def detect_scenes(
    video_path: str | Path,
    threshold: float = None,
    progress_callback=None
) -> list[float]:
    """
    Detect scene changes in a video using FFmpeg.
    
    Args:
        video_path: Path to video file
        threshold: Scene detection threshold (0-1), lower = more sensitive
        progress_callback: Optional async callback(progress: float) for progress updates
        
    Returns:
        List of timestamps (in seconds) where scene changes occur
    """
    video_path = Path(video_path)
    if threshold is None:
        threshold = settings.scene_threshold
    
    # Get video duration for progress tracking
    info = await get_video_info(video_path)
    total_duration = info.duration
    
    # FFmpeg scene detection command
    cmd = [
        settings.ffmpeg_path,
        "-i", str(video_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-"
    ]
    
    scenes = [0.0]  # Always start with 0
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Read stderr line by line (FFmpeg outputs to stderr)
    last_progress = 0
    while True:
        line = await proc.stderr.readline()
        if not line:
            break
        
        line_str = line.decode("utf-8", errors="ignore")
        
        # Parse scene detection output
        if "pts_time:" in line_str:
            try:
                # Extract pts_time value
                for part in line_str.split():
                    if part.startswith("pts_time:"):
                        timestamp = float(part.split(":")[1])
                        if timestamp > 0 and timestamp not in scenes:
                            scenes.append(timestamp)
                        break
            except (ValueError, IndexError):
                pass
        
        # Track progress from time= output
        if progress_callback and "time=" in line_str:
            try:
                for part in line_str.split():
                    if part.startswith("time="):
                        time_str = part.split("=")[1]
                        # Parse HH:MM:SS.ms format
                        parts = time_str.split(":")
                        if len(parts) == 3:
                            hours, mins, secs = parts
                            current_time = float(hours) * 3600 + float(mins) * 60 + float(secs)
                            progress = min(100, (current_time / total_duration) * 100)
                            if progress - last_progress >= 1:  # Update every 1%
                                await progress_callback(progress)
                                last_progress = progress
                        break
            except (ValueError, IndexError):
                pass
    
    await proc.wait()
    
    # Sort and return unique scenes
    scenes = sorted(set(scenes))
    return scenes


async def generate_thumbnail(
    video_path: str | Path,
    output_path: str | Path,
    timestamp: float,
    width: int = None,
    height: int = None
) -> Path:
    """
    Generate a thumbnail from a video at a specific timestamp.
    
    Args:
        video_path: Path to video file
        output_path: Path to save thumbnail
        timestamp: Time in seconds to capture
        width: Optional thumbnail width
        height: Optional thumbnail height
        
    Returns:
        Path to generated thumbnail
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    
    width = width or settings.thumbnail_width
    height = height or settings.thumbnail_height
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        settings.ffmpeg_path,
        "-y",  # Overwrite
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-q:v", "2",
        str(output_path)
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    _, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        raise FFmpegError(f"Thumbnail generation failed: {stderr.decode()}")
    
    return output_path


async def export_clip(
    source_path: str | Path,
    output_path: str | Path,
    start_time: float,
    end_time: float,
    progress_callback=None
) -> Path:
    """
    Export a clip from the source video.
    
    Args:
        source_path: Path to source video
        output_path: Path for output file
        start_time: Start time in seconds
        end_time: End time in seconds
        progress_callback: Optional async callback(progress: float)
        
    Returns:
        Path to exported clip
    """
    source_path = Path(source_path)
    output_path = Path(output_path)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    duration = end_time - start_time
    
    cmd = [
        settings.ffmpeg_path,
        "-y",
        "-ss", str(start_time),
        "-i", str(source_path),
        "-t", str(duration),
        "-c:v", settings.export_video_codec,
        "-preset", settings.export_video_preset,
        "-crf", str(settings.export_video_crf),
        "-c:a", settings.export_audio_codec,
        "-b:a", settings.export_audio_bitrate,
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        str(output_path)
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    last_progress = 0
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        
        line_str = line.decode("utf-8", errors="ignore").strip()
        
        if progress_callback and line_str.startswith("out_time_ms="):
            try:
                out_time_us = int(line_str.split("=")[1])
                out_time_s = out_time_us / 1_000_000
                progress = min(100, (out_time_s / duration) * 100)
                if progress - last_progress >= 1:
                    await progress_callback(progress)
                    last_progress = progress
            except (ValueError, IndexError):
                pass
    
    await proc.wait()
    
    if proc.returncode != 0:
        stderr = await proc.stderr.read()
        raise FFmpegError(f"Export failed: {stderr.decode()}")
    
    return output_path


async def export_compound_clip(
    source_path: str | Path,
    output_path: str | Path,
    segments: list[tuple[float, float]],
    progress_callback=None
) -> Path:
    """
    Export a compound clip by concatenating multiple segments.
    
    Args:
        source_path: Path to source video
        output_path: Path for output file
        segments: List of (start_time, end_time) tuples
        progress_callback: Optional async callback(progress: float)
        
    Returns:
        Path to exported clip
    """
    source_path = Path(source_path)
    output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if len(segments) == 1:
        # Single segment, use simple export
        return await export_clip(
            source_path, output_path,
            segments[0][0], segments[0][1],
            progress_callback
        )
    
    # Build filter complex for multiple segments
    filter_parts = []
    concat_inputs = []
    
    for i, (start, end) in enumerate(segments):
        duration = end - start
        filter_parts.append(
            f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]"
        )
        concat_inputs.append(f"[v{i}][a{i}]")
    
    filter_complex = ";".join(filter_parts)
    filter_complex += f";{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=1[outv][outa]"
    
    total_duration = sum(end - start for start, end in segments)
    
    cmd = [
        settings.ffmpeg_path,
        "-y",
        "-i", str(source_path),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", settings.export_video_codec,
        "-preset", settings.export_video_preset,
        "-crf", str(settings.export_video_crf),
        "-c:a", settings.export_audio_codec,
        "-b:a", settings.export_audio_bitrate,
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        str(output_path)
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    last_progress = 0
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        
        line_str = line.decode("utf-8", errors="ignore").strip()
        
        if progress_callback and line_str.startswith("out_time_ms="):
            try:
                out_time_us = int(line_str.split("=")[1])
                out_time_s = out_time_us / 1_000_000
                progress = min(100, (out_time_s / total_duration) * 100)
                if progress - last_progress >= 1:
                    await progress_callback(progress)
                    last_progress = progress
            except (ValueError, IndexError):
                pass
    
    await proc.wait()
    
    if proc.returncode != 0:
        stderr = await proc.stderr.read()
        raise FFmpegError(f"Compound export failed: {stderr.decode()}")
    
    return output_path

