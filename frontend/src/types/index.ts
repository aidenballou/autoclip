// Project types
export interface Project {
  id: number
  name: string
  created_at: string
  updated_at: string
  source_type: 'youtube' | 'local'
  source_url: string | null
  source_path: string | null
  duration: number | null
  width: number | null
  height: number | null
  fps: number | null
  video_codec: string | null
  audio_codec: string | null
  status: ProjectStatus
  error_message: string | null
  output_folder: string | null
  clip_count: number | null
}

export type ProjectStatus = 
  | 'pending'
  | 'downloading'
  | 'downloaded'
  | 'analyzing'
  | 'ready'
  | 'error'

// Clip types
export interface Clip {
  id: number
  project_id: number
  start_time: number
  end_time: number
  duration: number
  name: string | null
  thumbnail_path: string | null
  thumbnail_url: string | null
  created_by: 'auto' | 'manual'
  ordering: number
  quality_score: number | null
  anchor_time_sec: number | null
  generation_version: string | null
  created_at: string
}

// Segmentation mode type
export type SegmentationMode = 'v1' | 'v2'

// Compound clip types
export interface CompoundClipItem {
  id: number
  clip_id: number
  start_time: number
  end_time: number
  duration: number
  ordering: number
}

export interface CompoundClip {
  id: number
  project_id: number
  name: string
  total_duration: number
  items: CompoundClipItem[]
  created_at: string
}

// Job types
export interface Job {
  id: number
  project_id: number
  job_type: JobType
  status: JobStatus
  progress: number
  message: string | null
  result: string | null
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export type JobType = 
  | 'download'
  | 'analyze'
  | 'thumbnail'
  | 'export'
  | 'export_batch'

export type JobStatus = 
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

// Health check types
export interface HealthResponse {
  status: string
  ffmpeg_available: boolean
  ffprobe_available: boolean
  ytdlp_available: boolean
  message: string | null
}

export interface DependencyCheck {
  name: string
  available: boolean
  path: string | null
  version: string | null
  install_command: string | null
}

// API request/response types
export interface CreateProjectYoutubeRequest {
  youtube_url: string
  name?: string
}

export interface CreateProjectLocalRequest {
  file_path: string
  name?: string
  copy_file?: boolean
}

export interface UpdateClipRequest {
  start_time?: number
  end_time?: number
  name?: string
}

export interface CreateCompoundClipRequest {
  name: string
  items: {
    clip_id: number
    start_override?: number
    end_override?: number
  }[]
}

export interface ExportRequest {
  clip_id?: number
  compound_clip_id?: number
  output_folder?: string
  filename?: string
}

export interface ExportBatchRequest {
  clip_ids: number[]
  output_folder?: string
}

export interface ValidateFolderResponse {
  valid: boolean
  path: string
  message: string | null
}

// Niche types
export interface Niche {
  id: number
  name: string
  description: string | null
  default_hashtags: string[]
  default_caption_template: string | null
  default_text_overlay: string | null
  default_text_position: string
  default_text_color: string
  default_text_size: number
  default_audio_path: string | null
  default_audio_volume: number
  account_count: number | null
  created_at: string
  updated_at: string
}

export interface CreateNicheRequest {
  name: string
  description?: string
  default_hashtags?: string[]
  default_caption_template?: string
  default_text_overlay?: string
  default_text_position?: string
  default_text_color?: string
  default_text_size?: number
  default_audio_path?: string
  default_audio_volume?: number
}

export interface UpdateNicheRequest {
  name?: string
  description?: string
  default_hashtags?: string[]
  default_caption_template?: string
  default_text_overlay?: string
  default_text_position?: string
  default_text_color?: string
  default_text_size?: number
  default_audio_path?: string
  default_audio_volume?: number
}

// Account types
export type Platform = 
  | 'youtube_shorts'
  | 'tiktok'
  | 'instagram_reels'
  | 'twitter'
  | 'snapchat'

export type AuthStatus = 
  | 'not_connected'
  | 'connected'
  | 'expired'
  | 'error'

export interface Account {
  id: number
  niche_id: number
  platform: Platform
  handle: string
  display_name: string | null
  auth_status: AuthStatus
  platform_user_id: string | null
  youtube_channel_id?: string | null
  youtube_channel_title?: string | null
  auto_upload: boolean
  created_at: string
  updated_at: string
  last_upload_at: string | null
}

export interface CreateAccountRequest {
  niche_id: number
  platform: Platform
  handle: string
  display_name?: string
  auto_upload?: boolean
}

export interface UpdateAccountRequest {
  handle?: string
  display_name?: string
  auto_upload?: boolean
}

// Publish types
export type VerticalFramingMode = 'fit' | 'fill' | 'blur'
export type VerticalResolutionMode = 'fixed_1080' | 'limit_upscale' | 'match_source'

export interface TextOverlaySettings {
  text: string
  position: 'top' | 'center' | 'bottom'
  color: string
  size: number
}

export interface AudioOverlaySettings {
  path: string
  volume: number
  original_volume: number
}

export interface PublishRequest {
  clip_id: number
  niche_id: number
  account_ids: number[]
  output_folder: string
  caption?: string
  hashtags?: string[]
  text_overlay?: TextOverlaySettings
  audio_overlay?: AudioOverlaySettings
  use_vertical_preset?: boolean
  vertical_framing?: VerticalFramingMode
  vertical_resolution?: VerticalResolutionMode
}

export interface PublishExportResult {
  platform: string
  video_path: string
  metadata_path: string
  accounts: string[]
}

export interface PublishErrorResult {
  platform: string
  error: string
}

export interface PublishResult {
  exports: PublishExportResult[]
  errors: PublishErrorResult[]
}

// Upload types
export interface UploadRequest {
  video_path: string
  account_id: number
  title: string
  description: string
  tags?: string[]
  privacy_status?: 'private' | 'public' | 'unlisted'
}

export interface UploadResult {
  success: boolean
  platform: string
  account_id: number
  video_id: string | null
  video_url: string | null
  error: string | null
}

export interface OAuthUrlResponse {
  url: string
  platform: string
}

export interface YouTubeChannelOption {
  channel_id: string
  title: string
  handle: string
}

export interface OAuthConnectedResponse {
  status: 'connected'
  account: Account
}

export interface OAuthSelectionRequiredResponse {
  status: 'selection_required'
  account_id: number
  selection_token: string
  channels: YouTubeChannelOption[]
}

export type OAuthCallbackResult = OAuthConnectedResponse | OAuthSelectionRequiredResponse

export interface YouTubePendingChannelsResponse {
  account_id: number
  selection_token: string
  channels: YouTubeChannelOption[]
}

export interface UploadSelectedRequest {
  clip_ids: number[]
  account_id: number
  niche_id: number
  privacy_status?: 'private' | 'public' | 'unlisted'
  title_prefix?: string
  description_template?: string
  hashtags?: string[]
  use_vertical_preset?: boolean
  vertical_framing?: VerticalFramingMode
  vertical_resolution?: VerticalResolutionMode
}

export interface UploadSelectedJobItem {
  job_id: number
  clip_id: number
  clip_name: string
}

export interface UploadSelectedErrorItem {
  clip_id: number
  error: string
}

export interface UploadSelectedResponse {
  jobs: UploadSelectedJobItem[]
  errors: UploadSelectedErrorItem[]
}

// Platform specs
export interface PlatformSpecs {
  max_duration: number | null
  min_duration: number | null
  aspect_ratio: string | null
  max_file_size_mb: number | null
  recommended_resolution: [number, number] | null
  formats: string[] | null
}
