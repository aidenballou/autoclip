import axios from 'axios'
import type {
  Project,
  Clip,
  CompoundClip,
  Job,
  HealthResponse,
  DependencyCheck,
  CreateProjectYoutubeRequest,
  CreateProjectLocalRequest,
  UpdateClipRequest,
  CreateCompoundClipRequest,
  ExportRequest,
  ExportBatchRequest,
  ValidateFolderResponse,
  Niche,
  CreateNicheRequest,
  UpdateNicheRequest,
  Account,
  CreateAccountRequest,
  UpdateAccountRequest,
  PublishRequest,
  OAuthUrlResponse,
  OAuthCallbackResult,
  YouTubePendingChannelsResponse,
  PlatformSpecs,
  UploadSelectedRequest,
  UploadSelectedResponse,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Health & System
export const getHealth = async (): Promise<HealthResponse> => {
  const { data } = await api.get('/health')
  return data
}

export const getDependencies = async (): Promise<DependencyCheck[]> => {
  const { data } = await api.get('/dependencies')
  return data
}

// Projects
export const getProjects = async (): Promise<Project[]> => {
  const { data } = await api.get('/projects')
  return data
}

export const getProject = async (id: number): Promise<Project> => {
  const { data } = await api.get(`/projects/${id}`)
  return data
}

export const createProjectYoutube = async (
  request: CreateProjectYoutubeRequest
): Promise<Project> => {
  const { data } = await api.post('/projects/youtube', request)
  return data
}

export const createProjectLocal = async (
  request: CreateProjectLocalRequest
): Promise<Project> => {
  const { data } = await api.post('/projects/local', request)
  return data
}

export const uploadProject = async (
  file: File,
  name?: string
): Promise<Project> => {
  const formData = new FormData()
  formData.append('file', file)
  if (name) {
    formData.append('name', name)
  }
  const { data } = await api.post('/projects/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const deleteProject = async (id: number): Promise<void> => {
  await api.delete(`/projects/${id}`)
}

export const startDownload = async (projectId: number): Promise<Job> => {
  const { data } = await api.post(`/projects/${projectId}/download`)
  return data
}

export const startAnalysis = async (
  projectId: number,
  segmentationMode?: 'v1' | 'v2'
): Promise<Job> => {
  const params = segmentationMode ? { segmentation_mode: segmentationMode } : {}
  const { data } = await api.post(`/projects/${projectId}/analyze`, null, { params })
  return data
}

export const setOutputFolder = async (
  projectId: number,
  folderPath: string
): Promise<Project> => {
  const { data } = await api.post(`/projects/${projectId}/output-folder`, {
    folder_path: folderPath,
  })
  return data
}

export const validateFolder = async (
  folderPath: string
): Promise<ValidateFolderResponse> => {
  const { data } = await api.post('/validate-folder', {
    folder_path: folderPath,
  })
  return data
}

// Clips
export const getClips = async (projectId: number): Promise<Clip[]> => {
  const { data } = await api.get(`/projects/${projectId}/clips`)
  return data
}

export const getClip = async (clipId: number): Promise<Clip> => {
  const { data } = await api.get(`/clips/${clipId}`)
  return data
}

export const updateClip = async (
  clipId: number,
  request: UpdateClipRequest
): Promise<Clip> => {
  const { data } = await api.patch(`/clips/${clipId}`, request)
  return data
}

export const deleteClip = async (clipId: number): Promise<void> => {
  await api.delete(`/clips/${clipId}`)
}

// Compound Clips
export const getCompoundClips = async (
  projectId: number
): Promise<CompoundClip[]> => {
  const { data } = await api.get(`/projects/${projectId}/compound-clips`)
  return data
}

export const createCompoundClip = async (
  projectId: number,
  request: CreateCompoundClipRequest
): Promise<CompoundClip> => {
  const { data } = await api.post(
    `/projects/${projectId}/compound-clips`,
    request
  )
  return data
}

export const deleteCompoundClip = async (compoundId: number): Promise<void> => {
  await api.delete(`/compound-clips/${compoundId}`)
}

// Exports
export const exportClip = async (
  projectId: number,
  request: ExportRequest
): Promise<Job> => {
  const { data } = await api.post(`/projects/${projectId}/exports`, request)
  return data
}

export const exportBatch = async (
  projectId: number,
  request: ExportBatchRequest
): Promise<Job> => {
  const { data } = await api.post(`/projects/${projectId}/exports/batch`, request)
  return data
}

// Jobs
export const getJob = async (jobId: number): Promise<Job> => {
  const { data } = await api.get(`/jobs/${jobId}`)
  return data
}

export const getProjectJobs = async (projectId: number): Promise<Job[]> => {
  const { data } = await api.get(`/projects/${projectId}/jobs`)
  return data
}

// Video URL helpers
export const getVideoUrl = (projectId: number): string => {
  return `/api/projects/${projectId}/video`
}

export const getThumbnailUrl = (projectId: number, clipId: number): string => {
  return `/api/projects/${projectId}/thumbnails/${clipId}`
}

// Niches
export const getNiches = async (): Promise<Niche[]> => {
  const { data } = await api.get('/niches')
  return data
}

export const getNiche = async (id: number): Promise<Niche> => {
  const { data } = await api.get(`/niches/${id}`)
  return data
}

export const createNiche = async (request: CreateNicheRequest): Promise<Niche> => {
  const { data } = await api.post('/niches', request)
  return data
}

export const updateNiche = async (
  id: number,
  request: UpdateNicheRequest
): Promise<Niche> => {
  const { data } = await api.patch(`/niches/${id}`, request)
  return data
}

export const deleteNiche = async (id: number): Promise<void> => {
  await api.delete(`/niches/${id}`)
}

// Accounts
export const getAccounts = async (nicheId?: number): Promise<Account[]> => {
  const params = nicheId ? { niche_id: nicheId } : {}
  const { data } = await api.get('/accounts', { params })
  return data
}

export const getNicheAccounts = async (nicheId: number): Promise<Account[]> => {
  const { data } = await api.get(`/niches/${nicheId}/accounts`)
  return data
}

export const getAccount = async (id: number): Promise<Account> => {
  const { data } = await api.get(`/accounts/${id}`)
  return data
}

export const createAccount = async (request: CreateAccountRequest): Promise<Account> => {
  const { data } = await api.post('/accounts', request)
  return data
}

export const updateAccount = async (
  id: number,
  request: UpdateAccountRequest
): Promise<Account> => {
  const { data } = await api.patch(`/accounts/${id}`, request)
  return data
}

export const deleteAccount = async (id: number): Promise<void> => {
  await api.delete(`/accounts/${id}`)
}

export const getOAuthUrl = async (
  accountId: number,
  redirectUri: string
): Promise<OAuthUrlResponse> => {
  const { data } = await api.get(`/accounts/${accountId}/oauth-url`, {
    params: { redirect_uri: redirectUri },
  })
  return data
}

export const completeOAuth = async (
  accountId: number,
  code: string,
  redirectUri: string
): Promise<OAuthCallbackResult> => {
  const { data } = await api.post(`/accounts/${accountId}/oauth-callback`, {
    code,
    redirect_uri: redirectUri,
  })
  return data
}

export const getPendingYouTubeChannels = async (
  accountId: number,
  selectionToken: string
): Promise<YouTubePendingChannelsResponse> => {
  const { data } = await api.get(`/accounts/${accountId}/youtube-channels/pending`, {
    params: { selection_token: selectionToken },
  })
  return data
}

export const finalizeYouTubeChannelSelection = async (
  accountId: number,
  selectionToken: string,
  channelId: string
): Promise<Account> => {
  const { data } = await api.post(`/accounts/${accountId}/youtube-channel-selection`, {
    selection_token: selectionToken,
    channel_id: channelId,
  })
  return data
}

// Publish
export const publishClip = async (
  projectId: number,
  request: PublishRequest
): Promise<Job> => {
  const { data } = await api.post(`/projects/${projectId}/publish`, request)
  return data
}

export const uploadSelectedClips = async (
  projectId: number,
  request: UploadSelectedRequest
): Promise<UploadSelectedResponse> => {
  const { data } = await api.post(`/projects/${projectId}/upload-selected`, request)
  return data
}

export const getPlatforms = async (): Promise<string[]> => {
  const { data } = await api.get('/platforms')
  return data
}

export const getPlatformSpecs = async (platform: string): Promise<PlatformSpecs> => {
  const { data } = await api.get(`/platforms/${platform}/specs`)
  return data
}

export const validateClipForPlatforms = async (
  clipId: number,
  platforms: string[]
): Promise<Record<string, { valid: boolean; issues: string[]; warnings: string[] }>> => {
  const { data } = await api.post(`/clips/${clipId}/validate-platforms`, null, {
    params: { platforms },
  })
  return data
}
