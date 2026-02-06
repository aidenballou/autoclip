"""API routes."""
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.project import Project
from app.models.clip import Clip
from app.models.compound_clip import CompoundClip
from app.models.job import Job
from app.services.project_service import ProjectService
from app.services.clip_service import ClipService
from app.utils.ffmpeg import check_ffmpeg_available, check_ffprobe_available
from app.utils.ytdlp import check_ytdlp_available
from app.api.schemas import (
    ProjectCreateYoutube,
    ProjectCreateLocal,
    ProjectResponse,
    SetOutputFolderRequest,
    ValidateFolderResponse,
    ClipResponse,
    ClipUpdate,
    CompoundClipCreate,
    CompoundClipResponse,
    ExportClipRequest,
    ExportBatchRequest,
    AnalyzeRequest,
    JobResponse,
    HealthResponse,
    DependencyCheckResponse,
    NicheCreate,
    NicheUpdate,
    NicheResponse,
    AccountCreate,
    AccountUpdate,
    AccountResponse,
    PublishRequest,
    PublishResultResponse,
    PlatformSpecsResponse,
    ClipValidationResult,
    UploadRequest,
    UploadResultResponse,
    OAuthUrlResponse,
    OAuthCallbackRequest,
    OAuthCallbackConnectedResponse,
    OAuthCallbackSelectionRequiredResponse,
    YouTubeChannelSelectionRequest,
    YouTubePendingChannelsResponse,
    UploadSelectedRequest,
    UploadSelectedResponse,
)
from app.services.niche_service import NicheService
from app.services.publish_service import PublishService
from app.services.upload_service import UploadService, OAuthUpstreamError

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Health & System
# =============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and dependencies."""
    ffmpeg_ok = check_ffmpeg_available()
    ffprobe_ok = check_ffprobe_available()
    ytdlp_ok = check_ytdlp_available()
    
    all_ok = ffmpeg_ok and ffprobe_ok and ytdlp_ok
    
    message = None
    if not all_ok:
        missing = []
        if not ffmpeg_ok:
            missing.append("ffmpeg")
        if not ffprobe_ok:
            missing.append("ffprobe")
        if not ytdlp_ok:
            missing.append("yt-dlp")
        message = f"Missing dependencies: {', '.join(missing)}. Install with: brew install ffmpeg yt-dlp"
    
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
        ytdlp_available=ytdlp_ok,
        message=message
    )


@router.get("/dependencies", response_model=List[DependencyCheckResponse])
async def check_dependencies():
    """Check status of all dependencies."""
    deps = []
    
    # FFmpeg
    ffmpeg_path = shutil.which(settings.ffmpeg_path)
    deps.append(DependencyCheckResponse(
        name="ffmpeg",
        available=ffmpeg_path is not None,
        path=ffmpeg_path,
        install_command="brew install ffmpeg"
    ))
    
    # FFprobe
    ffprobe_path = shutil.which(settings.ffprobe_path)
    deps.append(DependencyCheckResponse(
        name="ffprobe",
        available=ffprobe_path is not None,
        path=ffprobe_path,
        install_command="brew install ffmpeg"
    ))
    
    # yt-dlp
    ytdlp_path = shutil.which(settings.ytdlp_path)
    deps.append(DependencyCheckResponse(
        name="yt-dlp",
        available=ytdlp_path is not None,
        path=ytdlp_path,
        install_command="brew install yt-dlp"
    ))
    
    return deps


# =============================================================================
# Projects
# =============================================================================

