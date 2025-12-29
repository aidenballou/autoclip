"""Anchor detection for V2 pipeline.

Anchors represent likely highlight moments - the "center" of interesting events.
These become the reference points around which clip windows are constructed.
"""
import logging
from dataclasses import dataclass
from typing import List

import numpy as np

from .config import V2PipelineConfig
from .features import ExtractedFeatures

logger = logging.getLogger(__name__)


@dataclass
class Anchor:
    """A detected highlight anchor point."""
    time_sec: float
    score: float  # Excitement/importance score
    audio_z: float  # Audio z-score at anchor
    motion_z: float  # Motion z-score at anchor
    reason: str  # Why this was selected as anchor
    
    def to_dict(self) -> dict:
        return {
            "time_sec": self.time_sec,
            "score": self.score,
            "audio_z": self.audio_z,
            "motion_z": self.motion_z,
            "reason": self.reason,
        }


def find_local_maxima(
    arr: np.ndarray,
    times: np.ndarray,
    min_distance_sec: float,
    step_sec: float,
    threshold: float = 0.0,
) -> List[tuple]:
    """
    Find local maxima in array with minimum spacing.
    
    Returns list of (time, value) tuples.
    """
    min_distance_samples = int(min_distance_sec / step_sec)
    
    maxima = []
    for i in range(1, len(arr) - 1):
        if arr[i] <= threshold:
            continue
        
        # Check if local maximum
        window_start = max(0, i - min_distance_samples)
        window_end = min(len(arr), i + min_distance_samples + 1)
        
        if arr[i] == np.max(arr[window_start:window_end]):
            maxima.append((times[i], arr[i], i))
    
    # Non-max suppression
    maxima.sort(key=lambda x: x[1], reverse=True)
    
    selected = []
    used_times = set()
    
    for time, value, idx in maxima:
        # Check if too close to already selected
        too_close = False
        for used_time in used_times:
            if abs(time - used_time) < min_distance_sec:
                too_close = True
                break
        
        if not too_close:
            selected.append((time, value, idx))
            used_times.add(time)
    
    return selected


def detect_anchors(
    features: ExtractedFeatures,
    config: V2PipelineConfig,
) -> List[Anchor]:
    """
    Detect highlight anchor points from features.
    
    Uses a combination of:
    - Audio loudness peaks
    - Motion activity peaks
    - Combined excitement peaks
    """
    logger.info("Detecting anchor points...")
    
    times = features.times
    step_sec = features.step_sec
    duration = features.duration
    
    # Calculate adaptive max anchors based on video length
    max_anchors = int(duration / 60 * config.max_anchors_per_minute)
    max_anchors = max(10, min(max_anchors, config.target_clip_count_soft * 2))
    
    anchors = []
    
    # Method 1: Excitement peaks (primary)
    excitement_peaks = find_local_maxima(
        features.excitement,
        times,
        min_distance_sec=config.anchor_suppression_window_sec,
        step_sec=step_sec,
        threshold=config.anchor_excitement_threshold,
    )
    
    for time, value, idx in excitement_peaks:
        anchors.append(Anchor(
            time_sec=time,
            score=value,
            audio_z=float(features.audio_rms_z[idx]),
            motion_z=float(features.motion_score_z[idx]),
            reason="excitement_peak",
        ))
    
    # Method 2: Strong audio peaks (even if motion is low - commentary/reaction)
    audio_only_peaks = find_local_maxima(
        features.audio_rms_z,
        times,
        min_distance_sec=config.anchor_suppression_window_sec,
        step_sec=step_sec,
        threshold=1.5,  # High threshold for audio-only
    )
    
    existing_times = {a.time_sec for a in anchors}
    for time, value, idx in audio_only_peaks:
        # Skip if too close to existing anchor
        if any(abs(time - et) < config.anchor_suppression_window_sec for et in existing_times):
            continue
        
        anchors.append(Anchor(
            time_sec=time,
            score=value * 0.7,  # Slightly lower weight for audio-only
            audio_z=float(features.audio_rms_z[idx]),
            motion_z=float(features.motion_score_z[idx]),
            reason="audio_peak",
        ))
        existing_times.add(time)
    
    # Method 3: High motion with scene cut clusters (action sequences)
    if features.scene_cuts:
        # Find regions with clustered scene cuts
        cut_density = np.zeros_like(times)
        window_sec = 5.0
        
        for cut_time in features.scene_cuts:
            for i, t in enumerate(times):
                if abs(t - cut_time) < window_sec:
                    cut_density[i] += 1.0 / (1.0 + abs(t - cut_time))
        
        # Combine with motion
        action_score = features.motion_score_z * (1 + cut_density * 0.5)
        
        action_peaks = find_local_maxima(
            action_score,
            times,
            min_distance_sec=config.anchor_suppression_window_sec,
            step_sec=step_sec,
            threshold=1.0,
        )
        
        for time, value, idx in action_peaks:
            if any(abs(time - et) < config.anchor_suppression_window_sec for et in existing_times):
                continue
            
            anchors.append(Anchor(
                time_sec=time,
                score=value * 0.6,
                audio_z=float(features.audio_rms_z[idx]),
                motion_z=float(features.motion_score_z[idx]),
                reason="action_sequence",
            ))
            existing_times.add(time)
    
    # Sort by score and limit
    anchors.sort(key=lambda a: a.score, reverse=True)
    anchors = anchors[:max_anchors]
    
    # Re-sort by time for processing
    anchors.sort(key=lambda a: a.time_sec)
    
    logger.info(f"Detected {len(anchors)} anchor points")
    return anchors


def get_excitement_at_time(
    features: ExtractedFeatures,
    time_sec: float,
) -> float:
    """Get interpolated excitement value at a specific time."""
    idx = int(time_sec / features.step_sec)
    idx = max(0, min(idx, len(features.excitement) - 1))
    return float(features.excitement[idx])


def get_excitement_integral(
    features: ExtractedFeatures,
    start_sec: float,
    end_sec: float,
) -> float:
    """Compute integral of excitement over a time range."""
    start_idx = int(start_sec / features.step_sec)
    end_idx = int(end_sec / features.step_sec)
    
    start_idx = max(0, start_idx)
    end_idx = min(len(features.excitement), end_idx + 1)
    
    if start_idx >= end_idx:
        return 0.0
    
    return float(np.sum(features.excitement[start_idx:end_idx]) * features.step_sec)

