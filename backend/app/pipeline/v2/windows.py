"""Window selection for V2 pipeline.

Selects clip start/end times by snapping anchors to the best nearby boundaries.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import numpy as np

from .config import V2PipelineConfig
from .features import ExtractedFeatures
from .anchors import Anchor, get_excitement_integral
from .boundaries import BoundaryCandidate, get_best_boundary_in_range

logger = logging.getLogger(__name__)


@dataclass
class ClipWindow:
    """A selected clip window with quality metrics."""
    start_sec: float
    end_sec: float
    anchor_time_sec: float
    anchor_score: float
    
    # Quality score components
    quality_score: float
    excitement_score: float
    dead_time_penalty: float
    boundary_quality: float
    narrative_score: float
    
    # Selection metadata
    start_boundary_score: float
    end_boundary_score: float
    start_reason: str  # How start was selected
    end_reason: str    # How end was selected
    
    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec
    
    def to_dict(self) -> dict:
        return {
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "duration": self.duration,
            "anchor_time_sec": self.anchor_time_sec,
            "anchor_score": self.anchor_score,
            "quality_score": self.quality_score,
            "excitement_score": self.excitement_score,
            "dead_time_penalty": self.dead_time_penalty,
            "boundary_quality": self.boundary_quality,
            "narrative_score": self.narrative_score,
            "start_boundary_score": self.start_boundary_score,
            "end_boundary_score": self.end_boundary_score,
            "start_reason": self.start_reason,
            "end_reason": self.end_reason,
        }


def select_start_boundary(
    anchor_time: float,
    boundaries: List[BoundaryCandidate],
    config: V2PipelineConfig,
    video_duration: float,
) -> tuple:
    """
    Select clip start time by finding best boundary before anchor.
    
    Returns (start_time, boundary_score, reason).
    """
    search_start = max(0, anchor_time - config.pre_max)
    search_end = max(0, anchor_time - config.pre_min)
    
    if search_start >= search_end:
        # Not enough room to search, use fallback
        start = max(0, anchor_time - config.fallback_pre)
        return start, 0.0, "fallback_offset"
    
    best = get_best_boundary_in_range(boundaries, search_start, search_end)
    
    if best is not None:
        return best.time_sec, best.score, "boundary_snap"
    
    # Fallback
    start = max(0, anchor_time - config.fallback_pre)
    return start, 0.0, "fallback_offset"


def select_end_boundary(
    anchor_time: float,
    start_time: float,
    boundaries: List[BoundaryCandidate],
    features: ExtractedFeatures,
    config: V2PipelineConfig,
    video_duration: float,
) -> tuple:
    """
    Select clip end time by finding best boundary after anchor.
    
    Returns (end_time, boundary_score, reason).
    """
    # Ensure we don't exceed max duration
    max_end = min(video_duration, start_time + config.max_clip_seconds)
    
    search_start = anchor_time + config.post_min
    search_end = min(max_end, anchor_time + config.post_max)
    
    if search_start >= search_end:
        # Not enough room to search
        end = min(video_duration, anchor_time + config.fallback_post)
        end = min(end, start_time + config.max_clip_seconds)
        return end, 0.0, "fallback_offset"
    
    # Get candidates
    candidates = [b for b in boundaries if search_start <= b.time_sec <= search_end]
    
    if not candidates:
        end = min(video_duration, anchor_time + config.fallback_post)
        end = min(end, start_time + config.max_clip_seconds)
        return end, 0.0, "fallback_offset"
    
    # Prefer ends shortly after excitement peaks
    # Score = boundary_score + small bonus for being after high excitement
    def end_preference_score(b: BoundaryCandidate) -> float:
        base_score = b.score
        
        # Look back a bit from the boundary for excitement
        lookback_start = max(anchor_time, b.time_sec - 3.0)
        excitement = get_excitement_integral(features, lookback_start, b.time_sec)
        excitement_bonus = min(0.2, excitement * 0.1)  # Small bonus
        
        return base_score + excitement_bonus
    
    best = max(candidates, key=end_preference_score)
    return best.time_sec, best.score, "boundary_snap"


def compute_quality_score(
    start_sec: float,
    end_sec: float,
    anchor_time_sec: float,
    anchor_score: float,
    features: ExtractedFeatures,
    start_boundary_score: float,
    end_boundary_score: float,
    config: V2PipelineConfig,
) -> tuple:
    """
    Compute quality score for a clip window.
    
    Returns (total_score, excitement_score, dead_time_penalty, boundary_quality, narrative_score).
    """
    duration = end_sec - start_sec
    
    # Excitement integral normalized by duration
    excitement = get_excitement_integral(features, start_sec, end_sec)
    excitement_score = excitement / max(1, duration)
    
    # Dead time penalty (low activity portions)
    start_idx = int(start_sec / features.step_sec)
    end_idx = int(end_sec / features.step_sec)
    start_idx = max(0, start_idx)
    end_idx = min(len(features.excitement), end_idx + 1)
    
    if end_idx > start_idx:
        window_excitement = features.excitement[start_idx:end_idx]
        low_activity_ratio = np.sum(window_excitement < 0.1) / len(window_excitement)
        dead_time_penalty = low_activity_ratio * config.quality_w_dead_time_penalty
    else:
        dead_time_penalty = 0.0
    
    # Boundary quality
    boundary_quality = (start_boundary_score + end_boundary_score) / 2
    
    # Narrative score (anchor shouldn't be too close to start or end)
    anchor_offset_from_start = anchor_time_sec - start_sec
    anchor_offset_from_end = end_sec - anchor_time_sec
    min_offset = min(anchor_offset_from_start, anchor_offset_from_end)
    
    # Ideal: anchor is at least 20% from either edge
    ideal_offset = duration * 0.2
    if min_offset < ideal_offset:
        narrative_score = min_offset / ideal_offset
    else:
        narrative_score = 1.0
    
    # Combined score
    total = (
        config.quality_w_excitement * excitement_score +
        config.quality_w_boundary_quality * boundary_quality +
        config.quality_w_narrative * narrative_score -
        dead_time_penalty
    )
    
    # Boost by anchor score
    total = total * (0.5 + 0.5 * min(1.0, anchor_score))
    
    return total, excitement_score, dead_time_penalty, boundary_quality, narrative_score


def select_windows(
    anchors: List[Anchor],
    boundaries: List[BoundaryCandidate],
    features: ExtractedFeatures,
    config: V2PipelineConfig,
) -> List[ClipWindow]:
    """
    Select clip windows for all anchors.
    """
    logger.info(f"Selecting windows for {len(anchors)} anchors...")
    
    duration = features.duration
    windows = []
    
    for anchor in anchors:
        # Select start boundary
        start, start_score, start_reason = select_start_boundary(
            anchor.time_sec, boundaries, config, duration
        )
        
        # Select end boundary (considering start)
        end, end_score, end_reason = select_end_boundary(
            anchor.time_sec, start, boundaries, features, config, duration
        )
        
        # Enforce constraints
        clip_duration = end - start
        
        # Too short - expand
        if clip_duration < config.min_clip_seconds:
            needed = config.min_clip_seconds - clip_duration
            # Try expanding end first
            end = min(duration, end + needed / 2)
            start = max(0, start - needed / 2)
            clip_duration = end - start
            
            if clip_duration < config.min_clip_seconds:
                # Force minimum
                if end < duration:
                    end = min(duration, start + config.min_clip_seconds)
                else:
                    start = max(0, end - config.min_clip_seconds)
        
        # Too long - shrink
        if clip_duration > config.max_clip_seconds:
            # Prefer cutting from end
            end = start + config.max_clip_seconds
            end_reason = "hard_cut_max_duration"
        
        # Final validation
        if end <= start:
            logger.warning(f"Invalid window for anchor at {anchor.time_sec}s, skipping")
            continue
        
        # Compute quality
        quality, excitement, dead_penalty, boundary_qual, narrative = compute_quality_score(
            start, end, anchor.time_sec, anchor.score,
            features, start_score, end_score, config
        )
        
        windows.append(ClipWindow(
            start_sec=start,
            end_sec=end,
            anchor_time_sec=anchor.time_sec,
            anchor_score=anchor.score,
            quality_score=quality,
            excitement_score=excitement,
            dead_time_penalty=dead_penalty,
            boundary_quality=boundary_qual,
            narrative_score=narrative,
            start_boundary_score=start_score,
            end_boundary_score=end_score,
            start_reason=start_reason,
            end_reason=end_reason,
        ))
    
    logger.info(f"Selected {len(windows)} clip windows")
    return windows