@router.post("/projects/youtube", response_model=ProjectResponse)
async def create_project_youtube(
    data: ProjectCreateYoutube,
    db: AsyncSession = Depends(get_db)
):
    """Create a project from a YouTube URL."""
    service = ProjectService(db)
    try:
        project = await service.create_from_youtube(data.youtube_url, data.name)
        return await _project_to_response(project, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/local", response_model=ProjectResponse)
async def create_project_local(
    data: ProjectCreateLocal,
    db: AsyncSession = Depends(get_db)
):
    """Create a project from a local video file."""
    service = ProjectService(db)
    try:
        project = await service.create_from_local_file(
            data.file_path,
            data.name,
            data.copy_file
        )
        return await _project_to_response(project, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/upload", response_model=ProjectResponse)
async def create_project_upload(
    file: UploadFile = File(...),
    name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Create a project by uploading a video file."""
    # Create temporary file
    temp_dir = settings.data_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    temp_path = temp_dir / file.filename
    
    try:
        # Save uploaded file
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create project with copy
        service = ProjectService(db)
        project = await service.create_from_local_file(
            str(temp_path),
            name or Path(file.filename).stem,
            copy_file=True
        )
        
        return await _project_to_response(project, db)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects."""
    service = ProjectService(db)
    projects = await service.list_projects()
    return [await _project_to_response(p, db) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get a project by ID."""
    service = ProjectService(db)
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _project_to_response(project, db)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a project."""
    service = ProjectService(db)
    if not await service.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


@router.post("/projects/{project_id}/download", response_model=JobResponse)
async def start_download(project_id: int, db: AsyncSession = Depends(get_db)):
    """Start downloading a YouTube video."""
    service = ProjectService(db)
    try:
        job = await service.start_download_job(project_id)
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/analyze", response_model=JobResponse)
async def start_analysis(
    project_id: int,
    segmentation_mode: Optional[str] = Query(
        None,
        description="Segmentation mode: 'v1' (scene-based) or 'v2' (highlight-aware)"
    ),
    db: AsyncSession = Depends(get_db)
):
    """Start video analysis and clip generation.
    
    Use segmentation_mode to override the default:
    - v1: Scene-based segmentation (original algorithm)
    - v2: Highlight-aware segmentation (improved algorithm with quality scores)
    """
    service = ProjectService(db)
    try:
        job = await service.start_analyze_job(project_id, segmentation_mode=segmentation_mode)
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/output-folder", response_model=ProjectResponse)
async def set_output_folder(
    project_id: int,
    data: SetOutputFolderRequest,
    db: AsyncSession = Depends(get_db)
):
    """Set the output folder for a project."""
    service = ProjectService(db)
    try:
        project = await service.set_output_folder(project_id, data.folder_path)
        return await _project_to_response(project, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validate-folder", response_model=ValidateFolderResponse)
async def validate_folder(data: SetOutputFolderRequest):
    """Validate a folder path for write access."""
    folder = Path(data.folder_path)
    
    if not folder.exists():
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return ValidateFolderResponse(
                valid=False,
                path=str(folder),
                message="Cannot create folder - permission denied"
            )
        except Exception as e:
            return ValidateFolderResponse(
                valid=False,
                path=str(folder),
                message=f"Cannot create folder: {e}"
            )
    
    if not folder.is_dir():
        return ValidateFolderResponse(
            valid=False,
            path=str(folder),
            message="Path is not a directory"
        )
    
    # Test write permission
    test_file = folder / ".autoclip_test"
    try:
        test_file.touch()
        test_file.unlink()
    except PermissionError:
        return ValidateFolderResponse(
            valid=False,
            path=str(folder),
            message="No write permission for this folder"
        )
    
    return ValidateFolderResponse(
        valid=True,
        path=str(folder.absolute()),
        message="Folder is valid and writable"
    )


# =============================================================================
# Clips
# =============================================================================

@router.get("/projects/{project_id}/clips", response_model=List[ClipResponse])
async def list_clips(project_id: int, db: AsyncSession = Depends(get_db)):
    """List all clips for a project."""
    service = ClipService(db)
    clips = await service.list_clips(project_id)
    return [_clip_to_response(c) for c in clips]


@router.get("/clips/{clip_id}", response_model=ClipResponse)
async def get_clip(clip_id: int, db: AsyncSession = Depends(get_db)):
    """Get a clip by ID."""
    service = ClipService(db)
    clip = await service.get_clip(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return _clip_to_response(clip)


@router.patch("/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: int,
    data: ClipUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a clip's properties."""
    service = ClipService(db)
    try:
        clip = await service.update_clip(
            clip_id,
            start_time=data.start_time,
            end_time=data.end_time,
            name=data.name
        )
        return _clip_to_response(clip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/clips/{clip_id}")
async def delete_clip(clip_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a clip."""
    service = ClipService(db)
    if not await service.delete_clip(clip_id):
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"status": "deleted"}


# =============================================================================
# Compound Clips
# =============================================================================

@router.post("/projects/{project_id}/compound-clips", response_model=CompoundClipResponse)
async def create_compound_clip(
    project_id: int,
    data: CompoundClipCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a compound clip."""
    service = ClipService(db)
    try:
        items = [item.model_dump() for item in data.items]
        compound = await service.create_compound_clip(project_id, data.name, items)
        return _compound_to_response(compound)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/compound-clips", response_model=List[CompoundClipResponse])
async def list_compound_clips(project_id: int, db: AsyncSession = Depends(get_db)):
    """List compound clips for a project."""
    service = ClipService(db)
    compounds = await service.list_compound_clips(project_id)
    return [_compound_to_response(c) for c in compounds]


@router.get("/compound-clips/{compound_id}", response_model=CompoundClipResponse)
async def get_compound_clip(compound_id: int, db: AsyncSession = Depends(get_db)):
    """Get a compound clip by ID."""
    service = ClipService(db)
    compound = await service.get_compound_clip(compound_id)
    if not compound:
        raise HTTPException(status_code=404, detail="Compound clip not found")
    return _compound_to_response(compound)


@router.delete("/compound-clips/{compound_id}")
async def delete_compound_clip(compound_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a compound clip."""
    service = ClipService(db)
    if not await service.delete_compound_clip(compound_id):
        raise HTTPException(status_code=404, detail="Compound clip not found")
    return {"status": "deleted"}


# =============================================================================
# Exports
# =============================================================================

@router.post("/projects/{project_id}/exports", response_model=JobResponse)
async def export_clip(
    project_id: int,
    data: ExportClipRequest,
    db: AsyncSession = Depends(get_db)
):
    """Export a clip or compound clip."""
    service = ClipService(db)
    
    if data.clip_id and data.compound_clip_id:
        raise HTTPException(
            status_code=400,
            detail="Provide either clip_id or compound_clip_id, not both"
        )
    
    if not data.clip_id and not data.compound_clip_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide clip_id or compound_clip_id"
        )
    
    try:
        if data.compound_clip_id:
            job = await service.export_compound_clip(
                project_id,
                data.compound_clip_id,
                data.output_folder,
                data.filename
            )
        else:
            job = await service.export_clip(
                project_id,
                data.clip_id,
                data.output_folder,
                data.filename
            )
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/exports/batch", response_model=JobResponse)
async def export_batch(
    project_id: int,
    data: ExportBatchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Batch export multiple clips."""
    service = ClipService(db)
    try:
        job = await service.export_batch(
            project_id,
            data.clip_ids,
            data.output_folder
        )
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Jobs
# =============================================================================

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get job status."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.get("/projects/{project_id}/jobs", response_model=List[JobResponse])
async def list_jobs(project_id: int, db: AsyncSession = Depends(get_db)):
    """List jobs for a project."""
    result = await db.execute(
        select(Job)
        .where(Job.project_id == project_id)
        .order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    return [JobResponse.model_validate(j) for j in jobs]


# =============================================================================
# Static Files
# =============================================================================

@router.get("/projects/{project_id}/video")
async def get_project_video(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get the source video file for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.source_path:
        raise HTTPException(status_code=404, detail="No video file available")
    
    video_path = Path(project.source_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=video_path.name
    )


@router.get("/projects/{project_id}/thumbnails/{clip_id}")
async def get_thumbnail(
    project_id: int,
    clip_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a clip thumbnail."""
    clip = await db.get(Clip, clip_id)
    if not clip or clip.project_id != project_id:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    if not clip.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    
    thumb_path = Path(clip.thumbnail_path)
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found")
    
    return FileResponse(
        thumb_path,
        media_type=f"image/{settings.thumbnail_format}"
    )


# =============================================================================
# Helpers
# =============================================================================

async def _project_to_response(project: Project, db: AsyncSession) -> ProjectResponse:
    """Convert project model to response with clip count."""
    result = await db.execute(
        select(func.count(Clip.id)).where(Clip.project_id == project.id)
    )
    clip_count = result.scalar()
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at,
        source_type=project.source_type.value,
        source_url=project.source_url,
        source_path=project.source_path,
        duration=project.duration,
        width=project.width,
        height=project.height,
        fps=project.fps,
        video_codec=project.video_codec,
        audio_codec=project.audio_codec,
        status=project.status.value,
        error_message=project.error_message,
        output_folder=project.output_folder,
        clip_count=clip_count
    )


def _clip_to_response(clip: Clip) -> ClipResponse:
    """Convert clip model to response."""
    thumbnail_url = None
    if clip.thumbnail_path:
        thumbnail_url = f"/api/projects/{clip.project_id}/thumbnails/{clip.id}"
    
    return ClipResponse(
        id=clip.id,
        project_id=clip.project_id,
        start_time=clip.start_time,
        end_time=clip.end_time,
        duration=clip.duration,
        name=clip.name,
        thumbnail_path=clip.thumbnail_path,
        thumbnail_url=thumbnail_url,
        created_by=clip.created_by.value,
        ordering=clip.ordering,
        quality_score=clip.quality_score,
        anchor_time_sec=clip.anchor_time_sec,
        generation_version=clip.generation_version,
        created_at=clip.created_at
    )


def _compound_to_response(compound: CompoundClip) -> CompoundClipResponse:
    """Convert compound clip model to response."""
    from app.api.schemas import CompoundClipItemResponse
    
    items = []
    for item in sorted(compound.items, key=lambda x: x.ordering):
        items.append(CompoundClipItemResponse(
            id=item.id,
            clip_id=item.clip_id,
            start_time=item.start_time,
            end_time=item.end_time,
            duration=item.duration,
            ordering=item.ordering
        ))
    
    return CompoundClipResponse(
        id=compound.id,
        project_id=compound.project_id,
        name=compound.name,
        total_duration=compound.total_duration,
        items=items,
        created_at=compound.created_at
    )


# =============================================================================
# Niches
# =============================================================================

@router.post("/niches", response_model=NicheResponse)
async def create_niche(
    data: NicheCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new niche."""
    service = NicheService(db)
    try:
        niche = await service.create_niche(
            name=data.name,
            description=data.description,
            default_hashtags=data.default_hashtags,
            default_caption_template=data.default_caption_template,
            default_text_overlay=data.default_text_overlay,
            default_text_position=data.default_text_position,
            default_text_color=data.default_text_color,
            default_text_size=data.default_text_size,
            default_audio_path=data.default_audio_path,
            default_audio_volume=data.default_audio_volume,
        )
        return await _niche_to_response(niche, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/niches", response_model=List[NicheResponse])
async def list_niches(db: AsyncSession = Depends(get_db)):
    """List all niches."""
    service = NicheService(db)
    niches = await service.list_niches()
    return [await _niche_to_response(n, db) for n in niches]


@router.get("/niches/{niche_id}", response_model=NicheResponse)
async def get_niche(niche_id: int, db: AsyncSession = Depends(get_db)):
    """Get a niche by ID."""
    service = NicheService(db)
    niche = await service.get_niche(niche_id)
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found")
    return await _niche_to_response(niche, db)


@router.patch("/niches/{niche_id}", response_model=NicheResponse)
async def update_niche(
    niche_id: int,
    data: NicheUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a niche."""
    service = NicheService(db)
    try:
        niche = await service.update_niche(
            niche_id=niche_id,
            name=data.name,
            description=data.description,
            default_hashtags=data.default_hashtags,
            default_caption_template=data.default_caption_template,
            default_text_overlay=data.default_text_overlay,
            default_text_position=data.default_text_position,
            default_text_color=data.default_text_color,
            default_text_size=data.default_text_size,
            default_audio_path=data.default_audio_path,
            default_audio_volume=data.default_audio_volume,
        )
        return await _niche_to_response(niche, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/niches/{niche_id}")
async def delete_niche(niche_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a niche and all associated accounts."""
    service = NicheService(db)
    if not await service.delete_niche(niche_id):
        raise HTTPException(status_code=404, detail="Niche not found")
    return {"status": "deleted"}


# =============================================================================
# Accounts
# =============================================================================

@router.post("/accounts", response_model=AccountResponse)
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new account for a niche."""
    service = NicheService(db)
    try:
        account = await service.create_account(
            niche_id=data.niche_id,
            platform=data.platform,
            handle=data.handle,
            display_name=data.display_name,
            auto_upload=data.auto_upload,
        )
        return _account_to_response(account)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    niche_id: Optional[int] = Query(None, description="Filter by niche ID"),
    db: AsyncSession = Depends(get_db)
):
    """List all accounts, optionally filtered by niche."""
    service = NicheService(db)
    accounts = await service.list_accounts(niche_id)
    return [_account_to_response(a) for a in accounts]


@router.get("/niches/{niche_id}/accounts", response_model=List[AccountResponse])
async def list_niche_accounts(niche_id: int, db: AsyncSession = Depends(get_db)):
    """List all accounts for a specific niche."""
    service = NicheService(db)
    niche = await service.get_niche(niche_id)
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found")
    accounts = await service.list_accounts(niche_id)
    return [_account_to_response(a) for a in accounts]


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """Get an account by ID."""
    service = NicheService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return _account_to_response(account)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    data: AccountUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an account."""
    service = NicheService(db)
    try:
        account = await service.update_account(
            account_id=account_id,
            handle=data.handle,
            display_name=data.display_name,
            auto_upload=data.auto_upload,
        )
        return _account_to_response(account)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an account."""
    service = NicheService(db)
    if not await service.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "deleted"}


# =============================================================================
# Niche/Account Helpers
# =============================================================================

async def _niche_to_response(niche, db: AsyncSession) -> NicheResponse:
    """Convert niche model to response with account count."""
    import json
    from app.models.account import Account
    
    result = await db.execute(
        select(func.count(Account.id)).where(Account.niche_id == niche.id)
    )
    account_count = result.scalar()
    
    hashtags = []
    if niche.default_hashtags:
        try:
            hashtags = json.loads(niche.default_hashtags)
        except json.JSONDecodeError:
            hashtags = []
    
    return NicheResponse(
        id=niche.id,
        name=niche.name,
        description=niche.description,
        default_hashtags=hashtags,
        default_caption_template=niche.default_caption_template,
        default_text_overlay=niche.default_text_overlay,
        default_text_position=niche.default_text_position,
        default_text_color=niche.default_text_color,
        default_text_size=niche.default_text_size,
        default_audio_path=niche.default_audio_path,
        default_audio_volume=niche.default_audio_volume,
        account_count=account_count,
        created_at=niche.created_at,
        updated_at=niche.updated_at,
    )


def _account_to_response(account) -> AccountResponse:
    """Convert account model to response."""
    return AccountResponse(
        id=account.id,
        niche_id=account.niche_id,
        platform=account.platform.value,
        handle=account.handle,
        display_name=account.display_name,
        auth_status=account.auth_status.value,
        platform_user_id=account.platform_user_id,
        youtube_channel_id=account.platform_user_id if account.platform.value == "youtube_shorts" else None,
        youtube_channel_title=account.display_name if account.platform.value == "youtube_shorts" else None,
        auto_upload=account.auto_upload,
        created_at=account.created_at,
        updated_at=account.updated_at,
        last_upload_at=account.last_upload_at,
    )


# =============================================================================
# Publish
# =============================================================================

@router.post("/projects/{project_id}/publish", response_model=JobResponse)
async def publish_clip(
    project_id: int,
    data: PublishRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Publish a clip to multiple platforms.
    
    Creates exports for each platform with appropriate formatting
    and generates metadata.json files for each export.
    """
    service = PublishService(db)
    try:
        # Create the publish job
        job = await service.create_publish_job(
            project_id=project_id,
            clip_id=data.clip_id,
            niche_id=data.niche_id,
            account_ids=data.account_ids,
            output_base_folder=data.output_folder,
            caption=data.caption,
            hashtags=data.hashtags,
            text_overlay_text=data.text_overlay.text if data.text_overlay else None,
            text_overlay_position=data.text_overlay.position if data.text_overlay else "bottom",
            text_overlay_color=data.text_overlay.color if data.text_overlay else "#FFFFFF",
            text_overlay_size=data.text_overlay.size if data.text_overlay else 48,
            background_audio_path=data.audio_overlay.path if data.audio_overlay else None,
            background_audio_volume=data.audio_overlay.volume if data.audio_overlay else 30,
            original_audio_volume=data.audio_overlay.original_volume if data.audio_overlay else 100,
            use_vertical_preset=data.use_vertical_preset,
            vertical_framing=data.vertical_framing,
            vertical_resolution=data.vertical_resolution,
        )
        
        # Execute the job in background (for now, run synchronously)
        # In production, this would be queued to a background worker
        from app.workers.handlers import run_publish_job
        import asyncio
        asyncio.create_task(run_publish_job(job.id))
        
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/platforms", response_model=List[str])
async def list_platforms():
    """List all supported platforms."""
    from app.models.account import Platform
    return [p.value for p in Platform]


@router.get("/platforms/{platform}/specs", response_model=PlatformSpecsResponse)
async def get_platform_specs(
    platform: str,
    db: AsyncSession = Depends(get_db)
):
    """Get specifications and requirements for a platform."""
    service = PublishService(db)
    try:
        specs = await service.get_platform_requirements(platform)
        return PlatformSpecsResponse(**specs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/clips/{clip_id}/validate-platforms")
async def validate_clip_for_platforms(
    clip_id: int,
    platforms: List[str] = Query(..., description="Platform names to validate against"),
    db: AsyncSession = Depends(get_db)
):
    """Validate if a clip meets requirements for target platforms."""
    service = PublishService(db)
    try:
        results = await service.validate_clip_for_platforms(clip_id, platforms)
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Upload / Direct Platform Upload
# =============================================================================

@router.post("/projects/{project_id}/upload", response_model=JobResponse)
async def upload_video(
    project_id: int,
    data: UploadRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a video directly to a platform.
    
    Currently supports YouTube Shorts with OAuth.
    Other platforms return export-only guidance.
    """
    service = UploadService(db)
    try:
        job = await service.create_upload_job(
            project_id=project_id,
            video_path=data.video_path,
            account_id=data.account_id,
            title=data.title,
            description=data.description,
            tags=data.tags,
            privacy_status=data.privacy_status,
        )
        
        # Execute upload in background
        from app.workers.handlers import run_upload_job
        import asyncio
        asyncio.create_task(run_upload_job(job.id))
        
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/upload-selected", response_model=UploadSelectedResponse)
async def upload_selected_clips(
    project_id: int,
    data: UploadSelectedRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create one direct-upload job per selected clip for YouTube."""
    service = UploadService(db)
    try:
        result = await service.upload_selected_clips(
            project_id=project_id,
            clip_ids=data.clip_ids,
            account_id=data.account_id,
            niche_id=data.niche_id,
            privacy_status=data.privacy_status,
            title_prefix=data.title_prefix,
            description_template=data.description_template,
            hashtags=data.hashtags,
            use_vertical_preset=data.use_vertical_preset,
            vertical_framing=data.vertical_framing,
            vertical_resolution=data.vertical_resolution,
        )
        return UploadSelectedResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OAuthUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/accounts/{account_id}/oauth-url", response_model=OAuthUrlResponse)
async def get_oauth_url(
    account_id: int,
    redirect_uri: str = Query(..., description="OAuth redirect URI"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get OAuth URL for connecting a platform account.
    
    Redirect user to this URL to authorize the application.
    """
    service = UploadService(db)
    try:
        result = await service.get_oauth_url(account_id, redirect_uri)
        return OAuthUrlResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/accounts/{account_id}/oauth-callback")
async def oauth_callback(
    account_id: int,
    data: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Complete OAuth flow with authorization code.
    
    Called after user authorizes the application.
    """
    service = UploadService(db)
    try:
        result = await service.complete_oauth(
            account_id=account_id,
            authorization_code=data.code,
            redirect_uri=data.redirect_uri,
        )
        if result["status"] == "connected":
            payload = OAuthCallbackConnectedResponse(
                account=_account_to_response(result["account"])
            )
            return payload

        payload = OAuthCallbackSelectionRequiredResponse(
            account_id=result["account_id"],
            selection_token=result["selection_token"],
            channels=result["channels"],
        )
        return JSONResponse(status_code=202, content=payload.model_dump())
    except OAuthUpstreamError as e:
        logger.warning(
            "OAuth callback upstream error for account_id=%s: %s",
            account_id,
            e,
        )
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/accounts/{account_id}/youtube-channels/pending", response_model=YouTubePendingChannelsResponse)
async def get_pending_youtube_channels(
    account_id: int,
    selection_token: str = Query(..., description="Pending channel selection token"),
    db: AsyncSession = Depends(get_db)
):
    """Get pending channel options after OAuth callback selection_required response."""
    service = UploadService(db)
    try:
        result = await service.get_pending_youtube_channels(account_id, selection_token)
        return YouTubePendingChannelsResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/accounts/{account_id}/youtube-channel-selection", response_model=AccountResponse)
async def finalize_youtube_channel_selection(
    account_id: int,
    data: YouTubeChannelSelectionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Finalize selected YouTube channel and connect account."""
    service = UploadService(db)
    try:
        account = await service.finalize_youtube_channel_selection(
            account_id=account_id,
            selection_token=data.selection_token,
            channel_id=data.channel_id,
        )
        return _account_to_response(account)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
