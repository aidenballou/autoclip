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
    quality_score: Optional[float] = None
    anchor_time_sec: Optional[float] = None
    generation_version: Optional[str] = None
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
# Analysis Schemas
# =============================================================================

class AnalyzeRequest(BaseModel):
    """Request to analyze a video."""
    segmentation_mode: Optional[str] = Field(
        None, 
        description="Segmentation mode: 'v1' (scene-based) or 'v2' (highlight-aware). Uses config default if not specified."
    )


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


# =============================================================================
# Niche Schemas
# =============================================================================

class NicheCreate(BaseModel):
    """Request to create a niche."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    default_hashtags: Optional[List[str]] = None
    default_caption_template: Optional[str] = None
    default_text_overlay: Optional[str] = None
    default_text_position: Optional[str] = Field(None, pattern="^(top|center|bottom)$")
    default_text_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    default_text_size: Optional[int] = Field(None, ge=12, le=200)
    default_audio_path: Optional[str] = None
    default_audio_volume: Optional[int] = Field(None, ge=0, le=100)


class NicheUpdate(BaseModel):
    """Request to update a niche."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    default_hashtags: Optional[List[str]] = None
    default_caption_template: Optional[str] = None
    default_text_overlay: Optional[str] = None
    default_text_position: Optional[str] = Field(None, pattern="^(top|center|bottom)$")
    default_text_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    default_text_size: Optional[int] = Field(None, ge=12, le=200)
    default_audio_path: Optional[str] = None
    default_audio_volume: Optional[int] = Field(None, ge=0, le=100)


class NicheResponse(BaseModel):
    """Niche response."""
    id: int
    name: str
    description: Optional[str]
    default_hashtags: List[str]
    default_caption_template: Optional[str]
    default_text_overlay: Optional[str]
    default_text_position: str
    default_text_color: str
    default_text_size: int
    default_audio_path: Optional[str]
    default_audio_volume: int
    account_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# Account Schemas
# =============================================================================

class AccountCreate(BaseModel):
    """Request to create an account."""
    niche_id: int
    platform: str = Field(..., description="Platform: youtube_shorts, tiktok, instagram_reels, twitter, snapchat")
    handle: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = None
    auto_upload: bool = False


class AccountUpdate(BaseModel):
    """Request to update an account."""
    handle: Optional[str] = Field(None, min_length=1, max_length=255)
    display_name: Optional[str] = None
    auto_upload: Optional[bool] = None


class AccountResponse(BaseModel):
    """Account response."""
    id: int
    niche_id: int
    platform: str
    handle: str
    display_name: Optional[str]
    auth_status: str
    platform_user_id: Optional[str]
    youtube_channel_id: Optional[str] = None
    youtube_channel_title: Optional[str] = None
    auto_upload: bool
    created_at: datetime
    updated_at: datetime
    last_upload_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AccountAuthRequest(BaseModel):
    """Request to authenticate an account (for OAuth callback)."""
    code: str = Field(..., description="OAuth authorization code")
    redirect_uri: Optional[str] = None


# =============================================================================
# Publish Schemas
# =============================================================================

class TextOverlaySettings(BaseModel):
    """Text overlay settings for publish."""
    text: str = Field(..., min_length=1)
    position: str = Field("bottom", pattern="^(top|center|bottom)$")
    color: str = Field("#FFFFFF", pattern="^#[0-9A-Fa-f]{6}$")
    size: int = Field(48, ge=12, le=200)


class AudioOverlaySettings(BaseModel):
    """Audio overlay settings for publish."""
    path: str = Field(..., description="Path to background audio file")
    volume: int = Field(30, ge=0, le=100, description="Background audio volume (0-100)")
    original_volume: int = Field(100, ge=0, le=100, description="Original audio volume (0-100)")


class PublishRequest(BaseModel):
    """Request to publish a clip to multiple platforms."""
    clip_id: int
    niche_id: int
    account_ids: List[int] = Field(..., min_length=1)
    output_folder: str = Field(..., description="Base folder for exports")
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    text_overlay: Optional[TextOverlaySettings] = None
    audio_overlay: Optional[AudioOverlaySettings] = None
    use_vertical_preset: bool = Field(True, description="Use 9:16 vertical format")
    vertical_framing: str = Field("fill", pattern="^(fit|fill|blur)$")
    vertical_resolution: str = Field("limit_upscale", pattern="^(fixed_1080|limit_upscale|match_source)$")


