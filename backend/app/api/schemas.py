"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Project Schemas
# =============================================================================

class ProjectCreateYoutube(BaseModel):
    """Request to create a project from YouTube."""
    youtube_url: str = Field(..., description="YouTube video URL")
    name: Optional[str] = Field(None, description="Project name (fetched from YouTube if not provided)")


class ProjectCreateLocal(BaseModel):
    """Request to create a project from a local file."""
    file_path: str = Field(..., description="Path to local video file")
    name: Optional[str] = Field(None, description="Project name (uses filename if not provided)")
    copy_file: bool = Field(False, description="Whether to copy file to project directory")


class ProjectResponse(BaseModel):
    """Project response."""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    source_type: str
    source_url: Optional[str]
    source_path: Optional[str]
    duration: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    video_codec: Optional[str]
    audio_codec: Optional[str]
    status: str
    error_message: Optional[str]
    output_folder: Optional[str]
    clip_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class SetOutputFolderRequest(BaseModel):
    """Request to set output folder."""
    folder_path: str = Field(..., description="Path to output folder")


class ValidateFolderResponse(BaseModel):
    """Response for folder validation."""
    valid: bool
    path: str
    message: Optional[str] = None


# =============================================================================
# Clip Schemas
# =============================================================================

class ClipResponse(BaseModel):
    """Clip response."""
    id: int
    project_id: int
    start_time: float
    end_time: float
    duration: float
    name: Optional[str]
    thumbnail_path: Optional[str]
    thumbnail_url: Optional[str] = None
    created_by: str
    ordering: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ClipUpdate(BaseModel):
    """Request to update a clip."""
    start_time: Optional[float] = Field(None, ge=0)
    end_time: Optional[float] = Field(None, gt=0)
    name: Optional[str] = None


# =============================================================================
# Compound Clip Schemas
# =============================================================================

class CompoundClipItemRequest(BaseModel):
    """Item in a compound clip create request."""
    clip_id: int
    start_override: Optional[float] = None
    end_override: Optional[float] = None


class CompoundClipCreate(BaseModel):
    """Request to create a compound clip."""
    name: str = Field(..., min_length=1)
    items: List[CompoundClipItemRequest] = Field(..., min_length=1)


class CompoundClipItemResponse(BaseModel):
    """Compound clip item response."""
    id: int
    clip_id: int
    start_time: float
    end_time: float
    duration: float
    ordering: int
    
    class Config:
        from_attributes = True


class CompoundClipResponse(BaseModel):
    """Compound clip response."""
    id: int
    project_id: int
    name: str
    total_duration: float
    items: List[CompoundClipItemResponse]
    created_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# Export Schemas
# =============================================================================

class ExportClipRequest(BaseModel):
    """Request to export a single clip."""
    clip_id: Optional[int] = None
    compound_clip_id: Optional[int] = None
    output_folder: Optional[str] = None
    filename: Optional[str] = None


class ExportBatchRequest(BaseModel):
    """Request to batch export clips."""
    clip_ids: List[int] = Field(..., min_length=1)
    output_folder: Optional[str] = None


# =============================================================================
# Job Schemas
# =============================================================================

class JobResponse(BaseModel):
    """Job response."""
    id: int
    project_id: int
    job_type: str
    status: str
    progress: float
    message: Optional[str]
    result: Optional[str]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# =============================================================================
# Health Check
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    ffmpeg_available: bool
    ffprobe_available: bool
    ytdlp_available: bool
    message: Optional[str] = None


class DependencyCheckResponse(BaseModel):
    """Dependency check response."""
    name: str
    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    install_command: Optional[str] = None

