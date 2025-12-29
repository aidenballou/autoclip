"""Job handlers for different task types."""
import json
import logging
from pathlib import Path
from typing import Callable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.database import async_session_maker
from app.models.project import Project, ProjectStatus
from app.models.clip import Clip, ClipSource
from app.models.compound_clip import CompoundClip
from app.utils.ffmpeg import (
    get_video_info,
    detect_scenes,
    generate_thumbnail,
    export_clip,
    export_compound_clip,
    FFmpegError
)
from app.utils.ytdlp import download_video, YtdlpError
from app.pipeline.clip_processor import generate_clips_from_video, generate_clips_auto

logger = logging.getLogger(__name__)


async def handle_download(
    job_id: int,
    project_id: int,
    progress_callback: Callable,
    **kwargs
) -> dict:
    """
    Handle YouTube video download job.
    
    Args:
        job_id: Job ID
        project_id: Project ID
        progress_callback: Async callback for progress updates
        
    Returns:
        Result dictionary
    """
    async with async_session_maker() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        if not project.source_url:
            raise ValueError("No source URL provided")
        
        project.status = ProjectStatus.DOWNLOADING
        await session.commit()
        
        source_url = project.source_url
        project_dir = settings.projects_dir / str(project_id)
    
    try:
        await progress_callback(0, "Starting download...")
        
        # Download the video
        downloaded_path = await download_video(
            url=source_url,
            output_dir=project_dir,
            filename="source",
            progress_callback=progress_callback
        )
        
        await progress_callback(98, "Getting video info...")
        
        # Get video metadata
        video_info = await get_video_info(downloaded_path)
        
        # Update project with video info
        async with async_session_maker() as session:
            project = await session.get(Project, project_id)
            project.source_path = str(downloaded_path)
            project.duration = video_info.duration
            project.width = video_info.width
            project.height = video_info.height
            project.fps = video_info.fps
            project.video_codec = video_info.video_codec
            project.audio_codec = video_info.audio_codec
            project.status = ProjectStatus.DOWNLOADED
            await session.commit()
        
        await progress_callback(100, "Download complete")
        
        return {
            "path": str(downloaded_path),
            "duration": video_info.duration,
            "resolution": f"{video_info.width}x{video_info.height}"
        }
        
    except (YtdlpError, FFmpegError) as e:
        async with async_session_maker() as session:
            project = await session.get(Project, project_id)
            project.status = ProjectStatus.ERROR
            project.error_message = str(e)
            await session.commit()
        raise


async def handle_analyze(
    job_id: int,
    project_id: int,
    progress_callback: Callable,
    segmentation_mode: Optional[str] = None,
    **kwargs
) -> dict:
    """
    Handle video analysis and clip generation job.
    
    Args:
        job_id: Job ID
        project_id: Project ID
        progress_callback: Async callback for progress updates
        segmentation_mode: Override segmentation mode ("v1" or "v2")
        
    Returns:
        Result dictionary with clip count
    """
    async with async_session_maker() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        if not project.source_path:
            raise ValueError("No source video file")
        
        project.status = ProjectStatus.ANALYZING
        await session.commit()
        
        source_path = project.source_path
        video_duration = project.duration
    
    # Get the project directory for caching/debug
    project_dir = settings.projects_dir / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine mode
    mode = segmentation_mode or settings.segmentation_mode
    
    try:
        await progress_callback(0, f"Starting analysis ({mode})...")
        
        # Wrapper for progress callback to match expected signature
        async def pipeline_progress(pct, msg):
            await progress_callback(pct * 0.85, msg)  # Reserve 15% for thumbnails
        
        # Use unified pipeline interface
        clips_data = await generate_clips_auto(
            video_path=source_path,
            video_duration=video_duration,
            project_dir=project_dir,
            mode=mode,
            progress_callback=pipeline_progress
        )
        
        await progress_callback(85, f"Creating {len(clips_data)} clips...")
        
        # Delete existing auto-generated clips
        async with async_session_maker() as session:
            existing_clips = await session.execute(
                select(Clip).where(
                    Clip.project_id == project_id,
                    Clip.created_by == ClipSource.AUTO
                )
            )
            for clip in existing_clips.scalars():
                await session.delete(clip)
            await session.commit()
        
        # Create clip records with new fields
        async with async_session_maker() as session:
            for i, clip_data in enumerate(clips_data):
                clip = Clip(
                    project_id=project_id,
                    start_time=clip_data["start_time"],
                    end_time=clip_data["end_time"],
                    name=f"Clip {i + 1}",
                    created_by=ClipSource.AUTO,
                    ordering=i,
                    quality_score=clip_data.get("quality_score"),
                    anchor_time_sec=clip_data.get("anchor_time_sec"),
                    generation_version=clip_data.get("generation_version", mode)
                )
                session.add(clip)
            await session.commit()
        
        await progress_callback(88, "Generating thumbnails...")
        
        # Generate thumbnails
        await generate_clip_thumbnails(project_id, progress_callback, 88, 100)
        
        # Update project status
        async with async_session_maker() as session:
            project = await session.get(Project, project_id)
            project.status = ProjectStatus.READY
            await session.commit()
        
        await progress_callback(100, f"Analysis complete - {len(clips_data)} clips created ({mode})")
        
        return {
            "clip_count": len(clips_data),
            "segmentation_mode": mode
        }
        
    except (FFmpegError, Exception) as e:
        logger.exception(f"Analysis failed: {e}")
        async with async_session_maker() as session:
            project = await session.get(Project, project_id)
            project.status = ProjectStatus.ERROR
            project.error_message = str(e)
            await session.commit()
        raise


