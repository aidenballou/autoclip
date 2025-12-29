"""Clip processing - dispatches to v1 or v2 pipeline.

This module provides backward compatibility while allowing selection
of either v1 (scene-based) or v2 (highlight-aware) pipeline.
"""
from dataclasses import dataclass
from typing import List, Optional, Literal
from pathlib import Path

from app.config import settings

# Re-export Segment for backward compatibility
from app.pipeline.v1.scene_segmentation import (
    Segment,
    create_segments_from_scenes,
    merge_short_segments,
    split_long_segments,
    post_process_segments,
)


SegmentationMode = Literal["v1", "v2"]


def get_segmentation_mode(override: Optional[str] = None) -> SegmentationMode:
    """Get the segmentation mode to use."""
    if override and override in ("v1", "v2"):
        return override
    return settings.segmentation_mode


def generate_clips_from_video(
    scene_timestamps: List[float],
    video_duration: float,
    min_duration: float = None,
    max_duration: float = None
) -> List[Segment]:
    """
    V1 interface: Generate clips from scene detection results.
    
    This is the original interface for backward compatibility.
    For V2 pipeline, use run_v2_pipeline() directly.
    
    Args:
        scene_timestamps: Timestamps where scenes change
        video_duration: Total video duration
        min_duration: Minimum clip duration
        max_duration: Maximum clip duration
        
    Returns:
        List of processed segments ready for clip creation
    """
    from app.pipeline.v1 import generate_clips_from_video as v1_generate
    return v1_generate(scene_timestamps, video_duration, min_duration, max_duration)


async def generate_clips_auto(
    video_path: str | Path,
    video_duration: float,
    project_dir: Path,
    mode: Optional[SegmentationMode] = None,
    progress_callback=None,
) -> List[dict]:
    """
    Generate clips using the configured or specified pipeline.
    
    Returns list of clip dictionaries with:
    - start_time: float
    - end_time: float
    - duration: float
    - quality_score: Optional[float] (v2 only)
    - anchor_time_sec: Optional[float] (v2 only)
    - generation_version: str
    
    Args:
        video_path: Path to video file
        video_duration: Video duration in seconds
        project_dir: Project directory for caching/debug
        mode: Force v1 or v2 (uses config default if None)
        progress_callback: Async progress callback
        
    Returns:
        List of clip dictionaries
    """
    mode = get_segmentation_mode(mode)
    
    if mode == "v2":
        from app.pipeline.v2.runner import run_v2_pipeline
        
        result = await run_v2_pipeline(
            video_path, video_duration, project_dir,
            progress_callback=progress_callback
        )
        return result.to_clip_list()
    
    else:
        # V1 pipeline
        from app.utils.ffmpeg import detect_scenes
        from app.pipeline.v1 import generate_clips_from_video
        
        if progress_callback:
            await progress_callback(10, "Detecting scenes (v1)...")
        
        # Detect scenes
        scene_timestamps = await detect_scenes(
            video_path,
            threshold=settings.scene_threshold,
            progress_callback=progress_callback if progress_callback else None
        )
        
        if progress_callback:
            await progress_callback(70, "Processing segments...")
        
        # Generate clips
        segments = generate_clips_from_video(scene_timestamps, video_duration)
        
        # Convert to dict format with v1 metadata
        clips = []
        for i, seg in enumerate(segments):
            clips.append({
                "start_time": seg.start,
                "end_time": seg.end,
                "duration": seg.duration,
                "quality_score": None,  # V1 doesn't compute quality
                "anchor_time_sec": None,  # V1 doesn't have anchors
                "generation_version": "v1",
            })
        
        if progress_callback:
            await progress_callback(90, f"Generated {len(clips)} clips (v1)")
        
        return clips


# Export for backward compatibility
__all__ = [
    "Segment",
    "create_segments_from_scenes",
    "merge_short_segments",
    "split_long_segments",
    "post_process_segments",
    "generate_clips_from_video",
    "generate_clips_auto",
    "get_segmentation_mode",
    "SegmentationMode",
]
