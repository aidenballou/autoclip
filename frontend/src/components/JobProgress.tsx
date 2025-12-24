import { useEffect } from 'react'
import { Loader2, CheckCircle2, XCircle, AlertCircle } from 'lucide-react'
import type { Job } from '../types'
import { ProgressBar } from './ProgressBar'
import clsx from 'clsx'

interface JobProgressProps {
  job: Job | null
  showDetails?: boolean
  className?: string
}

export function JobProgress({ job, showDetails = true, className }: JobProgressProps) {
  if (!job) return null

  const statusConfig = {
    pending: {
      icon: <Loader2 className="w-5 h-5 animate-spin text-gray-400" />,
      label: 'Pending',
      color: 'text-gray-400',
    },
    running: {
      icon: <Loader2 className="w-5 h-5 animate-spin text-clip-accent" />,
      label: 'Running',
      color: 'text-clip-accent',
    },
    completed: {
      icon: <CheckCircle2 className="w-5 h-5 text-clip-success" />,
      label: 'Completed',
      color: 'text-clip-success',
    },
    failed: {
      icon: <XCircle className="w-5 h-5 text-clip-error" />,
      label: 'Failed',
      color: 'text-clip-error',
    },
    cancelled: {
      icon: <AlertCircle className="w-5 h-5 text-gray-500" />,
      label: 'Cancelled',
      color: 'text-gray-500',
    },
  }

  const config = statusConfig[job.status]
  const isActive = job.status === 'pending' || job.status === 'running'

  return (
    <div className={clsx('bg-clip-elevated rounded-lg p-4', className)}>
      <div className="flex items-center gap-3">
        {config.icon}
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <span className={clsx('text-sm font-medium', config.color)}>
              {job.job_type.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </span>
            <span className="text-xs text-gray-500">{config.label}</span>
          </div>
          {job.message && (
            <p className="text-xs text-gray-400 mt-0.5 truncate">{job.message}</p>
          )}
        </div>
      </div>

      {isActive && (
        <div className="mt-3">
          <ProgressBar 
            progress={job.progress} 
            variant={job.status === 'running' ? 'default' : 'warning'}
          />
        </div>
      )}

      {showDetails && job.status === 'failed' && job.error && (
        <div className="mt-3 p-2 bg-clip-error/10 rounded text-xs text-clip-error font-mono overflow-auto max-h-32">
          {job.error}
        </div>
      )}

      {showDetails && job.status === 'completed' && job.result && (
        <div className="mt-3 text-xs text-gray-400">
          {(() => {
            try {
              const result = JSON.parse(job.result)
              if (result.clip_count) {
                return `Generated ${result.clip_count} clips`
              }
              if (result.exported_count) {
                return `Exported ${result.exported_count} clips`
              }
              if (result.output_path) {
                return `Saved to: ${result.output_path}`
              }
              return null
            } catch {
              return null
            }
          })()}
        </div>
      )}
    </div>
  )
}

