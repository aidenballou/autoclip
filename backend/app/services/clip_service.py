"""Clip service layer."""
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.clip import Clip, ClipSource
from app.models.compound_clip import CompoundClip, CompoundClipItem
from app.models.job import Job, JobType, JobStatus
from app.workers.job_runner import job_runner


class ClipService:
    """Service for clip operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_clip(self, clip_id: int) -> Optional[Clip]:
        """Get a clip by ID."""
        return await self.db.get(Clip, clip_id)
    
    async def list_clips(self, project_id: int) -> List[Clip]:
        """List all clips for a project."""
        result = await self.db.execute(
            select(Clip)
            .where(Clip.project_id == project_id)
            .order_by(Clip.ordering)
        )
        return result.scalars().all()
    
    async def update_clip(
        self,
        clip_id: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        name: Optional[str] = None
    ) -> Clip:
        """
        Update a clip's properties.
        
        Args:
            clip_id: Clip ID
            start_time: New start time
            end_time: New end time
            name: New name
            
        Returns:
            Updated clip
        """
        clip = await self.db.get(Clip, clip_id)
        if not clip:
            raise ValueError(f"Clip {clip_id} not found")
        
        if start_time is not None:
            if start_time < 0:
                raise ValueError("Start time cannot be negative")
            clip.start_time = start_time
            clip.created_by = ClipSource.MANUAL
        
        if end_time is not None:
            if end_time <= clip.start_time:
                raise ValueError("End time must be after start time")
            clip.end_time = end_time
            clip.created_by = ClipSource.MANUAL
        
        if name is not None:
            clip.name = name
        
        await self.db.commit()
        await self.db.refresh(clip)
        
        return clip
    
    async def delete_clip(self, clip_id: int) -> bool:
        """Delete a clip."""
        clip = await self.db.get(Clip, clip_id)
        if not clip:
            return False
        
        await self.db.delete(clip)
        await self.db.commit()
        
        return True
    
    async def create_compound_clip(
        self,
        project_id: int,
        name: str,
        clip_items: List[dict]
    ) -> CompoundClip:
        """
        Create a compound clip from multiple clips.
        
        Args:
            project_id: Project ID
            name: Compound clip name
            clip_items: List of dicts with clip_id and optional start/end overrides
                       [{"clip_id": 1, "start_override": 1.0, "end_override": 5.0}, ...]
            
        Returns:
            Created compound clip
        """
        compound = CompoundClip(
            project_id=project_id,
            name=name
        )
        self.db.add(compound)
        await self.db.flush()  # Get compound.id
        
        for i, item in enumerate(clip_items):
            clip_id = item.get("clip_id")
            if not clip_id:
                raise ValueError(f"Missing clip_id in item {i}")
            
            # Verify clip exists and belongs to project
            clip = await self.db.get(Clip, clip_id)
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
            if clip.project_id != project_id:
                raise ValueError(f"Clip {clip_id} does not belong to project {project_id}")
            
            compound_item = CompoundClipItem(
                compound_clip_id=compound.id,
                clip_id=clip_id,
                start_override=item.get("start_override"),
                end_override=item.get("end_override"),
                ordering=i
            )
            self.db.add(compound_item)
        
        await self.db.commit()
        await self.db.refresh(compound)
        
        # Load items relationship
        result = await self.db.execute(
            select(CompoundClip)
            .where(CompoundClip.id == compound.id)
            .options(selectinload(CompoundClip.items))
        )
        return result.scalar_one()
    
    async def get_compound_clip(self, compound_id: int) -> Optional[CompoundClip]:
        """Get a compound clip with its items."""
        result = await self.db.execute(
            select(CompoundClip)
            .where(CompoundClip.id == compound_id)
            .options(selectinload(CompoundClip.items).selectinload(CompoundClipItem.clip))
        )
        return result.scalar_one_or_none()
    
    async def list_compound_clips(self, project_id: int) -> List[CompoundClip]:
        """List compound clips for a project."""
        result = await self.db.execute(
            select(CompoundClip)
            .where(CompoundClip.project_id == project_id)
            .options(selectinload(CompoundClip.items))
            .order_by(CompoundClip.created_at.desc())
        )
        return result.scalars().all()
    
    async def delete_compound_clip(self, compound_id: int) -> bool:
        """Delete a compound clip."""
        compound = await self.db.get(CompoundClip, compound_id)
        if not compound:
            return False
        
        await self.db.delete(compound)
        await self.db.commit()
        
        return True
    
    async def export_clip(
        self,
        project_id: int,
        clip_id: int,
        output_folder: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Job:
        """
        Start an export job for a single clip.
        
        Args:
            project_id: Project ID
            clip_id: Clip ID
            output_folder: Optional output folder override
            filename: Optional output filename
            
        Returns:
            Created job
        """
        job = Job(
            project_id=project_id,
            job_type=JobType.EXPORT,
            status=JobStatus.PENDING
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        await job_runner.start_job(
            job.id,
            "export",
            project_id=project_id,
            clip_id=clip_id,
            output_folder=output_folder,
            filename=filename
        )
        
        return job
    
    async def export_compound_clip(
        self,
        project_id: int,
        compound_clip_id: int,
        output_folder: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Job:
        """
        Start an export job for a compound clip.
        
        Args:
            project_id: Project ID
            compound_clip_id: Compound clip ID
            output_folder: Optional output folder override
            filename: Optional output filename
            
        Returns:
            Created job
        """
        job = Job(
            project_id=project_id,
            job_type=JobType.EXPORT,
            status=JobStatus.PENDING
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        await job_runner.start_job(
            job.id,
            "export",
            project_id=project_id,
            compound_clip_id=compound_clip_id,
            output_folder=output_folder,
            filename=filename
        )
        
        return job
    
    async def export_batch(
        self,
        project_id: int,
        clip_ids: List[int],
        output_folder: Optional[str] = None
    ) -> Job:
        """
        Start a batch export job.
        
        Args:
            project_id: Project ID
            clip_ids: List of clip IDs to export
            output_folder: Optional output folder override
            
        Returns:
            Created job
        """
        job = Job(
            project_id=project_id,
            job_type=JobType.EXPORT_BATCH,
            status=JobStatus.PENDING
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        await job_runner.start_job(
            job.id,
            "export_batch",
            project_id=project_id,
            clip_ids=clip_ids,
            output_folder=output_folder
        )
        
        return job

