"""V2 Pipeline Configuration."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class V2PipelineConfig:
    """Configuration for the V2 highlight-aware pipeline."""
    
    # Feature extraction
    step_sec: float = 0.5  # Time step for feature sampling
    audio_sample_rate: int = 16000  # Sample rate for audio extraction
    motion_fps: int = 4  # Frames per second for motion analysis
    motion_width: int = 160  # Downscaled frame width for motion
    
    # Clip duration constraints
    min_clip_seconds: float = 5.0
    max_clip_seconds: float = 60.0
    
    # Window selection ranges (relative to anchor)
    pre_max: float = 14.0  # Max lookback for start boundary
    pre_min: float = 2.0   # Min lookback for start boundary
    post_max: float = 28.0  # Max lookahead for end boundary
    post_min: float = 2.0   # Min lookahead for end boundary
    fallback_pre: float = 8.0  # Fallback offset if no boundary found
    fallback_post: float = 12.0  # Fallback offset if no boundary found
    
    # Anchor detection
    anchor_suppression_window_sec: float = 4.0
    anchor_excitement_threshold: float = 0.3  # Min z-score for anchor
    max_anchors_per_minute: float = 8.0  # Adaptive limit
    
    # Boundary scoring weights
    boundary_w_scene: float = 0.45
    boundary_w_audio_dip: float = 0.25
    boundary_w_fade: float = 0.15
    boundary_w_motion_valley: float = 0.15
    boundary_min_spacing_sec: float = 1.5
    boundary_candidate_threshold: float = 0.1  # Min score to be candidate
    
    # Post-filtering
    target_clip_count_soft: int = 200
    overlap_iou_threshold: float = 0.35
    boring_threshold: float = 0.15  # Max avg excitement for "boring"
    boring_duration_ratio: float = 0.7  # % of clip that must be low-activity
    
    # Quality scoring weights
    quality_w_excitement: float = 0.4
    quality_w_dead_time_penalty: float = 0.2
    quality_w_boundary_quality: float = 0.2
    quality_w_narrative: float = 0.2
    
    # Scene detection
    scene_threshold: float = 0.3
    
    # Debug
    write_debug_json: bool = True
    write_debug_plot: bool = False  # Optional timeline plot
    
    # Caching
    cache_version: str = "v2.0.0"  # Bump to invalidate cache
    
    def to_dict(self) -> dict:
        """Convert config to dictionary for serialization."""
        return {
            "step_sec": self.step_sec,
            "audio_sample_rate": self.audio_sample_rate,
            "motion_fps": self.motion_fps,
            "motion_width": self.motion_width,
            "min_clip_seconds": self.min_clip_seconds,
            "max_clip_seconds": self.max_clip_seconds,
            "pre_max": self.pre_max,
            "pre_min": self.pre_min,
            "post_max": self.post_max,
            "post_min": self.post_min,
            "fallback_pre": self.fallback_pre,
            "fallback_post": self.fallback_post,
            "anchor_suppression_window_sec": self.anchor_suppression_window_sec,
            "anchor_excitement_threshold": self.anchor_excitement_threshold,
            "max_anchors_per_minute": self.max_anchors_per_minute,
            "boundary_w_scene": self.boundary_w_scene,
            "boundary_w_audio_dip": self.boundary_w_audio_dip,
            "boundary_w_fade": self.boundary_w_fade,
            "boundary_w_motion_valley": self.boundary_w_motion_valley,
            "boundary_min_spacing_sec": self.boundary_min_spacing_sec,
            "target_clip_count_soft": self.target_clip_count_soft,
            "overlap_iou_threshold": self.overlap_iou_threshold,
            "scene_threshold": self.scene_threshold,
            "cache_version": self.cache_version,
        }


# Default configuration instance
DEFAULT_V2_CONFIG = V2PipelineConfig()

