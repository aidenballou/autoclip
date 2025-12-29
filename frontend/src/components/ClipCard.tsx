import { useState } from 'react'
import { Clock, Edit3, Trash2, Check, Square, CheckSquare, Star, Sparkles } from 'lucide-react'
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
  showQualityScore?: boolean
  rank?: number
}

export function ClipCard({
  clip,
  projectId,
  selected = false,
  active = false,
  onSelect,
  onClick,
  onToggleSelection,
  showQualityScore = false,
  rank,
}: ClipCardProps) {
  const thumbnailUrl = clip.thumbnail_url || `/api/projects/${projectId}/thumbnails/${clip.id}`
  
  // Format quality score as percentage (0-100)
  const qualityPercent = clip.quality_score !== null 
    ? Math.round(clip.quality_score * 100) 
    : null

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

        {/* Quality score badge */}
        {showQualityScore && qualityPercent !== null && (
          <div className={clsx(
            'absolute bottom-2 left-2 px-1.5 py-0.5 rounded text-xs font-medium flex items-center gap-1',
            qualityPercent >= 70 ? 'bg-emerald-500/90 text-white' :
            qualityPercent >= 40 ? 'bg-amber-500/90 text-white' :
            'bg-gray-500/90 text-white'
          )}>
            <Star className="w-3 h-3" />
            {qualityPercent}
          </div>
        )}

        {/* Rank badge */}
        {rank && rank <= 10 && (
          <div className={clsx(
            'absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
            rank === 1 ? 'bg-yellow-500 text-black' :
            rank === 2 ? 'bg-gray-300 text-black' :
            rank === 3 ? 'bg-amber-600 text-white' :
            'bg-clip-elevated text-white'
          )}>
            {rank}
          </div>
        )}

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
        <div className="flex items-center gap-1 mt-2 flex-wrap">
          {clip.created_by === 'manual' && (
            <span className="inline-block px-1.5 py-0.5 bg-clip-accent/20 text-clip-accent text-xs rounded">
              Edited
            </span>
          )}
          {clip.generation_version === 'v2' && (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
              <Sparkles className="w-3 h-3" />
              V2
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

