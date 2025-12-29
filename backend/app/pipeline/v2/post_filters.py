"""Post-processing filters for V2 pipeline.

Handles overlap resolution, deduplication, and boring clip filtering.
"""
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional
import hashlib

import numpy as np

from .config import V2PipelineConfig
from .features import ExtractedFeatures
from .windows import ClipWindow

logger = logging.getLogger(__name__)


@dataclass 
class FilterDecision:
    """Records why a clip was kept or dropped."""
    clip_index: int
    action: str  # "keep", "drop_overlap", "drop_boring", "drop_duplicate", "drop_quality"
    reason: str
    related_clip_index: Optional[int] = None  # For overlap/duplicate decisions
    
    def to_dict(self) -> dict:
        return {
            "clip_index": self.clip_index,
            "action": self.action,
            "reason": self.reason,
            "related_clip_index": self.related_clip_index,
        }


def compute_iou(window1: ClipWindow, window2: ClipWindow) -> float:
    """Compute Intersection over Union for two time windows."""
    start = max(window1.start_sec, window2.start_sec)
    end = min(window1.end_sec, window2.end_sec)
    
    intersection = max(0, end - start)
    union = (window1.duration + window2.duration) - intersection
    
    if union <= 0:
        return 0.0
    
    return intersection / union


def resolve_overlaps(
    windows: List[ClipWindow],
    config: V2PipelineConfig,
) -> Tuple[List[ClipWindow], List[FilterDecision]]:
    """
    Resolve overlapping clips by keeping higher-quality ones.
    
    Uses greedy selection: sort by quality, keep if not too much overlap with kept clips.
    """
    logger.info("Resolving overlaps...")
    
    if not windows:
        return [], []
    
    # Sort by quality descending
    sorted_windows = sorted(windows, key=lambda w: w.quality_score, reverse=True)
    
    kept = []
    decisions = []
    
    for i, window in enumerate(sorted_windows):
        # Find original index
        original_idx = windows.index(window)
        
        # Check overlap with all kept clips
        has_high_overlap = False
        overlap_with = None
        
        for kept_window in kept:
            iou = compute_iou(window, kept_window)
            if iou > config.overlap_iou_threshold:
                has_high_overlap = True
                overlap_with = windows.index(kept_window)
                break
        
        if has_high_overlap:
            decisions.append(FilterDecision(
                clip_index=original_idx,
                action="drop_overlap",
                reason=f"IoU {iou:.2f} > threshold {config.overlap_iou_threshold}",
                related_clip_index=overlap_with,
            ))
        else:
            kept.append(window)
            decisions.append(FilterDecision(
                clip_index=original_idx,
                action="keep",
                reason="Passed overlap check",
            ))
    
    logger.info(f"Overlap resolution: {len(windows)} -> {len(kept)} clips")
    return kept, decisions


def filter_boring(
    windows: List[ClipWindow],
    features: ExtractedFeatures,
    config: V2PipelineConfig,
) -> Tuple[List[ClipWindow], List[FilterDecision]]:
    """
    Remove clips that are mostly low-activity.
    """
    logger.info("Filtering boring clips...")
    
    kept = []
    decisions = []
    
    for i, window in enumerate(windows):
        # Get excitement in window
        start_idx = int(window.start_sec / features.step_sec)
        end_idx = int(window.end_sec / features.step_sec)
        start_idx = max(0, start_idx)
        end_idx = min(len(features.excitement), end_idx + 1)
        
        if end_idx <= start_idx:
            kept.append(window)
            decisions.append(FilterDecision(
                clip_index=i, action="keep", reason="No excitement data"
            ))
            continue
        
        window_excitement = features.excitement[start_idx:end_idx]
        avg_excitement = np.mean(window_excitement)
        low_ratio = np.sum(window_excitement < config.boring_threshold) / len(window_excitement)
        
        # Don't drop if anchor score is high (might be important despite low excitement)
        is_boring = (
            avg_excitement < config.boring_threshold and 
            low_ratio > config.boring_duration_ratio and
            window.anchor_score < 0.5
        )
        
        if is_boring:
            decisions.append(FilterDecision(
                clip_index=i,
                action="drop_boring",
                reason=f"Avg excitement {avg_excitement:.2f}, low ratio {low_ratio:.2f}",
            ))
        else:
            kept.append(window)
            decisions.append(FilterDecision(
                clip_index=i, action="keep", reason="Passed boring filter"
            ))
    
    logger.info(f"Boring filter: {len(windows)} -> {len(kept)} clips")
    return kept, decisions


def filter_by_quality_target(
    windows: List[ClipWindow],
    config: V2PipelineConfig,
) -> Tuple[List[ClipWindow], List[FilterDecision]]:
    """
    Reduce clip count to target by raising quality threshold.
    """
    if len(windows) <= config.target_clip_count_soft:
        return windows, [FilterDecision(i, "keep", "Under target count") for i in range(len(windows))]
    
    logger.info(f"Reducing {len(windows)} clips to target {config.target_clip_count_soft}...")
    
    # Sort by quality
    sorted_windows = sorted(windows, key=lambda w: w.quality_score, reverse=True)
    
    # Keep top N
    kept = sorted_windows[:config.target_clip_count_soft]
    dropped = sorted_windows[config.target_clip_count_soft:]
    
    decisions = []
    for window in windows:
        original_idx = windows.index(window)
        if window in kept:
            decisions.append(FilterDecision(
                clip_index=original_idx, action="keep", reason="Above quality cutoff"
            ))
        else:
            decisions.append(FilterDecision(
                clip_index=original_idx, action="drop_quality",
                reason=f"Below quality cutoff (score: {window.quality_score:.3f})"
            ))
    
    logger.info(f"Quality filter: {len(windows)} -> {len(kept)} clips")
    return kept, decisions


