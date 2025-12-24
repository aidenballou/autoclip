import { useState } from 'react'
import { Clock, Edit3, Trash2, Check, Square, CheckSquare } from 'lucide-react'
import type { Clip } from '../types'
import { formatDuration, formatTimestamp } from '../utils/format'
import clsx from 'clsx'

interface ClipCardProps {
  clip: Clip
  projectId: number
  selected?: boolean
  active?: boolean
  onSelect?: () => void
  onClick?: () => void
  onToggleSelection?: () => void
}

export function ClipCard({
  clip,
  projectId,
  selected = false,
  active = false,
  onSelect,
  onClick,
  onToggleSelection,
}: ClipCardProps) {
  const thumbnailUrl = clip.thumbnail_url || `/api/projects/${projectId}/thumbnails/${clip.id}`

  return (
    <div
      className={clsx(
        'clip-card relative bg-clip-surface border rounded-lg overflow-hidden cursor-pointer',
        active ? 'border-clip-accent ring-2 ring-clip-accent/30' : 'border-clip-border hover:border-gray-600',
        selected && 'ring-2 ring-clip-success/50'
      )}
      onClick={onClick}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-clip-elevated">
        <img
          src={thumbnailUrl}
          alt={clip.name || `Clip ${clip.id}`}
          className="w-full h-full object-cover"
          loading="lazy"
          onError={(e) => {
            // Hide broken images
            (e.target as HTMLImageElement).style.display = 'none'
          }}
        />
        
        {/* Duration badge */}
        <div className="absolute bottom-2 right-2 px-1.5 py-0.5 bg-black/70 rounded text-xs font-mono text-white">
          {formatDuration(clip.duration)}
        </div>

        {/* Selection checkbox */}
        {onToggleSelection && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleSelection()
            }}
            className={clsx(
              'absolute top-2 left-2 p-1 rounded transition-all',
              selected ? 'bg-clip-success text-white' : 'bg-black/50 text-gray-300 hover:bg-black/70'
            )}
          >
            {selected ? (
              <CheckSquare className="w-4 h-4" />
            ) : (
              <Square className="w-4 h-4" />
            )}
          </button>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="text-sm font-medium text-white truncate">
          {clip.name || `Clip ${clip.ordering + 1}`}
        </h3>
        <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 font-mono">
          <span>{formatTimestamp(clip.start_time)}</span>
          <span>→</span>
          <span>{formatTimestamp(clip.end_time)}</span>
        </div>
        {clip.created_by === 'manual' && (
          <span className="inline-block mt-2 px-1.5 py-0.5 bg-clip-accent/20 text-clip-accent text-xs rounded">
            Edited
          </span>
        )}
      </div>
    </div>
  )
}

