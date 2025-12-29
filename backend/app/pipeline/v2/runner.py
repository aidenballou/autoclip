"""V2 Pipeline Runner.

Orchestrates the full highlight-aware clip generation pipeline.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Callable, Awaitable

from .config import V2PipelineConfig, DEFAULT_V2_CONFIG
from .features import (
    ExtractedFeatures,
    extract_features,
    load_cached_features,
    save_features_cache,
)
from .anchors import detect_anchors, Anchor
from .boundaries import compute_boundary_scores, BoundaryCandidate
from .windows import select_windows, ClipWindow
from .post_filters import apply_post_filters
from .debug_artifacts import write_debug_json, write_debug_plot

logger = logging.getLogger(__name__)


@dataclass
class V2PipelineResult:
    """Result from V2 pipeline execution."""
    clips: List[ClipWindow]
    anchors: List[Anchor]
    boundaries: List[BoundaryCandidate]
    features: ExtractedFeatures
    filter_report: dict
    config: V2PipelineConfig
    
    def to_clip_list(self) -> List[dict]:
        """Convert to list of clip dictionaries for API response."""
        return [
            {
                "start_time": clip.start_sec,
                "end_time": clip.end_sec,
                "duration": clip.duration,
                "quality_score": clip.quality_score,
                "anchor_time_sec": clip.anchor_time_sec,
                "generation_version": "v2",
            }
            for clip in self.clips
        ]


async def run_v2_pipeline(
    video_path: str | Path,
    duration: float,
    project_dir: Path,
    config: Optional[V2PipelineConfig] = None,
    progress_callback: Optional[Callable[[float, str], Awaitable[None]]] = None,
) -> V2PipelineResult:
    """
    Run the full V2 highlight-aware pipeline.
    
    Args:
        video_path: Path to video file
        duration: Video duration in seconds
        project_dir: Project directory for caching and debug output
        config: Pipeline configuration (uses defaults if not provided)
        progress_callback: Optional async callback for progress updates
        
    Returns:
        V2PipelineResult with clips and metadata
    """
    video_path = Path(video_path)
    config = config or DEFAULT_V2_CONFIG
    
    logger.info(f"Running V2 pipeline on {video_path}")
    
    # Setup directories
    features_dir = project_dir / "features"
    debug_dir = project_dir / "debug"
    features_cache_path = features_dir / "features_v2.json"
    
    # Progress helper
    async def report_progress(pct: float, msg: str):
        if progress_callback:
            await progress_callback(pct, msg)
        logger.info(f"[{pct:.0f}%] {msg}")
    
    # Stage 1: Feature extraction (with caching)
    await report_progress(0, "Starting V2 pipeline...")
    
    features = load_cached_features(features_cache_path, config)
    
    if features is None:
        await report_progress(5, "Extracting features...")
        
        async def feature_progress(pct, msg):
            # Map feature extraction progress to 5-40%
            mapped_pct = 5 + (pct / 100) * 35
            await report_progress(mapped_pct, msg)
        
        features = await extract_features(
            video_path, duration, config, feature_progress
        )
        
        save_features_cache(features, features_cache_path)
        await report_progress(40, "Features cached")
    else:
        await report_progress(40, "Loaded cached features")
    
    # Stage 2: Anchor detection
    await report_progress(45, "Detecting anchors...")
    anchors = detect_anchors(features, config)
    await report_progress(55, f"Found {len(anchors)} anchors")
    
    # Stage 3: Boundary scoring
    await report_progress(60, "Computing boundaries...")
    boundaries = compute_boundary_scores(features, config)
    await report_progress(70, f"Found {len(boundaries)} boundary candidates")
    
    # Stage 4: Window selection
    await report_progress(75, "Selecting clip windows...")
    windows = select_windows(anchors, boundaries, features, config)
    await report_progress(80, f"Selected {len(windows)} candidate windows")
    
    # Stage 5: Post-filtering
    await report_progress(82, "Applying post-filters...")
    final_clips, filter_report = apply_post_filters(
        windows, features, str(video_path), config
    )
    await report_progress(90, f"Final clip count: {len(final_clips)}")
    
    # Stage 6: Write debug artifacts
    if config.write_debug_json:
        debug_json_path = debug_dir / "segmentation_v2_debug.json"
        write_debug_json(
            debug_json_path, config, features, anchors,
            boundaries, windows, filter_report, final_clips
        )
    
    if config.write_debug_plot:
        debug_plot_path = debug_dir / "segmentation_v2_plot.png"
        write_debug_plot(debug_plot_path, features, anchors, final_clips)
    
    await report_progress(95, "V2 pipeline complete")
    
    return V2PipelineResult(
        clips=final_clips,
        anchors=anchors,
        boundaries=boundaries,
        features=features,
        filter_report=filter_report,
        config=config,
    )


async def run_v2_pipeline_simple(
    video_path: str | Path,
    duration: float,
    output_dir: Optional[Path] = None,
) -> List[dict]:
    """
    Simplified interface for running V2 pipeline.
    
    Returns list of clip dictionaries.
    """
    video_path = Path(video_path)
    project_dir = output_dir or video_path.parent / ".autoclip_v2"
    
    result = await run_v2_pipeline(
        video_path, duration, project_dir
    )
    
    return result.to_clip_list()

