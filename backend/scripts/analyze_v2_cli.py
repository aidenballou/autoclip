#!/usr/bin/env python3
"""
CLI tool to run V2 pipeline on a video file and emit debug JSON.

Usage:
    python scripts/analyze_v2_cli.py <video_path> [--output-dir <dir>] [--mode v1|v2]

Example:
    python scripts/analyze_v2_cli.py ~/Videos/highlights.mp4 --output-dir ./output
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline.v2.config import V2PipelineConfig
from app.pipeline.v2.runner import run_v2_pipeline
from app.utils.ffmpeg import get_video_info


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def analyze_video(
    video_path: Path,
    output_dir: Path,
    mode: str = "v2",
    config: V2PipelineConfig = None,
):
    """
    Analyze a video file and write debug output.
    
    Args:
        video_path: Path to video file
        output_dir: Directory for output files
        mode: Pipeline mode ("v1" or "v2")
        config: Optional pipeline config override
    """
    # Validate input
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get video info
    logger.info(f"Analyzing: {video_path}")
    video_info = await get_video_info(video_path)
    logger.info(f"Duration: {video_info.duration:.1f}s, Resolution: {video_info.width}x{video_info.height}")
    
    if mode == "v1":
        # Run V1 pipeline
        from app.utils.ffmpeg import detect_scenes
        from app.pipeline.v1 import generate_clips_from_video
        
        logger.info("Running V1 (scene-based) pipeline...")
        
        scene_timestamps = await detect_scenes(video_path)
        segments = generate_clips_from_video(scene_timestamps, video_info.duration)
        
        # Write simple output
        clips_data = [
            {
                "index": i,
                "start_time": seg.start,
                "end_time": seg.end,
                "duration": seg.duration,
            }
            for i, seg in enumerate(segments)
        ]
        
        output_file = output_dir / "v1_clips.json"
        with open(output_file, 'w') as f:
            json.dump({
                "video_path": str(video_path),
                "duration": video_info.duration,
                "scene_count": len(scene_timestamps),
                "clip_count": len(segments),
                "clips": clips_data,
            }, f, indent=2)
        
        logger.info(f"V1 output written to: {output_file}")
        logger.info(f"Generated {len(segments)} clips from {len(scene_timestamps)} scenes")
        
    else:
        # Run V2 pipeline
        logger.info("Running V2 (highlight-aware) pipeline...")
        
        config = config or V2PipelineConfig(write_debug_json=True, write_debug_plot=True)
        
        async def progress_callback(pct, msg):
            logger.info(f"[{pct:.0f}%] {msg}")
        
        result = await run_v2_pipeline(
            video_path=video_path,
            duration=video_info.duration,
            project_dir=output_dir,
            config=config,
            progress_callback=progress_callback,
        )
        
        # Write clips summary
        clips_data = result.to_clip_list()
        output_file = output_dir / "v2_clips.json"
        with open(output_file, 'w') as f:
            json.dump({
                "video_path": str(video_path),
                "duration": video_info.duration,
                "anchor_count": len(result.anchors),
                "boundary_count": len(result.boundaries),
                "clip_count": len(result.clips),
                "clips": clips_data,
            }, f, indent=2)
        
        logger.info(f"V2 clips written to: {output_file}")
        logger.info(f"Debug JSON at: {output_dir}/debug/segmentation_v2_debug.json")
        logger.info(f"Generated {len(result.clips)} clips from {len(result.anchors)} anchors")
        
        # Print top clips by quality
        logger.info("\nTop 10 clips by quality:")
        sorted_clips = sorted(result.clips, key=lambda c: c.quality_score, reverse=True)[:10]
        for i, clip in enumerate(sorted_clips):
            logger.info(
                f"  {i+1}. {clip.start_sec:.1f}s - {clip.end_sec:.1f}s "
                f"(quality: {clip.quality_score:.3f}, anchor: {clip.anchor_time_sec:.1f}s)"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a video file with AutoClip V2 pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze with V2 pipeline (default)
    python scripts/analyze_v2_cli.py video.mp4

    # Compare V1 and V2
    python scripts/analyze_v2_cli.py video.mp4 --mode v1 --output-dir ./v1_output
    python scripts/analyze_v2_cli.py video.mp4 --mode v2 --output-dir ./v2_output

    # Custom output directory
    python scripts/analyze_v2_cli.py video.mp4 --output-dir /path/to/output
        """
    )
    
    parser.add_argument(
        "video_path",
        type=Path,
        help="Path to video file to analyze"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=None,
        help="Output directory for debug files (default: ./autoclip_output)"
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["v1", "v2"],
        default="v2",
        help="Pipeline mode: v1 (scene-based) or v2 (highlight-aware)"
    )
    
    args = parser.parse_args()
    
    # Default output directory
    if args.output_dir is None:
        args.output_dir = Path("./autoclip_output")
    
    # Run
    try:
        asyncio.run(analyze_video(
            video_path=args.video_path,
            output_dir=args.output_dir,
            mode=args.mode,
        ))
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

