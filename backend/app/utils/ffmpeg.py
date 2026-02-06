"""FFmpeg and ffprobe utilities."""
import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal, Tuple

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


@dataclass
class TextOverlay:
    """Text overlay configuration."""
    text: str
    position: str = "bottom"  # top, center, bottom
    font_size: int = 48
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    start_time: Optional[float] = None  # None = entire clip
    end_time: Optional[float] = None


@dataclass
class AudioOverlay:
    """Background audio overlay configuration."""
    audio_path: str
    volume: int = 30  # 0-100 (original audio volume)
    original_volume: int = 100  # 0-100 (video's original audio)
    loop: bool = True


@dataclass
class ExportPreset:
    """Export preset configuration."""
    name: str = "original"  # original, vertical
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    
    @classmethod
    def vertical(cls) -> "ExportPreset":
        """Create a vertical (9:16) preset for shorts/reels/tiktok."""
        return cls(
            name="vertical",
            width=settings.vertical_width,
            height=settings.vertical_height,
            fps=settings.vertical_fps,
        )
    
    @classmethod
    def original(cls) -> "ExportPreset":
        """Keep original video dimensions."""
        return cls(name="original")


VerticalFramingMode = Literal["fit", "fill", "blur"]
VerticalResolutionMode = Literal["fixed_1080", "limit_upscale", "match_source"]


def _round_even(value: int) -> int:
    """Round down to the nearest even integer (min 2)."""
    if value < 2:
        return 2
    return value - (value % 2)


def _resolve_vertical_dimensions(
    source_width: int,
    source_height: int,
    resolution_mode: VerticalResolutionMode,
    preset: Optional[ExportPreset] = None,
) -> Tuple[int, int]:
    """Resolve target dimensions for vertical output based on source and mode."""
    preset = preset or ExportPreset.vertical()
    target_w = preset.width or settings.vertical_width
    target_h = preset.height or settings.vertical_height

    if resolution_mode == "fixed_1080":
        target_w = preset.width or settings.vertical_width
        target_h = preset.height or settings.vertical_height
    elif resolution_mode == "match_source":
        target_h = source_height
        target_w = round(target_h * 9 / 16)
    elif resolution_mode == "limit_upscale":
        # Tiered output: 1080x1920 for >=1080p sources, otherwise 720x1280.
        if source_height >= settings.vertical_width:
            target_w = settings.vertical_width
            target_h = settings.vertical_height
        else:
            # vertical_min_height is used as the base width for 9:16 output.
            target_w = settings.vertical_min_height
            target_h = round(target_w * 16 / 9)
        # For very small sources, cap the upscale factor.
        if source_height < settings.vertical_min_height:
            max_height = int(source_height * settings.vertical_max_upscale)
            if max_height > 0 and max_height < target_h:
                target_h = max_height
                target_w = round(target_h * 9 / 16)

    target_w = _round_even(int(target_w))
    target_h = _round_even(int(target_h))
    return target_w, target_h


def _build_vertical_base_filter(
    target_w: int,
    target_h: int,
    framing: VerticalFramingMode,
) -> tuple[str, str]:
    """Build FFmpeg filtergraph for vertical framing."""
    if framing == "fit":
        filtergraph = (
            f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black[vbase]"
        )
        return filtergraph, "vbase"

    if framing == "fill":
        filtergraph = (
            f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={target_w}:{target_h}:(in_w-out_w)/2:(in_h-out_h)/2[vbase]"
        )
        return filtergraph, "vbase"

    # blur
    blur_sigma = settings.vertical_blur_sigma
    blur_dim = settings.vertical_blur_dim
    filtergraph = (
        f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"gblur=sigma={blur_sigma},eq=brightness=-{blur_dim}[bg];"
        f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[vbase]"
    )
    return filtergraph, "vbase"


def _build_text_filter(
    overlay: TextOverlay,
    clip_duration: float,
) -> str:
    """Build FFmpeg drawtext filter for text overlay."""
    # Escape special characters for FFmpeg
    text = overlay.text.replace("'", "\\'").replace(":", "\\:")
    
    # Convert hex color to FFmpeg format
    font_color = overlay.font_color.lstrip('#')
    border_color = overlay.border_color.lstrip('#')
    
    # Calculate Y position
    if overlay.position == "top":
        y_expr = "h*0.1"
    elif overlay.position == "center":
        y_expr = "(h-text_h)/2"
    else:  # bottom
        y_expr = "h*0.85-text_h"
    
    # Build the drawtext filter
    filter_parts = [
        f"drawtext=text='{text}'",
        f"fontsize={overlay.font_size}",
        f"fontcolor=0x{font_color}",
        f"borderw={overlay.border_width}",
        f"bordercolor=0x{border_color}",
        "x=(w-text_w)/2",  # Center horizontally
        f"y={y_expr}",
    ]
    
    # Add timing if specified
    if overlay.start_time is not None or overlay.end_time is not None:
        start = overlay.start_time or 0
        end = overlay.end_time or clip_duration
        filter_parts.append(f"enable='between(t,{start},{end})'")
    
    return ":".join(filter_parts)


def _build_scale_filter(preset: ExportPreset, source_width: int, source_height: int) -> str:
    """Build FFmpeg scale/pad filter for preset dimensions."""
    if preset.name == "original" or (preset.width is None and preset.height is None):
        return ""
    
    # Scale to fit within the target dimensions while maintaining aspect ratio,
    # then pad to exact dimensions (letterbox/pillarbox)
    target_w = preset.width
    target_h = preset.height
    
    return (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
    )


