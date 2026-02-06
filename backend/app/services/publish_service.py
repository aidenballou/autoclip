"""Publish service for multi-platform clip distribution."""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.clip import Clip
from app.models.project import Project
from app.models.niche import Niche
from app.models.account import Account, Platform, AuthStatus
from app.models.job import Job, JobType, JobStatus
from app.utils.ffmpeg import (
    export_clip_enhanced,
    ExportPreset,
    TextOverlay,
    AudioOverlay,
    FFmpegError,
)


# Platform-specific requirements and recommendations
PLATFORM_SPECS = {
    Platform.YOUTUBE_SHORTS: {
        "max_duration": 60,
        "min_duration": 15,
        "aspect_ratio": "9:16",
        "max_file_size_mb": 256,
        "recommended_resolution": (1080, 1920),
        "formats": ["mp4"],
    },
    Platform.TIKTOK: {
        "max_duration": 180,
        "min_duration": 3,
        "aspect_ratio": "9:16",
        "max_file_size_mb": 287,
        "recommended_resolution": (1080, 1920),
        "formats": ["mp4"],
    },
    Platform.INSTAGRAM_REELS: {
        "max_duration": 90,
        "min_duration": 3,
        "aspect_ratio": "9:16",
        "max_file_size_mb": 250,
        "recommended_resolution": (1080, 1920),
        "formats": ["mp4"],
    },
    Platform.TWITTER: {
        "max_duration": 140,
        "min_duration": 0.5,
        "aspect_ratio": "any",
        "max_file_size_mb": 512,
        "recommended_resolution": (1280, 720),
        "formats": ["mp4"],
    },
    Platform.SNAPCHAT: {
        "max_duration": 60,
        "min_duration": 3,
        "aspect_ratio": "9:16",
        "max_file_size_mb": 32,
        "recommended_resolution": (1080, 1920),
        "formats": ["mp4"],
    },
}


