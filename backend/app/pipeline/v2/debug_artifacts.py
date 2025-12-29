"""Debug artifact generation for V2 pipeline.

Writes detailed JSON explaining all pipeline decisions.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Dict

from .config import V2PipelineConfig
from .features import ExtractedFeatures
from .anchors import Anchor
from .boundaries import BoundaryCandidate
from .windows import ClipWindow

logger = logging.getLogger(__name__)


def write_debug_json(
    output_path: Path,
    config: V2PipelineConfig,
    features: ExtractedFeatures,
    anchors: List[Anchor],
    boundaries: List[BoundaryCandidate],
    windows: List[ClipWindow],
    filter_report: dict,
    final_clips: List[ClipWindow],
):
    """
    Write comprehensive debug JSON file.
    """
    debug_data = {
        "generated_at": datetime.utcnow().isoformat(),
        "pipeline_version": "v2",
        
        # Configuration
        "config": config.to_dict(),
        
        # Feature extraction summary
        "features_summary": {
            "duration": features.duration,
            "step_sec": features.step_sec,
            "num_samples": len(features.times),
            "scene_cuts_count": len(features.scene_cuts),
            "fade_timestamps_count": len(features.fade_timestamps),
            "freeze_timestamps_count": len(features.freeze_timestamps),
            "audio_rms_stats": {
                "min": float(features.audio_rms.min()),
                "max": float(features.audio_rms.max()),
                "mean": float(features.audio_rms.mean()),
            },
            "motion_stats": {
                "min": float(features.motion_score.min()),
                "max": float(features.motion_score.max()),
                "mean": float(features.motion_score.mean()),
            },
        },
        
        # Scene cuts
        "scene_cuts": features.scene_cuts[:100],  # Limit for readability
        
        # Anchors
        "anchors": [a.to_dict() for a in anchors],
        
        # Top boundaries (limit for readability)
        "top_boundaries": [b.to_dict() for b in sorted(boundaries, key=lambda x: x.score, reverse=True)[:100]],
        
        # All candidate windows before filtering
        "candidate_windows": [w.to_dict() for w in windows],
        
        # Filter decisions
        "filter_report": filter_report,
        
        # Final clips
        "final_clips": [w.to_dict() for w in final_clips],
        
        # Statistics
        "statistics": {
            "total_anchors": len(anchors),
            "total_boundaries": len(boundaries),
            "candidate_windows": len(windows),
            "final_clips": len(final_clips),
            "avg_clip_duration": sum(c.duration for c in final_clips) / len(final_clips) if final_clips else 0,
            "avg_quality_score": sum(c.quality_score for c in final_clips) / len(final_clips) if final_clips else 0,
        }
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(debug_data, f, indent=2)
    
    logger.info(f"Wrote debug JSON to {output_path}")


def write_debug_plot(
    output_path: Path,
    features: ExtractedFeatures,
    anchors: List[Anchor],
    final_clips: List[ClipWindow],
):
    """
    Generate optional timeline visualization.
    
    Requires matplotlib (fails gracefully if not available).
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError:
        logger.warning("matplotlib not available, skipping debug plot")
        return
    
    try:
        fig, axes = plt.subplots(4, 1, figsize=(16, 10), sharex=True)
        times = features.times
        
        # Audio RMS
        ax = axes[0]
        ax.plot(times, features.audio_rms_z, 'b-', alpha=0.7, linewidth=0.5)
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.set_ylabel('Audio (z-score)')
        ax.set_title('V2 Pipeline Debug: Feature Timeline')
        
        # Motion
        ax = axes[1]
        ax.plot(times, features.motion_score_z, 'g-', alpha=0.7, linewidth=0.5)
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.set_ylabel('Motion (z-score)')
        
        # Excitement + Anchors
        ax = axes[2]
        ax.plot(times, features.excitement, 'r-', alpha=0.7, linewidth=0.5)
        for anchor in anchors:
            ax.axvline(x=anchor.time_sec, color='purple', alpha=0.5, linewidth=1)
        ax.set_ylabel('Excitement')
        ax.legend(['Excitement', 'Anchors'], loc='upper right')
        
        # Clips
        ax = axes[3]
        ax.set_ylim(0, 1)
        for i, clip in enumerate(final_clips):
            rect = patches.Rectangle(
                (clip.start_sec, 0.1), clip.duration, 0.8,
                linewidth=1, edgecolor='blue', facecolor='blue', alpha=0.3
            )
            ax.add_patch(rect)
            # Mark anchor
            ax.axvline(x=clip.anchor_time_sec, color='red', alpha=0.5, linewidth=0.5)
        ax.set_ylabel('Clips')
        ax.set_xlabel('Time (seconds)')
        
        # Scene cuts as vertical lines
        for cut in features.scene_cuts:
            for a in axes[:3]:
                a.axvline(x=cut, color='orange', alpha=0.2, linewidth=0.5)
        
        plt.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=100)
        plt.close()
        
        logger.info(f"Wrote debug plot to {output_path}")
        
    except Exception as e:
        logger.warning(f"Failed to generate debug plot: {e}")