async def generate_clip_thumbnails(
    project_id: int,
    progress_callback: Callable,
    start_progress: float,
    end_progress: float
):
    """Generate thumbnails for all clips in a project."""
    async with async_session_maker() as session:
        project = await session.get(Project, project_id)
        result = await session.execute(
            select(Clip).where(Clip.project_id == project_id).order_by(Clip.ordering)
        )
        clips = result.scalars().all()
        
        if not clips:
            return
        
        source_path = project.source_path
        thumbnails_dir = settings.projects_dir / str(project_id) / "thumbnails"
        thumbnails_dir.mkdir(parents=True, exist_ok=True)
        
        progress_range = end_progress - start_progress
        
        for i, clip in enumerate(clips):
            # Generate thumbnail at midpoint
            midpoint = (clip.start_time + clip.end_time) / 2
            thumbnail_path = thumbnails_dir / f"clip_{clip.id}.{settings.thumbnail_format}"
            
            try:
                await generate_thumbnail(
                    source_path,
                    thumbnail_path,
                    midpoint
                )
                
                # Update clip with thumbnail path
                clip.thumbnail_path = str(thumbnail_path)
                await session.commit()
                
            except FFmpegError as e:
                logger.warning(f"Failed to generate thumbnail for clip {clip.id}: {e}")
            
            # Update progress
            clip_progress = start_progress + (progress_range * (i + 1) / len(clips))
            await progress_callback(clip_progress, f"Generating thumbnails: {i + 1}/{len(clips)}")


async def handle_thumbnail(
    job_id: int,
    project_id: int,
    progress_callback: Callable,
    clip_ids: Optional[List[int]] = None,
    **kwargs
) -> dict:
    """
    Handle thumbnail generation job.
    
    Args:
        job_id: Job ID
        project_id: Project ID
        progress_callback: Async callback for progress updates
        clip_ids: Optional list of specific clip IDs to generate thumbnails for
        
    Returns:
        Result dictionary
    """
    await generate_clip_thumbnails(project_id, progress_callback, 0, 100)
    return {"status": "completed"}