class PublishExportResult(BaseModel):
    """Result for a single platform export."""
    platform: str
    video_path: str
    metadata_path: str
    accounts: List[str]


class PublishErrorResult(BaseModel):
    """Error for a single platform export."""
    platform: str
    error: str


class PublishResultResponse(BaseModel):
    """Response with publish job results."""
    exports: List[PublishExportResult]
    errors: List[PublishErrorResult]


class PlatformSpecsResponse(BaseModel):
    """Platform specifications."""
    max_duration: Optional[int] = None
    min_duration: Optional[float] = None
    aspect_ratio: Optional[str] = None
    max_file_size_mb: Optional[int] = None
    recommended_resolution: Optional[List[int]] = None
    formats: Optional[List[str]] = None


class ClipValidationResult(BaseModel):
    """Validation result for a clip against a platform."""
    valid: bool
    issues: List[str]
    warnings: List[str]
    specs: PlatformSpecsResponse


# =============================================================================
# Upload Schemas
# =============================================================================

class UploadRequest(BaseModel):
    """Request to upload a video to a platform."""
    video_path: str = Field(..., description="Path to video file")
    account_id: int
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=5000)
    tags: Optional[List[str]] = None
    privacy_status: str = Field("private", pattern="^(private|public|unlisted)$")


class UploadResultResponse(BaseModel):
    """Response for upload result."""
    success: bool
    platform: str
    account_id: int
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None


class OAuthUrlResponse(BaseModel):
    """Response with OAuth URL."""
    url: str
    platform: str


class OAuthCallbackRequest(BaseModel):
    """Request for OAuth callback."""
    code: str = Field(..., description="Authorization code from OAuth provider")
    redirect_uri: str = Field(..., description="Redirect URI used in OAuth flow")


class YouTubeChannelOption(BaseModel):
    """YouTube channel option returned after OAuth callback."""
    channel_id: str
    title: str
    handle: str


class OAuthCallbackConnectedResponse(BaseModel):
    """OAuth callback response when account is fully connected."""
    status: str = "connected"
    account: AccountResponse


class OAuthCallbackSelectionRequiredResponse(BaseModel):
    """OAuth callback response when user must pick a channel."""
    status: str = "selection_required"
    account_id: int
    selection_token: str
    channels: List[YouTubeChannelOption]


class YouTubeChannelSelectionRequest(BaseModel):
    """Finalize selected YouTube channel for a pending OAuth session."""
    selection_token: str
    channel_id: str


class YouTubePendingChannelsResponse(BaseModel):
    """Pending selectable channels for an account."""
    account_id: int
    selection_token: str
    channels: List[YouTubeChannelOption]


class UploadSelectedRequest(BaseModel):
    """Request to upload selected clips directly to YouTube."""
    clip_ids: List[int] = Field(..., min_length=1)
    account_id: int
    niche_id: int
    privacy_status: str = Field("private", pattern="^(private|public|unlisted)$")
    title_prefix: Optional[str] = None
    description_template: Optional[str] = None
    hashtags: Optional[List[str]] = None
    use_vertical_preset: bool = Field(True, description="Use 9:16 vertical format")
    vertical_framing: str = Field("fill", pattern="^(fit|fill|blur)$")
    vertical_resolution: str = Field("limit_upscale", pattern="^(fixed_1080|limit_upscale|match_source)$")


class UploadSelectedJobItem(BaseModel):
    """Result item for a queued upload job."""
    job_id: int
    clip_id: int
    clip_name: str


class UploadSelectedErrorItem(BaseModel):
    """Result item for skipped/failed clip enqueue."""
    clip_id: int
    error: str


class UploadSelectedResponse(BaseModel):
    """Batch upload-selected response."""
    jobs: List[UploadSelectedJobItem]
    errors: List[UploadSelectedErrorItem]
