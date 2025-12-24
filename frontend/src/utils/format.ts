/**
 * Format seconds to MM:SS or HH:MM:SS
 */
export function formatDuration(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '0:00'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

/**
 * Format seconds to precise timestamp with decimals
 */
export function formatTimestamp(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '0:00.00'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = (seconds % 60).toFixed(2)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.padStart(5, '0')}`
  }
  return `${minutes}:${secs.padStart(5, '0')}`
}

/**
 * Format bytes to human readable size
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${units[i]}`
}

/**
 * Format date to relative time
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)
  
  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString()
}

/**
 * Format resolution
 */
export function formatResolution(width: number | null, height: number | null): string {
  if (!width || !height) return 'Unknown'
  return `${width}×${height}`
}

/**
 * Get status color class
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case 'ready':
    case 'completed':
      return 'text-clip-success'
    case 'downloading':
    case 'analyzing':
    case 'running':
    case 'pending':
      return 'text-clip-warning'
    case 'error':
    case 'failed':
      return 'text-clip-error'
    default:
      return 'text-gray-400'
  }
}

/**
 * Get status background color class
 */
export function getStatusBgColor(status: string): string {
  switch (status) {
    case 'ready':
    case 'completed':
      return 'bg-clip-success/20 text-clip-success'
    case 'downloading':
    case 'analyzing':
    case 'running':
    case 'pending':
      return 'bg-clip-warning/20 text-clip-warning'
    case 'error':
    case 'failed':
      return 'bg-clip-error/20 text-clip-error'
    default:
      return 'bg-gray-500/20 text-gray-400'
  }
}

