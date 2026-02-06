import { useState, useEffect, useCallback } from 'react'
import { Save, X, RotateCcw, Music, Type, Volume2, VolumeX } from 'lucide-react'
import type { Clip, TextOverlaySettings, AudioOverlaySettings } from '../types'
import { VideoPlayer } from './VideoPlayer'
import { Button } from './Button'
import { Input } from './Input'
import { formatTimestamp, formatDuration } from '../utils/format'
import { getVideoUrl, updateClip } from '../api/client'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'

interface ClipEditorProps {
  clip: Clip
  projectId: number
  projectDuration: number
  onClose: () => void
  onPublish?: (clip: Clip, settings: { textOverlay?: TextOverlaySettings; audioOverlay?: AudioOverlaySettings }) => void
}

export function ClipEditor({
  clip,
  projectId,
  projectDuration,
  onClose,
  onPublish,
}: ClipEditorProps) {
  const queryClient = useQueryClient()
  const videoUrl = getVideoUrl(projectId)

  const [name, setName] = useState(clip.name || '')
  const [startTime, setStartTime] = useState(clip.start_time)
  const [endTime, setEndTime] = useState(clip.end_time)
  const [currentTime, setCurrentTime] = useState(clip.start_time)

  // Overlay settings
  const [showOverlaySettings, setShowOverlaySettings] = useState(false)
  const [textOverlayEnabled, setTextOverlayEnabled] = useState(false)
  const [textOverlayText, setTextOverlayText] = useState('')
  const [textOverlayPosition, setTextOverlayPosition] = useState<'top' | 'center' | 'bottom'>('bottom')
  const [textOverlayColor, setTextOverlayColor] = useState('#FFFFFF')
  const [textOverlaySize, setTextOverlaySize] = useState(48)

  const [audioOverlayEnabled, setAudioOverlayEnabled] = useState(false)
  const [audioOverlayPath, setAudioOverlayPath] = useState('')
  const [audioOverlayVolume, setAudioOverlayVolume] = useState(30)
  const [originalAudioVolume, setOriginalAudioVolume] = useState(100)

  // Reset when clip changes
  useEffect(() => {
    setName(clip.name || '')
    setStartTime(clip.start_time)
    setEndTime(clip.end_time)
    setCurrentTime(clip.start_time)
    // Reset overlay settings
    setTextOverlayEnabled(false)
    setTextOverlayText('')
    setAudioOverlayEnabled(false)
    setAudioOverlayPath('')
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

  const handlePublish = () => {
    if (onPublish) {
      const settings: { textOverlay?: TextOverlaySettings; audioOverlay?: AudioOverlaySettings } = {}
      
      if (textOverlayEnabled && textOverlayText) {
        settings.textOverlay = {
          text: textOverlayText,
          position: textOverlayPosition,
          color: textOverlayColor,
          size: textOverlaySize,
        }
      }
      
      if (audioOverlayEnabled && audioOverlayPath) {
        settings.audioOverlay = {
          path: audioOverlayPath,
          volume: audioOverlayVolume,
          original_volume: originalAudioVolume,
        }
      }
      
      onPublish(clip, settings)
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

        {/* Overlay Settings Toggle */}
        <div className="border-t border-clip-border pt-4">
          <button
            onClick={() => setShowOverlaySettings(!showOverlaySettings)}
            className="w-full flex items-center justify-between p-3 bg-clip-elevated rounded-lg hover:bg-clip-elevated/80 transition-colors"
          >
            <span className="text-sm font-medium text-white flex items-center gap-2">
              <Type className="w-4 h-4" />
              Overlay Settings (for Publish)
            </span>
            <span className="text-xs text-gray-500">
              {showOverlaySettings ? 'Hide' : 'Show'}
            </span>
          </button>
        </div>

        {/* Overlay Settings Content */}
        {showOverlaySettings && (
          <div className="space-y-4 p-4 bg-clip-elevated/50 rounded-lg">
            {/* Text Overlay */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm font-medium text-white">
                  <Type className="w-4 h-4" />
                  Text Overlay
                </label>
                <button
                  onClick={() => setTextOverlayEnabled(!textOverlayEnabled)}
                  className={clsx(
                    'w-10 h-5 rounded-full transition-colors',
                    textOverlayEnabled ? 'bg-clip-accent' : 'bg-gray-600'
                  )}
                >
                  <div className={clsx(
                    'w-4 h-4 rounded-full bg-white transition-transform mx-0.5',
                    textOverlayEnabled && 'translate-x-5'
                  )} />
                </button>
              </div>

              {textOverlayEnabled && (
                <div className="space-y-3 pl-6">
                  <Input
                    label="Text"
                    value={textOverlayText}
                    onChange={(e) => setTextOverlayText(e.target.value)}
                    placeholder="Enter overlay text..."
                  />
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Position</label>
                      <select
                        value={textOverlayPosition}
                        onChange={(e) => setTextOverlayPosition(e.target.value as 'top' | 'center' | 'bottom')}
                        className="w-full px-2 py-1.5 bg-clip-bg border border-clip-border rounded text-sm text-white"
                      >
                        <option value="top">Top</option>
                        <option value="center">Center</option>
                        <option value="bottom">Bottom</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Color</label>
                      <input
                        type="color"
                        value={textOverlayColor}
                        onChange={(e) => setTextOverlayColor(e.target.value)}
                        className="w-full h-8 rounded cursor-pointer"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Size</label>
                      <input
                        type="number"
                        value={textOverlaySize}
                        onChange={(e) => setTextOverlaySize(parseInt(e.target.value))}
                        min={12}
                        max={200}
                        className="w-full px-2 py-1.5 bg-clip-bg border border-clip-border rounded text-sm text-white"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Audio Overlay */}
            <div className="space-y-3 border-t border-clip-border pt-4">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm font-medium text-white">
                  <Music className="w-4 h-4" />
                  Background Audio
                </label>
                <button
                  onClick={() => setAudioOverlayEnabled(!audioOverlayEnabled)}
                  className={clsx(
                    'w-10 h-5 rounded-full transition-colors',
                    audioOverlayEnabled ? 'bg-clip-accent' : 'bg-gray-600'
                  )}
                >
                  <div className={clsx(
                    'w-4 h-4 rounded-full bg-white transition-transform mx-0.5',
                    audioOverlayEnabled && 'translate-x-5'
                  )} />
                </button>
              </div>

              {audioOverlayEnabled && (
                <div className="space-y-3 pl-6">
                  <Input
                    label="Audio File Path"
                    value={audioOverlayPath}
                    onChange={(e) => setAudioOverlayPath(e.target.value)}
                    placeholder="/path/to/audio.mp3"
                  />
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                        <Music className="w-3 h-3" />
                        Background Volume
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={audioOverlayVolume}
                          onChange={(e) => setAudioOverlayVolume(parseInt(e.target.value))}
                          className="flex-1"
                        />
                        <span className="text-xs text-gray-400 w-8">{audioOverlayVolume}%</span>
                      </div>
                    </div>
                    <div>
                      <label className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                        <Volume2 className="w-3 h-3" />
                        Original Audio
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={originalAudioVolume}
                          onChange={(e) => setOriginalAudioVolume(parseInt(e.target.value))}
                          className="flex-1"
                        />
                        <span className="text-xs text-gray-400 w-8">{originalAudioVolume}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

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
          {onPublish && (
            <Button
              variant="secondary"
              onClick={handlePublish}
            >
              Publish...
            </Button>
          )}
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
