"""Boundary candidate scoring for V2 pipeline.

Identifies and scores natural clip boundary points - good places to start/end clips.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .config import V2PipelineConfig
from .features import ExtractedFeatures

logger = logging.getLogger(__name__)


@dataclass
class BoundaryCandidate:
    """A potential clip boundary point."""
    time_sec: float
    score: float  # Overall boundary quality score
    scene_strength: float  # Scene cut proximity
    audio_dip_strength: float  # Audio valley strength
    fade_strength: float  # Fade/black transition proximity
    motion_valley_strength: float  # Motion valley strength
    
    def to_dict(self) -> dict:
        return {
            "time_sec": self.time_sec,
            "score": self.score,
            "scene_strength": self.scene_strength,
            "audio_dip_strength": self.audio_dip_strength,
            "fade_strength": self.fade_strength,
            "motion_valley_strength": self.motion_valley_strength,
        }


def find_valleys(
    arr: np.ndarray,
    times: np.ndarray,
    step_sec: float,
    min_spacing_sec: float = 1.0,
) -> List[tuple]:
    """Find local minima (valleys) in array."""
    min_spacing_samples = max(1, int(min_spacing_sec / step_sec))
    
    valleys = []
    for i in range(1, len(arr) - 1):
        # Simple local minimum check
        if arr[i] < arr[i - 1] and arr[i] < arr[i + 1]:
            # Check wider window
            window_start = max(0, i - min_spacing_samples)
            window_end = min(len(arr), i + min_spacing_samples + 1)
            
            if arr[i] == np.min(arr[window_start:window_end]):
                # Convert to "valley strength" (negative z-score gives positive strength)
                strength = -arr[i] if arr[i] < 0 else 0
                valleys.append((times[i], strength, i))
    
    return valleys


def compute_scene_proximity_scores(
    times: np.ndarray,
    scene_cuts: List[float],
    decay_sec: float = 0.5,
) -> np.ndarray:
    """
    Compute how close each time point is to a scene cut.
    
    Returns array of scores where 1.0 = at scene cut, decaying to 0.
    """
    scores = np.zeros_like(times)
    
    for cut_time in scene_cuts:
        distances = np.abs(times - cut_time)
        proximity = np.exp(-distances / decay_sec)
        scores = np.maximum(scores, proximity)
    
    return scores


def compute_fade_proximity_scores(
    times: np.ndarray,
    fade_timestamps: List[float],
    decay_sec: float = 0.5,
) -> np.ndarray:
    """Compute proximity to fade/black transitions."""
    scores = np.zeros_like(times)
    
    for fade_time in fade_timestamps:
        distances = np.abs(times - fade_time)
        proximity = np.exp(-distances / decay_sec)
        scores = np.maximum(scores, proximity)
    
    return scores


def compute_boundary_scores(
    features: ExtractedFeatures,
    config: V2PipelineConfig,
) -> List[BoundaryCandidate]:
    """
    Compute boundary candidate scores for all time points.
    
    Combines multiple signals to identify natural clip boundaries.
    """
    logger.info("Computing boundary scores...")
    
    times = features.times
    step_sec = features.step_sec
    
    # Scene cut proximity
    scene_scores = compute_scene_proximity_scores(
        times, features.scene_cuts, decay_sec=0.5
    )
    
    # Fade proximity
    fade_scores = compute_fade_proximity_scores(
        times, features.fade_timestamps, decay_sec=0.5
    )
    
    # Audio valleys (quiet moments = good transitions)
    audio_valley_scores = np.zeros_like(times)
    audio_valleys = find_valleys(
        features.audio_rms_z, times, step_sec,
        min_spacing_sec=config.boundary_min_spacing_sec
    )
    for valley_time, strength, idx in audio_valleys:
        # Spread the valley score slightly
        for i, t in enumerate(times):
            if abs(t - valley_time) < 1.0:
                decay = np.exp(-abs(t - valley_time) / 0.3)
                audio_valley_scores[i] = max(audio_valley_scores[i], strength * decay)
    
    # Motion valleys
    motion_valley_scores = np.zeros_like(times)
    motion_valleys = find_valleys(
        features.motion_score_z, times, step_sec,
        min_spacing_sec=config.boundary_min_spacing_sec
    )
    for valley_time, strength, idx in motion_valleys:
        for i, t in enumerate(times):
            if abs(t - valley_time) < 1.0:
                decay = np.exp(-abs(t - valley_time) / 0.3)
                motion_valley_scores[i] = max(motion_valley_scores[i], strength * decay)
    
    # Normalize all component scores to 0-1 range
    def normalize(arr):
        max_val = np.max(arr)
        if max_val > 0:
            return arr / max_val
        return arr
    
    scene_scores = normalize(scene_scores)
    fade_scores = normalize(fade_scores)
    audio_valley_scores = normalize(audio_valley_scores)
    motion_valley_scores = normalize(motion_valley_scores)
    
    # Compute weighted combination
    combined_scores = (
        config.boundary_w_scene * scene_scores +
        config.boundary_w_audio_dip * audio_valley_scores +
        config.boundary_w_fade * fade_scores +
        config.boundary_w_motion_valley * motion_valley_scores
    )
    
    # Apply spacing penalty for clustered candidates
    spacing_penalty = np.zeros_like(times)
    for i in range(len(times)):
        # Penalize if high-scoring neighbors are too close
        window_start = max(0, i - int(config.boundary_min_spacing_sec / step_sec))
        window_end = min(len(times), i + int(config.boundary_min_spacing_sec / step_sec) + 1)
        
        for j in range(window_start, window_end):
            if j != i and combined_scores[j] > combined_scores[i]:
                dist = abs(times[i] - times[j])
                if dist < config.boundary_min_spacing_sec:
                    spacing_penalty[i] += 0.3 * (1 - dist / config.boundary_min_spacing_sec)
    
    final_scores = combined_scores - spacing_penalty
    final_scores = np.maximum(0, final_scores)
    
    # Create boundary candidates for all points above threshold
    candidates = []
    for i, t in enumerate(times):
        if final_scores[i] >= config.boundary_candidate_threshold:
            candidates.append(BoundaryCandidate(
                time_sec=t,
                score=float(final_scores[i]),
                scene_strength=float(scene_scores[i]),
                audio_dip_strength=float(audio_valley_scores[i]),
                fade_strength=float(fade_scores[i]),
                motion_valley_strength=float(motion_valley_scores[i]),
            ))
    
    logger.info(f"Found {len(candidates)} boundary candidates")
    return candidates


def get_boundaries_in_range(
    boundaries: List[BoundaryCandidate],
    start_sec: float,
    end_sec: float,
) -> List[BoundaryCandidate]:
    """Get boundary candidates within a time range."""
    return [b for b in boundaries if start_sec <= b.time_sec <= end_sec]


def get_best_boundary_in_range(
    boundaries: List[BoundaryCandidate],
    start_sec: float,
    end_sec: float,
) -> Optional[BoundaryCandidate]:
    """Get the highest-scoring boundary in a time range."""
    in_range = get_boundaries_in_range(boundaries, start_sec, end_sec)
    if not in_range:
        return None
    return max(in_range, key=lambda b: b.score)

