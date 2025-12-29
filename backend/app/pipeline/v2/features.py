"""Feature extraction for V2 pipeline.

Extracts time-series signals:
- Audio loudness envelope (RMS)
- Motion/activity score (frame differences)
- Scene cut timestamps
- Fade/black transitions
"""
import asyncio
import json
import logging
import math
import os
import struct
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .config import V2PipelineConfig

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFeatures:
    """Container for all extracted features."""
    
    # Time axis (in seconds) for sampled features
    times: np.ndarray
    
    # Audio features (sampled at step_sec intervals)
    audio_rms: np.ndarray  # RMS loudness envelope
    audio_rms_z: np.ndarray  # Z-scored
    
    # Motion features (sampled at step_sec intervals)
    motion_score: np.ndarray  # Frame difference magnitude
    motion_score_z: np.ndarray  # Z-scored
    
    # Derived excitement signal
    excitement: np.ndarray  # Combined audio + motion
    
    # Scene cut timestamps (sparse events)
    scene_cuts: List[float]
    
    # Fade/black transitions (sparse events)
    fade_timestamps: List[float]
    
    # Freeze timestamps (sparse events)
    freeze_timestamps: List[float]
    
    # Metadata
    duration: float
    step_sec: float
    version: str
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "times": self.times.tolist(),
            "audio_rms": self.audio_rms.tolist(),
            "audio_rms_z": self.audio_rms_z.tolist(),
            "motion_score": self.motion_score.tolist(),
            "motion_score_z": self.motion_score_z.tolist(),
            "excitement": self.excitement.tolist(),
            "scene_cuts": self.scene_cuts,
            "fade_timestamps": self.fade_timestamps,
            "freeze_timestamps": self.freeze_timestamps,
            "duration": self.duration,
            "step_sec": self.step_sec,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedFeatures":
        """Load from dictionary."""
        return cls(
            times=np.array(data["times"]),
            audio_rms=np.array(data["audio_rms"]),
            audio_rms_z=np.array(data["audio_rms_z"]),
            motion_score=np.array(data["motion_score"]),
            motion_score_z=np.array(data["motion_score_z"]),
            excitement=np.array(data["excitement"]),
            scene_cuts=data["scene_cuts"],
            fade_timestamps=data.get("fade_timestamps", []),
            freeze_timestamps=data.get("freeze_timestamps", []),
            duration=data["duration"],
            step_sec=data["step_sec"],
            version=data["version"],
        )