async def export_clip_enhanced(
    source_path: str | Path,
    output_path: str | Path,
    start_time: float,
    end_time: float,
    preset: Optional[ExportPreset] = None,
    vertical_framing: Optional[VerticalFramingMode] = None,
    vertical_resolution: Optional[VerticalResolutionMode] = None,
    text_overlay: Optional[TextOverlay] = None,
    audio_overlay: Optional[AudioOverlay] = None,
    progress_callback=None
) -> Path:
    """
    Export a clip with optional overlays and format preset.
    
    Args:
        source_path: Path to source video
        output_path: Path for output file
        start_time: Start time in seconds
        end_time: End time in seconds
        preset: Export preset (original, vertical)
        vertical_framing: Vertical framing mode (fit, fill, blur)
        vertical_resolution: Vertical resolution mode (fixed_1080, limit_upscale, match_source)
        text_overlay: Optional text overlay configuration
        audio_overlay: Optional background audio configuration
        progress_callback: Optional async callback(progress: float)
        
    Returns:
        Path to exported clip
    """
    source_path = Path(source_path)
    output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    duration = end_time - start_time
    preset = preset or ExportPreset.original()
    
    # Get source video info for scaling calculations
    source_info = await get_video_info(source_path)
    
    # Build video filter chain
    video_filter = None
    video_output_label = None
    filter_complex_parts = []
    post_filters = []
    
    # Add FPS filter if specified
    if preset.fps:
        post_filters.append(f"fps={preset.fps}")
    
    # Add text overlay filter
    if text_overlay:
        text_filter = _build_text_filter(text_overlay, duration)
        post_filters.append(text_filter)
    
    if preset.name == "vertical":
        framing = vertical_framing or settings.vertical_framing
        resolution = vertical_resolution or settings.vertical_resolution
        target_w, target_h = _resolve_vertical_dimensions(
            source_info.width,
            source_info.height,
            resolution,
            preset=preset,
        )
        base_filter, base_label = _build_vertical_base_filter(
            target_w,
            target_h,
            framing,
        )
        filter_complex_parts.append(base_filter)
        if post_filters:
            filter_complex_parts.append(f"[{base_label}]{','.join(post_filters)}[vout]")
            video_output_label = "vout"
        else:
            video_output_label = base_label
    else:
        video_filters = []
        scale_filter = _build_scale_filter(preset, source_info.width, source_info.height)
        if scale_filter:
            video_filters.append(scale_filter)
        if post_filters:
            video_filters.extend(post_filters)
        if video_filters:
            video_filter = ",".join(video_filters)
    
    # Build the command
    cmd = [
        settings.ffmpeg_path,
        "-y",
        "-ss", str(start_time),
        "-i", str(source_path),
        "-t", str(duration),
    ]
    
    # Add background audio input if specified
    if audio_overlay:
        audio_path = Path(audio_overlay.audio_path)
        if not audio_path.exists():
            raise FFmpegError(f"Background audio file not found: {audio_path}")
        cmd.extend(["-i", str(audio_path)])
    
    # Build filter complex for audio mixing
    if audio_overlay:
        if video_filter:
            filter_complex_parts.append(f"[0:v]{video_filter}[vout]")
            video_output_label = "vout"
            video_filter = None
        # Mix original audio with background audio
        orig_vol = audio_overlay.original_volume / 100
        bg_vol = audio_overlay.volume / 100
        
        if audio_overlay.loop:
            # Loop background audio to match clip duration
            filter_complex_parts.append(
                f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{duration}[bgaudio]"
            )
        else:
            filter_complex_parts.append("[1:a]anull[bgaudio]")
        
        filter_complex_parts.append(
            f"[0:a]volume={orig_vol}[origaudio];"
            f"[bgaudio]volume={bg_vol}[bgadjusted];"
            f"[origaudio][bgadjusted]amix=inputs=2:duration=first[aout]"
        )
    
    # Add filters to command
    if filter_complex_parts:
        filter_complex = ";".join(filter_complex_parts)
        cmd.extend(["-filter_complex", filter_complex])
        if video_output_label:
            cmd.extend(["-map", f"[{video_output_label}]"])
        else:
            cmd.extend(["-map", "0:v"])
        
        if audio_overlay:
            cmd.extend(["-map", "[aout]"])
        else:
            cmd.extend(["-map", "0:a"])
    elif video_filter:
        # Simple video filter without complex audio mixing
        cmd.extend(["-vf", video_filter])
    
    # Output encoding settings
    cmd.extend([
        "-c:v", settings.export_video_codec,
        "-preset", settings.export_video_preset,
        "-crf", str(settings.export_video_crf),
        "-pix_fmt", "yuv420p",
        "-c:a", settings.export_audio_codec,
        "-b:a", settings.export_audio_bitrate,
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        str(output_path)
    ])
    
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
        raise FFmpegError(f"Enhanced export failed: {stderr.decode()}")
    
    return output_path


async def get_audio_duration(audio_path: str | Path) -> float:
    """Get duration of an audio file."""
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FFmpegError(f"Audio file not found: {audio_path}")
    
    cmd = [
        settings.ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(audio_path)
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed on audio: {stderr.decode()}")
    
    data = json.loads(stdout.decode())
    return float(data.get("format", {}).get("duration", 0))
