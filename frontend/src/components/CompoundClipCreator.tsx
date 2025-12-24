import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Layers, ChevronUp, ChevronDown, X, Plus } from 'lucide-react'
import { Modal } from './Modal'
import { Input } from './Input'
import { Button } from './Button'
import { createCompoundClip } from '../api/client'
import { formatDuration } from '../utils/format'
import type { Clip } from '../types'
import clsx from 'clsx'

interface CompoundClipCreatorProps {
  projectId: number
  selectedClips: Clip[]
  onClose: () => void
  onSuccess: () => void
}

export function CompoundClipCreator({
  projectId,
  selectedClips,
  onClose,
  onSuccess,
}: CompoundClipCreatorProps) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [orderedClips, setOrderedClips] = useState<Clip[]>([...selectedClips].sort((a, b) => a.ordering - b.ordering))

  const mutation = useMutation({
    mutationFn: () => createCompoundClip(projectId, {
      name,
      items: orderedClips.map((clip, index) => ({
        clip_id: clip.id,
      })),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compound-clips', projectId] })
      onSuccess()
      onClose()
    },
  })

  const handleMoveUp = (index: number) => {
    if (index === 0) return
    const newOrder = [...orderedClips]
    ;[newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]]
    setOrderedClips(newOrder)
  }

  const handleMoveDown = (index: number) => {
    if (index === orderedClips.length - 1) return
    const newOrder = [...orderedClips]
    ;[newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]]
    setOrderedClips(newOrder)
  }

  const handleRemove = (index: number) => {
    setOrderedClips(orderedClips.filter((_, i) => i !== index))
  }

  const totalDuration = orderedClips.reduce((sum, clip) => sum + clip.duration, 0)

  return (
    <Modal open onClose={onClose} title="Create Compound Clip" size="lg">
      <div className="space-y-4">
        <Input
          label="Compound Clip Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter a name for the combined clip"
        />

        {/* Clip order */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-300">
            Clip Order ({orderedClips.length} clips)
          </label>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {orderedClips.map((clip, index) => (
              <div
                key={clip.id}
                className="flex items-center gap-2 p-2 bg-clip-elevated rounded-lg group"
              >
                <span className="w-6 h-6 flex items-center justify-center text-xs font-medium text-gray-500 bg-clip-border rounded">
                  {index + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-white truncate block">
                    {clip.name || `Clip ${clip.ordering + 1}`}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">
                    {formatDuration(clip.duration)}
                  </span>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleMoveUp(index)}
                    disabled={index === 0}
                    className="p-1 rounded hover:bg-clip-border text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleMoveDown(index)}
                    disabled={index === orderedClips.length - 1}
                    className="p-1 rounded hover:bg-clip-border text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleRemove(index)}
                    className="p-1 rounded hover:bg-clip-error/20 text-gray-400 hover:text-clip-error"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Total duration */}
        <div className="flex items-center justify-center gap-2 py-3 bg-clip-elevated rounded-lg">
          <span className="text-sm text-gray-400">Total Duration:</span>
          <span className="text-lg font-mono text-white">{formatDuration(totalDuration)}</span>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            disabled={!name || orderedClips.length < 2}
            icon={<Layers className="w-4 h-4" />}
          >
            Create Compound Clip
          </Button>
        </div>

        {mutation.isError && (
          <p className="text-sm text-clip-error">
            Failed to create: {(mutation.error as Error).message}
          </p>
        )}
      </div>
    </Modal>
  )
}