def simple_frame_hash(
    video_path: str,
    time_sec: float,
    width: int = 16,
    height: int = 16,
) -> Optional[str]:
    """
    Compute a simple perceptual hash for a frame.
    
    This is a simplified implementation - extracts a small grayscale frame
    and computes average-based hash.
    """
    import asyncio
    import subprocess
    
    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(time_sec),
            "-i", video_path,
            "-vframes", "1",
            "-vf", f"scale={width}:{height},format=gray",
            "-f", "rawvideo",
            "-pix_fmt", "gray",
            "-"
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        
        if result.returncode != 0 or len(result.stdout) != width * height:
            return None
        
        pixels = np.frombuffer(result.stdout, dtype=np.uint8)
        avg = np.mean(pixels)
        
        # Create hash from average comparison
        bits = ''.join('1' if p > avg else '0' for p in pixels)
        return hashlib.md5(bits.encode()).hexdigest()[:16]
        
    except Exception:
        return None


def deduplicate_clips(
    windows: List[ClipWindow],
    video_path: str,
    config: V2PipelineConfig,
) -> Tuple[List[ClipWindow], List[FilterDecision]]:
    """
    Remove near-duplicate clips based on visual similarity.
    
    For efficiency, only compares clips that are close in time.
    """
    logger.info("Deduplicating clips...")
    
    if len(windows) < 2:
        return windows, [FilterDecision(0, "keep", "Single clip") for _ in windows]
    
    # Sort by start time for comparison
    windows_with_idx = [(i, w) for i, w in enumerate(windows)]
    windows_with_idx.sort(key=lambda x: x[1].start_sec)
    
    # Compute hashes for middle frame of each clip
    hashes = {}
    for orig_idx, window in windows_with_idx:
        mid_time = (window.start_sec + window.end_sec) / 2
        h = simple_frame_hash(video_path, mid_time)
        if h:
            hashes[orig_idx] = h
    
    kept_indices = set()
    dropped_indices = {}  # Maps dropped -> kept
    
    for orig_idx, window in windows_with_idx:
        if orig_idx in dropped_indices:
            continue
        
        is_dup = False
        dup_of = None
        
        # Only compare with clips within 30 seconds
        for kept_idx in kept_indices:
            kept_window = windows[kept_idx]
            time_diff = abs(window.start_sec - kept_window.start_sec)
            
            if time_diff > 30:
                continue
            
            # Compare hashes if available
            if orig_idx in hashes and kept_idx in hashes:
                if hashes[orig_idx] == hashes[kept_idx]:
                    # Same hash = likely duplicate
                    if window.quality_score < kept_window.quality_score:
                        is_dup = True
                        dup_of = kept_idx
                        break
        
        if is_dup:
            dropped_indices[orig_idx] = dup_of
        else:
            kept_indices.add(orig_idx)
    
    kept = [windows[i] for i in sorted(kept_indices)]
    decisions = []
    
    for i in range(len(windows)):
        if i in kept_indices:
            decisions.append(FilterDecision(i, "keep", "Unique clip"))
        elif i in dropped_indices:
            decisions.append(FilterDecision(
                i, "drop_duplicate", 
                f"Duplicate of clip at {windows[dropped_indices[i]].start_sec:.1f}s",
                related_clip_index=dropped_indices[i]
            ))
    
    logger.info(f"Deduplication: {len(windows)} -> {len(kept)} clips")
    return kept, decisions


def apply_post_filters(
    windows: List[ClipWindow],
    features: ExtractedFeatures,
    video_path: str,
    config: V2PipelineConfig,
) -> Tuple[List[ClipWindow], dict]:
    """
    Apply all post-processing filters.
    
    Returns (filtered_windows, filter_report).
    """
    all_decisions = {
        "overlap": [],
        "boring": [],
        "duplicate": [],
        "quality": [],
    }
    
    # 1. Resolve overlaps
    windows, decisions = resolve_overlaps(windows, config)
    all_decisions["overlap"] = [d.to_dict() for d in decisions]
    
    # 2. Filter boring clips
    windows, decisions = filter_boring(windows, features, config)
    all_decisions["boring"] = [d.to_dict() for d in decisions]
    
    # 3. Deduplicate
    windows, decisions = deduplicate_clips(windows, video_path, config)
    all_decisions["duplicate"] = [d.to_dict() for d in decisions]
    
    # 4. Reduce to target count
    windows, decisions = filter_by_quality_target(windows, config)
    all_decisions["quality"] = [d.to_dict() for d in decisions]
    
    # Re-sort by time
    windows.sort(key=lambda w: w.start_sec)
    
    return windows, all_decisions

