"""Project service layer."""
import shutil
from pathlib import Path
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.project import Project, ProjectStatus, SourceType
from app.models.clip import Clip
from app.models.job import Job, JobType, JobStatus
from app.utils.ffmpeg import get_video_info, FFmpegError
from app.utils.ytdlp import is_youtube_url, extract_video_title
from app.workers.job_runner import job_runner


class ProjectService:
    """Service for project operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_from_youtube(self, url: str, name: Optional[str] = None) -> Project:
        """
        Create a project from a YouTube URL.
        
        Args:
            url: YouTube video URL
            name: Optional project name (fetched from YouTube if not provided)
            
        Returns:
            Created project
        """
        if not is_youtube_url(url):
            raise ValueError("Invalid YouTube URL")
        
        # Get video title if name not provided
        if not name:
            name = await extract_video_title(url)
        
        project = Project(
            name=name,
            source_type=SourceType.YOUTUBE,
            source_url=url,
            status=ProjectStatus.PENDING
        )
        
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        
        # Create project directory
        project_dir = settings.projects_dir / str(project.id)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        return project
    
    async def create_from_local_file(
        self,
        file_path: str,
        name: Optional[str] = None,
        copy_file: bool = False
    ) -> Project:
        """
        Create a project from a local video file.
        
        Args:
            file_path: Path to local video file
            name: Optional project name (uses filename if not provided)
            copy_file: Whether to copy file to project directory
            
        Returns:
            Created project
        """
        source_path = Path(file_path)
        
        if not source_path.exists():
            raise ValueError(f"File not found: {file_path}")
        
        # Get video info to validate it's a valid video
        try:
            video_info = await get_video_info(source_path)
        except FFmpegError as e:
            raise ValueError(f"Invalid video file: {e}")
        
        # Use filename as name if not provided
        if not name:
            name = source_path.stem
        
        project = Project(
            name=name,
            source_type=SourceType.LOCAL,
            status=ProjectStatus.PENDING
        )
        
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        
        # Create project directory
        project_dir = settings.projects_dir / str(project.id)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Handle file path
        if copy_file:
            dest_path = project_dir / f"source{source_path.suffix}"
            shutil.copy2(source_path, dest_path)
            project.source_path = str(dest_path)
        else:
            project.source_path = str(source_path.absolute())
        
        # Update with video info
        project.duration = video_info.duration
        project.width = video_info.width
        project.height = video_info.height
        project.fps = video_info.fps
        project.video_codec = video_info.video_codec
        project.audio_codec = video_info.audio_codec
        project.status = ProjectStatus.DOWNLOADED  # Ready for analysis
        
        await self.db.commit()
        await self.db.refresh(project)
        
        return project
    
    async def get_project(self, project_id: int) -> Optional[Project]:
        """Get a project by ID."""
        return await self.db.get(Project, project_id)
    
    async def get_project_with_clips(self, project_id: int) -> Optional[Project]:
        """Get a project with its clips loaded."""
        result = await self.db.execute(
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.clips))
        )
        return result.scalar_one_or_none()
    
    async def list_projects(self) -> List[Project]:
        """List all projects."""
        result = await self.db.execute(
            select(Project).order_by(Project.created_at.desc())
        )
        return result.scalars().all()
    
    async def delete_project(self, project_id: int) -> bool:
        """
        Delete a project and its files.
        
        Args:
            project_id: Project ID
            
        Returns:
            True if deleted successfully
        """
        project = await self.db.get(Project, project_id)
        if not project:
            return False
        
        # Delete project directory
        project_dir = settings.projects_dir / str(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        await self.db.delete(project)
        await self.db.commit()
        
        return True
    
    async def set_output_folder(self, project_id: int, folder_path: str) -> Project:
        """
        Set the output folder for a project.
        
        Args:
            project_id: Project ID
            folder_path: Path to output folder
            
        Returns:
            Updated project
        """
        project = await self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Validate folder exists and is writable
        folder = Path(folder_path)
        if not folder.exists():
            # Try to create it
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise ValueError(f"Cannot create folder: {folder_path}")
        
        if not folder.is_dir():
            raise ValueError(f"Not a directory: {folder_path}")
        
        # Test write permissions
        test_file = folder / ".autoclip_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            raise ValueError(f"No write permission for: {folder_path}")
        
        project.output_folder = str(folder.absolute())
        await self.db.commit()
        await self.db.refresh(project)
        
        return project
    
    async def start_download_job(self, project_id: int) -> Job:
        """
        Start a download job for a YouTube project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Created job
        """
        project = await self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        if project.source_type != SourceType.YOUTUBE:
            raise ValueError("Download only available for YouTube projects")
        
        if project.status not in [ProjectStatus.PENDING, ProjectStatus.ERROR]:
            raise ValueError(f"Cannot download in state: {project.status}")
        
        # Create job record
        job = Job(
            project_id=project_id,
            job_type=JobType.DOWNLOAD,
            status=JobStatus.PENDING
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        # Start background job
        await job_runner.start_job(
            job.id,
            "download",
            project_id=project_id
        )
        
        return job
    
    async def start_analyze_job(self, project_id: int) -> Job:
        """
        Start an analysis job for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Created job
        """
        project = await self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        if not project.source_path:
            raise ValueError("No source video - download first")
        
        if project.status not in [ProjectStatus.DOWNLOADED, ProjectStatus.READY, ProjectStatus.ERROR]:
            raise ValueError(f"Cannot analyze in state: {project.status}")
        
        # Create job record
        job = Job(
            project_id=project_id,
            job_type=JobType.ANALYZE,
            status=JobStatus.PENDING
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        # Start background job
        await job_runner.start_job(
            job.id,
            "analyze",
            project_id=project_id
        )
        
        return job