async def handle_export(
    job_id: int,
    project_id: int,
    progress_callback: Callable,
    clip_id: Optional[int] = None,
    compound_clip_id: Optional[int] = None,
    output_folder: Optional[str] = None,
    filename: Optional[str] = None,
    **kwargs
) -> dict:
    """
    Handle single clip or compound clip export job.
    
    Args:
        job_id: Job ID
        project_id: Project ID
        progress_callback: Async callback for progress updates
        clip_id: ID of clip to export (mutually exclusive with compound_clip_id)
        compound_clip_id: ID of compound clip to export
        output_folder: Destination folder (uses project default if not provided)
        filename: Output filename (auto-generated if not provided)
        
    Returns:
        Result dictionary with output path
    """
    async with async_session_maker() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Determine output folder
        dest_folder = output_folder or project.output_folder
        if not dest_folder:
            dest_folder = str(settings.projects_dir / str(project_id) / "exports")
        
        dest_folder = Path(dest_folder)
        dest_folder.mkdir(parents=True, exist_ok=True)
        
        # Check write permissions
        test_file = dest_folder / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            raise ValueError(f"Cannot write to output folder: {dest_folder}")
        
        source_path = project.source_path
        
        if compound_clip_id:
            # Export compound clip
            compound = await session.get(
                CompoundClip, compound_clip_id,
                options=[selectinload(CompoundClip.items).selectinload("clip")]
            )
            if not compound:
                raise ValueError(f"Compound clip {compound_clip_id} not found")
            
            # Build segments list
            segments = []
            for item in sorted(compound.items, key=lambda x: x.ordering):
                start = item.start_override if item.start_override is not None else item.clip.start_time
                end = item.end_override if item.end_override is not None else item.clip.end_time
                segments.append((start, end))
            
            output_filename = filename or f"{compound.name.replace(' ', '_')}.mp4"
            output_path = dest_folder / output_filename
            
            await progress_callback(0, "Exporting compound clip...")
            
            await export_compound_clip(
                source_path,
                output_path,
                segments,
                progress_callback
            )
            
        elif clip_id:
            # Export single clip
            clip = await session.get(Clip, clip_id)
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
            
            output_filename = filename or f"{clip.name.replace(' ', '_')}.mp4"
            output_path = dest_folder / output_filename
            
            await progress_callback(0, "Exporting clip...")
            
            await export_clip(
                source_path,
                output_path,
                clip.start_time,
                clip.end_time,
                progress_callback
            )
        
        else:
            raise ValueError("Either clip_id or compound_clip_id must be provided")
    
    await progress_callback(100, "Export complete")
    
    return {
        "output_path": str(output_path),
        "filename": output_filename
    }


async def handle_export_batch(
    job_id: int,
    project_id: int,
    progress_callback: Callable,
    clip_ids: List[int],
    output_folder: Optional[str] = None,
    **kwargs
) -> dict:
    """
    Handle batch export of multiple clips.
    
    Args:
        job_id: Job ID
        project_id: Project ID
        progress_callback: Async callback for progress updates
        clip_ids: List of clip IDs to export
        output_folder: Destination folder
        
    Returns:
        Result dictionary with list of output paths
    """
    async with async_session_maker() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        dest_folder = output_folder or project.output_folder
        if not dest_folder:
            dest_folder = str(settings.projects_dir / str(project_id) / "exports")
        
        dest_folder = Path(dest_folder)
        dest_folder.mkdir(parents=True, exist_ok=True)
        
        source_path = project.source_path
        
        # Get all clips
        result = await session.execute(
            select(Clip).where(Clip.id.in_(clip_ids))
        )
        clips = result.scalars().all()
        
        if not clips:
            raise ValueError("No clips found")
    
    exported = []
    total = len(clips)
    
    for i, clip in enumerate(clips):
        clip_progress_start = (i / total) * 100
        clip_progress_end = ((i + 1) / total) * 100
        
        async def clip_progress(p, msg=None):
            actual_progress = clip_progress_start + (p / 100) * (clip_progress_end - clip_progress_start)
            await progress_callback(actual_progress, f"Exporting clip {i + 1}/{total}")
        
        output_filename = f"{clip.name.replace(' ', '_')}.mp4"
        output_path = dest_folder / output_filename
        
        # Handle duplicate filenames
        counter = 1
        while output_path.exists():
            output_filename = f"{clip.name.replace(' ', '_')}_{counter}.mp4"
            output_path = dest_folder / output_filename
            counter += 1
        
        await export_clip(
            source_path,
            output_path,
            clip.start_time,
            clip.end_time,
            clip_progress
        )
        
        exported.append(str(output_path))
    
    await progress_callback(100, f"Exported {len(exported)} clips")
    
    return {
        "exported_count": len(exported),
        "output_paths": exported
    }