def z_score(arr: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Compute z-scores with robust handling of constant arrays."""
    mean = np.mean(arr)
    std = np.std(arr)
    if std < eps:
        return np.zeros_like(arr)
    return (arr - mean) / std


def smooth(arr: np.ndarray, window: int = 3) -> np.ndarray:
    """Apply simple moving average smoothing."""
    if window <= 1 or len(arr) < window:
        return arr
    kernel = np.ones(window) / window
    # Pad to preserve length
    padded = np.pad(arr, (window // 2, window - window // 2 - 1), mode='edge')
    return np.convolve(padded, kernel, mode='valid')


async def extract_audio_rms(
    video_path: Path,
    duration: float,
    step_sec: float,
    sample_rate: int = 16000,
    progress_callback=None,
) -> np.ndarray:
    """
    Extract audio RMS loudness envelope.
    
    Uses FFmpeg to extract raw audio samples, then computes RMS per window.
    """
    num_samples = int(duration / step_sec) + 1
    window_samples = int(step_sec * sample_rate)
    
    # Extract mono audio as raw PCM s16le
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",  # No video
        "-ac", "1",  # Mono
        "-ar", str(sample_rate),
        "-f", "s16le",  # Raw PCM signed 16-bit little-endian
        "-"
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.warning(f"Audio extraction failed: {stderr.decode()[:500]}")
            return np.zeros(num_samples)
        
        # Parse raw audio samples
        total_samples = len(stdout) // 2  # 2 bytes per sample
        samples = np.array(struct.unpack(f'<{total_samples}h', stdout), dtype=np.float32)
        samples = samples / 32768.0  # Normalize to [-1, 1]
        
        # Compute RMS per window
        rms_values = []
        for i in range(num_samples):
            start_idx = int(i * window_samples)
            end_idx = min(start_idx + window_samples, len(samples))
            if start_idx >= len(samples):
                rms_values.append(0.0)
            else:
                window = samples[start_idx:end_idx]
                if len(window) > 0:
                    rms = np.sqrt(np.mean(window ** 2))
                    # Convert to dB-like scale (log)
                    rms_db = 20 * np.log10(max(rms, 1e-10)) + 60  # Offset to positive
                    rms_values.append(max(0, rms_db))
                else:
                    rms_values.append(0.0)
        
        result = np.array(rms_values)
        # Smooth to reduce noise
        result = smooth(result, window=3)
        
        if progress_callback:
            await progress_callback(25, "Audio features extracted")
        
        return result
        
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        return np.zeros(num_samples)


async def extract_motion_score(
    video_path: Path,
    duration: float,
    step_sec: float,
    fps: int = 4,
    width: int = 160,
    progress_callback=None,
) -> np.ndarray:
    """
    Extract motion score using frame differences.
    
    Decodes video at low FPS and resolution, computes frame-to-frame differences.
    """
    num_samples = int(duration / step_sec) + 1
    
    # Calculate height maintaining aspect ratio (assume 16:9)
    height = int(width * 9 / 16)
    
    # Extract frames as raw grayscale
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"fps={fps},scale={width}:{height},format=gray",
        "-f", "rawvideo",
        "-pix_fmt", "gray",
        "-"
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.warning(f"Motion extraction failed: {stderr.decode()[:500]}")
            return np.zeros(num_samples)
        
        frame_size = width * height
        num_frames = len(stdout) // frame_size
        
        if num_frames < 2:
            return np.zeros(num_samples)
        
        # Parse frames
        frames = []
        for i in range(num_frames):
            frame_data = stdout[i * frame_size:(i + 1) * frame_size]
            frame = np.frombuffer(frame_data, dtype=np.uint8).reshape(height, width)
            frames.append(frame.astype(np.float32))
        
        # Compute frame differences
        motion_per_frame = []
        for i in range(1, len(frames)):
            diff = np.abs(frames[i] - frames[i - 1])
            motion_per_frame.append(np.mean(diff))
        
        # Prepend first value
        motion_per_frame.insert(0, motion_per_frame[0] if motion_per_frame else 0)
        motion_array = np.array(motion_per_frame)
        
        # Resample to step_sec intervals
        frame_times = np.arange(len(motion_array)) / fps
        target_times = np.arange(num_samples) * step_sec
        
        # Simple interpolation
        motion_resampled = np.interp(target_times, frame_times, motion_array)
        
        # Smooth
        motion_resampled = smooth(motion_resampled, window=3)
        
        if progress_callback:
            await progress_callback(50, "Motion features extracted")
        
        return motion_resampled
        
    except Exception as e:
        logger.error(f"Motion extraction error: {e}")
        return np.zeros(num_samples)


async def detect_scene_cuts(
    video_path: Path,
    threshold: float = 0.3,
    progress_callback=None,
) -> List[float]:
    """
    Detect scene cut timestamps using FFmpeg.
    
    Returns list of timestamps where scene changes occur.
    """
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-"
    ]
    
    cuts = []
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # Read stderr (FFmpeg outputs filter info there)
        _, stderr = await proc.communicate()
        
        for line in stderr.decode("utf-8", errors="ignore").split("\n"):
            if "pts_time:" in line:
                for part in line.split():
                    if part.startswith("pts_time:"):
                        try:
                            ts = float(part.split(":")[1])
                            if ts > 0:
                                cuts.append(ts)
                        except (ValueError, IndexError):
                            pass
        
        if progress_callback:
            await progress_callback(65, f"Detected {len(cuts)} scene cuts")
        
        return sorted(set(cuts))
        
    except Exception as e:
        logger.error(f"Scene detection error: {e}")
        return []


async def detect_fades_and_freezes(
    video_path: Path,
    duration: float,
    progress_callback=None,
) -> Tuple[List[float], List[float]]:
    """
    Detect black/fade transitions and freeze frames.
    
    Returns (fade_timestamps, freeze_timestamps).
    """
    fade_timestamps = []
    freeze_timestamps = []
    
    # Black detection
    try:
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", "blackdetect=d=0.1:pix_th=0.10",
            "-f", "null",
            "-"
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        
        for line in stderr.decode("utf-8", errors="ignore").split("\n"):
            if "black_start:" in line:
                for part in line.split():
                    if part.startswith("black_start:"):
                        try:
                            ts = float(part.split(":")[1])
                            fade_timestamps.append(ts)
                        except (ValueError, IndexError):
                            pass
            if "black_end:" in line:
                for part in line.split():
                    if part.startswith("black_end:"):
                        try:
                            ts = float(part.split(":")[1])
                            fade_timestamps.append(ts)
                        except (ValueError, IndexError):
                            pass
                            
    except Exception as e:
        logger.warning(f"Fade detection error: {e}")
    
    # Freeze detection (expensive, so we limit duration)
    if duration < 600:  # Only for videos < 10 minutes
        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", "freezedetect=n=0.003:d=0.5",
                "-f", "null",
                "-"
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            
            for line in stderr.decode("utf-8", errors="ignore").split("\n"):
                if "freeze_start:" in line:
                    for part in line.split():
                        if part.startswith("freeze_start:"):
                            try:
                                ts = float(part.split(":")[1])
                                freeze_timestamps.append(ts)
                            except (ValueError, IndexError):
                                pass
                                
        except Exception as e:
            logger.warning(f"Freeze detection error: {e}")
    
    if progress_callback:
        await progress_callback(75, "Transition detection complete")
    
    return sorted(set(fade_timestamps)), sorted(set(freeze_timestamps))


async def extract_features(
    video_path: Path,
    duration: float,
    config: V2PipelineConfig,
    progress_callback=None,
) -> ExtractedFeatures:
    """
    Extract all features from video.
    
    This is the main entry point for feature extraction.
    """
    logger.info(f"Extracting features from {video_path} (duration: {duration:.1f}s)")
    
    # Create time axis
    num_samples = int(duration / config.step_sec) + 1
    times = np.arange(num_samples) * config.step_sec
    
    # Extract features in parallel where possible
    audio_task = extract_audio_rms(
        video_path, duration, config.step_sec,
        config.audio_sample_rate, progress_callback
    )
    
    motion_task = extract_motion_score(
        video_path, duration, config.step_sec,
        config.motion_fps, config.motion_width, progress_callback
    )
    
    scene_task = detect_scene_cuts(
        video_path, config.scene_threshold, progress_callback
    )
    
    # Run in parallel
    audio_rms, motion_score, scene_cuts = await asyncio.gather(
        audio_task, motion_task, scene_task
    )
    
    # Detect fades/freezes (can be slower)
    fade_timestamps, freeze_timestamps = await detect_fades_and_freezes(
        video_path, duration, progress_callback
    )
    
    # Ensure arrays are the same length
    audio_rms = audio_rms[:num_samples]
    motion_score = motion_score[:num_samples]
    
    if len(audio_rms) < num_samples:
        audio_rms = np.pad(audio_rms, (0, num_samples - len(audio_rms)), mode='edge')
    if len(motion_score) < num_samples:
        motion_score = np.pad(motion_score, (0, num_samples - len(motion_score)), mode='edge')
    
    # Compute z-scores
    audio_rms_z = z_score(audio_rms)
    motion_score_z = z_score(motion_score)
    
    # Compute combined excitement signal
    # Positive z-scores indicate above-average activity
    excitement = np.maximum(0, audio_rms_z) * 0.6 + np.maximum(0, motion_score_z) * 0.4
    
    if progress_callback:
        await progress_callback(80, "Feature extraction complete")
    
    return ExtractedFeatures(
        times=times,
        audio_rms=audio_rms,
        audio_rms_z=audio_rms_z,
        motion_score=motion_score,
        motion_score_z=motion_score_z,
        excitement=excitement,
        scene_cuts=scene_cuts,
        fade_timestamps=fade_timestamps,
        freeze_timestamps=freeze_timestamps,
        duration=duration,
        step_sec=config.step_sec,
        version=config.cache_version,
    )


def load_cached_features(cache_path: Path, config: V2PipelineConfig) -> Optional[ExtractedFeatures]:
    """Load features from cache if valid."""
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r') as f:
            data = json.load(f)
        
        if data.get("version") != config.cache_version:
            logger.info(f"Cache version mismatch, re-extracting features")
            return None
        
        return ExtractedFeatures.from_dict(data)
        
    except Exception as e:
        logger.warning(f"Failed to load cached features: {e}")
        return None


def save_features_cache(features: ExtractedFeatures, cache_path: Path):
    """Save features to cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w') as f:
        json.dump(features.to_dict(), f)

