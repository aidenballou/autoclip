"""V1 Scene-based segmentation logic.

Original pipeline that creates clips between scene change timestamps.
"""
from dataclasses import dataclass
from typing import List

from app.config import settings


@dataclass
class Segment:
    """A video segment with start and end times."""
    start: float
    end: float
    
    @property
    def duration(self) -> float:
        return self.end - self.start
    
    def __repr__(self):
        return f"Segment({self.start:.2f}-{self.end:.2f}, dur={self.duration:.2f}s)"


def create_segments_from_scenes(
    scene_timestamps: List[float],
    video_duration: float
) -> List[Segment]:
    """
    Create raw segments from scene detection timestamps.
    
    Args:
        scene_timestamps: List of timestamps where scenes change
        video_duration: Total video duration
        
    Returns:
        List of Segment objects
    """
    if not scene_timestamps:
        return [Segment(0, video_duration)]
    
    # Ensure timestamps are sorted and unique
    timestamps = sorted(set(scene_timestamps))
    
    # Ensure we start at 0
    if timestamps[0] > 0:
        timestamps.insert(0, 0.0)
    
    # Ensure we end at video duration
    if timestamps[-1] < video_duration:
        timestamps.append(video_duration)
    
    # Create segments between consecutive timestamps
    segments = []
    for i in range(len(timestamps) - 1):
        seg = Segment(timestamps[i], timestamps[i + 1])
        if seg.duration > 0.1:  # Filter out tiny segments
            segments.append(seg)
    
    return segments


def merge_short_segments(
    segments: List[Segment],
    min_duration: float = None
) -> List[Segment]:
    """
    Merge segments shorter than min_duration with neighbors.
    
    Strategy:
    - Merge short segment with whichever neighbor results in smaller combined duration
    - Prefer merging forward (with next segment)
    
    Args:
        segments: List of segments to process
        min_duration: Minimum segment duration (uses config default if not provided)
        
    Returns:
        List of merged segments
    """
    if min_duration is None:
        min_duration = settings.min_clip_seconds
    
    if not segments:
        return []
    
    if len(segments) == 1:
        return segments
    
    # Work with a copy
    result = list(segments)
    
    # Keep merging until no short segments remain
    changed = True
    while changed:
        changed = False
        i = 0
        new_result = []
        
        while i < len(result):
            current = result[i]
            
            if current.duration < min_duration and len(result) > 1:
                # Need to merge this segment
                if i == 0:
                    # First segment - merge with next
                    if i + 1 < len(result):
                        merged = Segment(current.start, result[i + 1].end)
                        new_result.append(merged)
                        i += 2  # Skip next segment
                        changed = True
                        continue
                elif i == len(result) - 1:
                    # Last segment - merge with previous
                    if new_result:
                        prev = new_result.pop()
                        merged = Segment(prev.start, current.end)
                        new_result.append(merged)
                        changed = True
                        i += 1
                        continue
                else:
                    # Middle segment - merge with smaller neighbor
                    prev_combined = current.start - new_result[-1].start if new_result else float('inf')
                    next_combined = result[i + 1].end - current.start
                    
                    if prev_combined <= next_combined and new_result:
                        # Merge with previous
                        prev = new_result.pop()
                        merged = Segment(prev.start, current.end)
                        new_result.append(merged)
                        changed = True
                    else:
                        # Merge with next
                        merged = Segment(current.start, result[i + 1].end)
                        new_result.append(merged)
                        i += 1  # Skip next segment
                        changed = True
                    i += 1
                    continue
            
            new_result.append(current)
            i += 1
        
        result = new_result
    
    return result


def split_long_segments(
    segments: List[Segment],
    max_duration: float = None
) -> List[Segment]:
    """
    Split segments longer than max_duration into smaller chunks.
    
    Strategy:
    - Split into roughly equal parts that are each <= max_duration
    
    Args:
        segments: List of segments to process
        max_duration: Maximum segment duration (uses config default if not provided)
        
    Returns:
        List of segments with none exceeding max_duration
    """
    if max_duration is None:
        max_duration = settings.max_clip_seconds
    
    result = []
    
    for seg in segments:
        if seg.duration <= max_duration:
            result.append(seg)
        else:
            # Calculate number of parts needed
            num_parts = int((seg.duration + max_duration - 0.01) // max_duration)
            part_duration = seg.duration / num_parts
            
            for i in range(num_parts):
                start = seg.start + (i * part_duration)
                end = seg.start + ((i + 1) * part_duration)
                # Ensure last segment goes exactly to the end
                if i == num_parts - 1:
                    end = seg.end
                result.append(Segment(start, end))
    
    return result


def post_process_segments(
    segments: List[Segment],
    min_duration: float = None,
    max_duration: float = None,
    target_max_clips: int = None
) -> List[Segment]:
    """
    Post-process segments: merge short ones, split long ones.
    
    This is the main entry point for segment post-processing.
    
    Args:
        segments: Raw segments from scene detection
        min_duration: Minimum segment duration
        max_duration: Maximum segment duration
        target_max_clips: Soft limit on number of clips
        
    Returns:
        Processed list of segments
    """
    if min_duration is None:
        min_duration = settings.min_clip_seconds
    if max_duration is None:
        max_duration = settings.max_clip_seconds
    if target_max_clips is None:
        target_max_clips = settings.target_max_clips
    
    if not segments:
        return []
    
    # First pass: split long segments
    result = split_long_segments(segments, max_duration)
    
    # Second pass: merge short segments
    result = merge_short_segments(result, min_duration)
    
    # If we have way too many clips, be more aggressive with merging
    if len(result) > target_max_clips:
        # Gradually increase min duration until we're under the limit
        adjusted_min = min_duration
        while len(result) > target_max_clips and adjusted_min < max_duration * 0.8:
            adjusted_min *= 1.2
            result = merge_short_segments(result, adjusted_min)
    
    # Final pass: ensure no segment exceeds max
    result = split_long_segments(result, max_duration)
    
    return result


def generate_clips_from_video(
    scene_timestamps: List[float],
    video_duration: float,
    min_duration: float = None,
    max_duration: float = None
) -> List[Segment]:
    """
    Main function to generate clips from scene detection results.
    
    Args:
        scene_timestamps: Timestamps where scenes change
        video_duration: Total video duration
        min_duration: Minimum clip duration
        max_duration: Maximum clip duration
        
    Returns:
        List of processed segments ready for clip creation
    """
    # Create initial segments
    segments = create_segments_from_scenes(scene_timestamps, video_duration)
    
    # Post-process
    return post_process_segments(segments, min_duration, max_duration)

