# V1 Pipeline - Scene-based segmentation
"""
V1 Pipeline: Scene-Cut Based Segmentation

This is the original pipeline that uses FFmpeg scene detection
to create clips between scene change timestamps.

Kept for comparison and fallback.
"""
from .scene_segmentation import (
    generate_clips_from_video,
    create_segments_from_scenes,
    merge_short_segments,
    split_long_segments,
    post_process_segments,
    Segment,
)

__all__ = [
    "generate_clips_from_video",
    "create_segments_from_scenes",
    "merge_short_segments",
    "split_long_segments",
    "post_process_segments",
    "Segment",
]

