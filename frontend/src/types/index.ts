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

