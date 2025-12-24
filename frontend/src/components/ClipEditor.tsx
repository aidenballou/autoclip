import { useState, useEffect, useCallback } from 'react'
import { Save, X, RotateCcw } from 'lucide-react'
import type { Clip } from '../types'
import { VideoPlayer } from './VideoPlayer'
import { Button } from './Button'
import { Input } from './Input'
import { formatTimestamp, formatDuration } from '../utils/format'
import { getVideoUrl, updateClip } from '../api/client'
import { useMutation, useQueryClient } from '@tanstack/react-query'

interface ClipEditorProps {
  clip: Clip
  projectId: number
  projectDuration: number
  onClose: () => void
}

export function ClipEditor({
  clip,
  projectId,
  projectDuration,
  onClose,
}: ClipEditorProps) {
  const queryClient = useQueryClient()
  const videoUrl = getVideoUrl(projectId)

  const [name, setName] = useState(clip.name || '')
  const [startTime, setStartTime] = useState(clip.start_time)
  const [endTime, setEndTime] = useState(clip.end_time)
  const [currentTime, setCurrentTime] = useState(clip.start_time)

  // Reset when clip changes
  useEffect(() => {
    setName(clip.name || '')
    setStartTime(clip.start_time)
    setEndTime(clip.end_time)
    setCurrentTime(clip.start_time)
  }, [clip])

  const mutation = useMutation({
    mutationFn: () => updateClip(clip.id, {
      name: name || undefined,
      start_time: startTime,
      end_time: endTime,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clips', projectId] })
      onClose()
    },
  })

  const handleSave = () => {
    if (startTime >= endTime) {
      alert('Start time must be before end time')
      return
    }
    mutation.mutate()
  }

  const handleReset = () => {
    setStartTime(clip.start_time)
    setEndTime(clip.end_time)
    setName(clip.name || '')
  }

  const handleSetStart = () => {
    if (currentTime < endTime) {
      setStartTime(currentTime)
    }
  }

  const handleSetEnd = () => {
    if (currentTime > startTime) {
      setEndTime(currentTime)
    }
  }

  const duration = endTime - startTime
  const hasChanges = 
    startTime !== clip.start_time || 
    endTime !== clip.end_time || 
    name !== (clip.name || '')

  return (
    <div className="bg-clip-surface border border-clip-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-clip-border">
        <h3 className="font-medium text-white">Edit Clip</h3>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-clip-elevated text-gray-400 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Video preview */}
      <div className="p-4">
        <VideoPlayer
          src={videoUrl}
          startTime={startTime}
          endTime={endTime}
          autoSeek
          onTimeUpdate={setCurrentTime}
          className="w-full"
        />
      </div>

      {/* Controls */}
      <div className="px-4 pb-4 space-y-4">
        {/* Name */}
        <Input
          label="Clip Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={`Clip ${clip.ordering + 1}`}
        />

        {/* Time controls */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              Start Time
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={projectDuration}
                step={0.1}
                value={startTime}
                onChange={(e) => setStartTime(parseFloat(e.target.value))}
                className="flex-1"
              />
              <span className="text-xs font-mono text-gray-400 w-20 text-right">
                {formatTimestamp(startTime)}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSetStart}
              className="w-full text-xs"
            >
              Set from playhead
            </Button>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              End Time
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={projectDuration}
                step={0.1}
                value={endTime}
                onChange={(e) => setEndTime(parseFloat(e.target.value))}
                className="flex-1"
              />
              <span className="text-xs font-mono text-gray-400 w-20 text-right">
                {formatTimestamp(endTime)}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSetEnd}
              className="w-full text-xs"
            >
              Set from playhead
            </Button>
          </div>
        </div>

        {/* Duration display */}
        <div className="flex items-center justify-center gap-2 py-2 bg-clip-elevated rounded-lg">
          <span className="text-sm text-gray-400">Duration:</span>
          <span className="text-sm font-mono text-white">{formatDuration(duration)}</span>
          {duration > 60 && (
            <span className="text-xs text-clip-warning">(Exceeds 60s)</span>
          )}
          {duration < 1 && (
            <span className="text-xs text-clip-error">(Too short)</span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <Button
            variant="ghost"
            onClick={handleReset}
            icon={<RotateCcw className="w-4 h-4" />}
            disabled={!hasChanges}
          >
            Reset
          </Button>
          <div className="flex-1" />
          <Button
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSave}
            loading={mutation.isPending}
            icon={<Save className="w-4 h-4" />}
            disabled={!hasChanges || startTime >= endTime}
          >
            Save
          </Button>
        </div>

        {mutation.isError && (
          <p className="text-sm text-clip-error">
            Failed to save: {(mutation.error as Error).message}
          </p>
        )}
      </div>
    </div>
  )
}

