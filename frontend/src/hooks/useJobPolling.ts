import { useEffect, useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getJob } from '../api/client'
import type { Job, JobStatus } from '../types'

interface UseJobPollingOptions {
  jobId: number | null
  onComplete?: (job: Job) => void
  onError?: (job: Job) => void
  pollInterval?: number
}

export function useJobPolling({
  jobId,
  onComplete,
  onError,
  pollInterval = 1000,
}: UseJobPollingOptions) {
  const queryClient = useQueryClient()
  const [job, setJob] = useState<Job | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const intervalRef = useRef<number | null>(null)
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)

  // Keep callback refs up to date
  useEffect(() => {
    onCompleteRef.current = onComplete
    onErrorRef.current = onError
  }, [onComplete, onError])

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const poll = useCallback(async () => {
    if (!jobId) return

    try {
      const updatedJob = await getJob(jobId)
      setJob(updatedJob)

      const terminalStatuses: JobStatus[] = ['completed', 'failed', 'cancelled']
      if (terminalStatuses.includes(updatedJob.status)) {
        stopPolling()

        // Invalidate relevant queries
        queryClient.invalidateQueries({ queryKey: ['project', updatedJob.project_id] })
        queryClient.invalidateQueries({ queryKey: ['clips', updatedJob.project_id] })

        if (updatedJob.status === 'completed') {
          onCompleteRef.current?.(updatedJob)
        } else if (updatedJob.status === 'failed') {
          onErrorRef.current?.(updatedJob)
        }
      }
    } catch (error) {
      console.error('Error polling job:', error)
    }
  }, [jobId, stopPolling, queryClient])

  useEffect(() => {
    if (!jobId) {
      stopPolling()
      setJob(null)
      return
    }

    // Start polling
    setIsPolling(true)
    poll() // Initial poll

    intervalRef.current = window.setInterval(poll, pollInterval)

    return () => {
      stopPolling()
    }
  }, [jobId, poll, pollInterval, stopPolling])

  return {
    job,
    isPolling,
    stopPolling,
  }
}