class PublishService:
    """Service for managing multi-platform clip publishing."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_publish_job(
        self,
        project_id: int,
        clip_id: int,
        niche_id: int,
        account_ids: List[int],
        output_base_folder: str,
        caption: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        text_overlay_text: Optional[str] = None,
        text_overlay_position: str = "bottom",
        text_overlay_color: str = "#FFFFFF",
        text_overlay_size: int = 48,
        background_audio_path: Optional[str] = None,
        background_audio_volume: int = 30,
        original_audio_volume: int = 100,
        use_vertical_preset: bool = True,
        vertical_framing: Optional[str] = None,
        vertical_resolution: Optional[str] = None,
    ) -> Job:
        """
        Create a publish job to export a clip for multiple platforms.
        
        Returns a Job that can be tracked for progress.
        """
        # Verify project exists
        project = await self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Verify clip exists
        clip = await self.db.get(Clip, clip_id)
        if not clip or clip.project_id != project_id:
            raise ValueError(f"Clip {clip_id} not found in project {project_id}")
        
        # Verify niche exists
        niche = await self.db.get(Niche, niche_id)
        if not niche:
            raise ValueError(f"Niche {niche_id} not found")
        
        # Verify accounts exist and belong to niche
        accounts = []
        for account_id in account_ids:
            account = await self.db.get(Account, account_id)
            if not account:
                raise ValueError(f"Account {account_id} not found")
            if account.niche_id != niche_id:
                raise ValueError(f"Account {account_id} does not belong to niche {niche_id}")
            accounts.append(account)
        
        # Create job with metadata
        job_metadata = {
            "clip_id": clip_id,
            "niche_id": niche_id,
            "account_ids": account_ids,
            "output_base_folder": output_base_folder,
            "caption": caption,
            "hashtags": hashtags or [],
            "text_overlay": {
                "text": text_overlay_text,
                "position": text_overlay_position,
                "color": text_overlay_color,
                "size": text_overlay_size,
            } if text_overlay_text else None,
            "audio_overlay": {
                "path": background_audio_path,
                "volume": background_audio_volume,
                "original_volume": original_audio_volume,
            } if background_audio_path else None,
            "use_vertical_preset": use_vertical_preset,
            "vertical_framing": vertical_framing or settings.vertical_framing,
            "vertical_resolution": vertical_resolution or settings.vertical_resolution,
        }
        
        job = Job(
            project_id=project_id,
            job_type=JobType.EXPORT,
            status=JobStatus.PENDING,
            message="Preparing publish job...",
            result=json.dumps(job_metadata),
        )
        
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        
        return job
    
    async def execute_publish_job(
        self,
        job_id: int,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Execute a publish job - export clip for all target platforms.
        
        Returns dict with export results per platform.
        """
        job = await self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        metadata = json.loads(job.result)
        
        # Get required entities
        project = await self.db.get(Project, job.project_id)
        clip = await self.db.get(Clip, metadata["clip_id"])
        niche = await self.db.get(Niche, metadata["niche_id"])
        
        accounts = []
        for account_id in metadata["account_ids"]:
            account = await self.db.get(Account, account_id)
            accounts.append(account)
        
        # Update job status
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.message = "Exporting clips for platforms..."
        await self.db.flush()
        
        results = {
            "exports": [],
            "errors": [],
        }
        
        try:
            output_base = Path(metadata["output_base_folder"])
            output_base.mkdir(parents=True, exist_ok=True)
            
            # Group accounts by platform
            platforms = {}
            for account in accounts:
                if account.platform not in platforms:
                    platforms[account.platform] = []
                platforms[account.platform].append(account)
            
            total_platforms = len(platforms)
            completed = 0
            
            for platform, platform_accounts in platforms.items():
                try:
                    # Create platform-specific folder
                    platform_folder = output_base / platform.value
                    platform_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Build export settings
                    preset = None
                    if metadata["use_vertical_preset"]:
                        preset = ExportPreset.vertical()
                    vertical_framing = metadata.get("vertical_framing") or settings.vertical_framing
                    vertical_resolution = metadata.get("vertical_resolution") or settings.vertical_resolution
                    
                    text_overlay = None
                    if metadata.get("text_overlay") and metadata["text_overlay"].get("text"):
                        to = metadata["text_overlay"]
                        text_overlay = TextOverlay(
                            text=to["text"],
                            position=to["position"],
                            font_size=to["size"],
                            font_color=to["color"],
                        )
                    
                    audio_overlay = None
                    if metadata.get("audio_overlay") and metadata["audio_overlay"].get("path"):
                        ao = metadata["audio_overlay"]
                        audio_overlay = AudioOverlay(
                            audio_path=ao["path"],
                            volume=ao["volume"],
                            original_volume=ao["original_volume"],
                        )
                    
                    # Generate output filename
                    clip_name = clip.name or f"clip_{clip.id}"
                    safe_name = "".join(c for c in clip_name if c.isalnum() or c in (" ", "-", "_")).strip()
                    output_filename = f"{safe_name}_{platform.value}.mp4"
                    output_path = platform_folder / output_filename
                    
                    # Export the clip
                    await export_clip_enhanced(
                        source_path=project.source_path,
                        output_path=output_path,
                        start_time=clip.start_time,
                        end_time=clip.end_time,
                        preset=preset,
                        vertical_framing=vertical_framing,
                        vertical_resolution=vertical_resolution,
                        text_overlay=text_overlay,
                        audio_overlay=audio_overlay,
                        progress_callback=None,  # Individual progress not tracked
                    )
                    
                    # Generate metadata.json for this platform
                    platform_metadata = self._generate_metadata(
                        clip=clip,
                        niche=niche,
                        platform=platform,
                        accounts=platform_accounts,
                        caption=metadata.get("caption"),
                        hashtags=metadata.get("hashtags", []),
                        output_filename=output_filename,
                    )
                    
                    metadata_path = platform_folder / f"{safe_name}_metadata.json"
                    with open(metadata_path, "w") as f:
                        json.dump(platform_metadata, f, indent=2, default=str)
                    
                    results["exports"].append({
                        "platform": platform.value,
                        "video_path": str(output_path),
                        "metadata_path": str(metadata_path),
                        "accounts": [a.handle for a in platform_accounts],
                    })
                    
                except Exception as e:
                    results["errors"].append({
                        "platform": platform.value,
                        "error": str(e),
                    })
                
                completed += 1
                if progress_callback:
                    await progress_callback((completed / total_platforms) * 100)
                
                job.progress = (completed / total_platforms) * 100
                job.message = f"Exported {completed}/{total_platforms} platforms"
                await self.db.flush()
            
            # Update job completion
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 100
            job.message = f"Published to {len(results['exports'])} platforms"
            job.result = json.dumps(results)
            
            if results["errors"]:
                job.error = f"{len(results['errors'])} platform(s) failed"
            
            await self.db.flush()
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            await self.db.flush()
            raise
        
        return results
    
    def _generate_metadata(
        self,
        clip: Clip,
        niche: Niche,
        platform: Platform,
        accounts: List[Account],
        caption: Optional[str],
        hashtags: List[str],
        output_filename: str,
    ) -> Dict[str, Any]:
        """Generate metadata.json for a platform export."""
        # Merge niche defaults with provided values
        final_hashtags = hashtags or []
        if niche.default_hashtags:
            try:
                niche_tags = json.loads(niche.default_hashtags)
                final_hashtags = list(set(final_hashtags + niche_tags))
            except json.JSONDecodeError:
                pass
        
        # Apply caption template if no caption provided
        final_caption = caption
        if not final_caption and niche.default_caption_template:
            final_caption = niche.default_caption_template
        
        # Platform-specific hashtag formatting
        if platform == Platform.TWITTER:
            # Twitter prefers hashtags at the end
            hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in final_hashtags)
        else:
            # Most platforms: hashtags inline or at end
            hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in final_hashtags)
        
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "clip": {
                "id": clip.id,
                "name": clip.name,
                "duration": clip.duration,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
            },
            "niche": {
                "id": niche.id,
                "name": niche.name,
            },
            "platform": {
                "name": platform.value,
                "specs": PLATFORM_SPECS.get(platform, {}),
            },
            "accounts": [
                {
                    "id": a.id,
                    "handle": a.handle,
                    "display_name": a.display_name,
                    "auth_status": a.auth_status.value,
                    "auto_upload": a.auto_upload,
                }
                for a in accounts
            ],
            "content": {
                "caption": final_caption,
                "hashtags": final_hashtags,
                "hashtag_string": hashtag_str,
                "full_caption": f"{final_caption}\n\n{hashtag_str}" if final_caption else hashtag_str,
            },
            "output": {
                "filename": output_filename,
            },
        }
    
    async def get_platform_requirements(self, platform: str) -> Dict[str, Any]:
        """Get requirements and recommendations for a platform."""
        try:
            platform_enum = Platform(platform)
            return PLATFORM_SPECS.get(platform_enum, {})
        except ValueError:
            raise ValueError(f"Unknown platform: {platform}")
    
    async def validate_clip_for_platforms(
        self,
        clip_id: int,
        platforms: List[str],
    ) -> Dict[str, Any]:
        """Check if a clip meets requirements for target platforms."""
        clip = await self.db.get(Clip, clip_id)
        if not clip:
            raise ValueError(f"Clip {clip_id} not found")
        
        results = {}
        for platform_str in platforms:
            try:
                platform = Platform(platform_str)
                specs = PLATFORM_SPECS.get(platform, {})
                
                issues = []
                warnings = []
                
                # Check duration
                if specs.get("max_duration") and clip.duration > specs["max_duration"]:
                    issues.append(f"Clip is {clip.duration:.1f}s, max is {specs['max_duration']}s")
                if specs.get("min_duration") and clip.duration < specs["min_duration"]:
                    issues.append(f"Clip is {clip.duration:.1f}s, min is {specs['min_duration']}s")
                
                results[platform_str] = {
                    "valid": len(issues) == 0,
                    "issues": issues,
                    "warnings": warnings,
                    "specs": specs,
                }
                
            except ValueError:
                results[platform_str] = {
                    "valid": False,
                    "issues": [f"Unknown platform: {platform_str}"],
                    "warnings": [],
                    "specs": {},
                }
        
        return results
