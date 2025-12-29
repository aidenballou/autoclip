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

