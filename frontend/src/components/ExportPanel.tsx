import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, FolderOutput, Check, AlertCircle } from 'lucide-react'
import { Button } from './Button'
import { Input } from './Input'
import { JobProgress } from './JobProgress'
import { useJobPolling } from '../hooks/useJobPolling'
import { exportClip, exportBatch, setOutputFolder, validateFolder } from '../api/client'
import type { Clip, CompoundClip, Project } from '../types'
import clsx from 'clsx'

interface ExportPanelProps {
  project: Project
  selectedClips: Clip[]
  compoundClips: CompoundClip[]
  onClearSelection: () => void
}

export function ExportPanel({
  project,
  selectedClips,
  compoundClips,
  onClearSelection,
}: ExportPanelProps) {
  const queryClient = useQueryClient()
  const [outputFolder, setOutputFolderState] = useState(project.output_folder || '')
  const [folderValid, setFolderValid] = useState<boolean | null>(null)
  const [folderMessage, setFolderMessage] = useState('')
  const [activeJobId, setActiveJobId] = useState<number | null>(null)

  const { job } = useJobPolling({
    jobId: activeJobId,
    onComplete: () => {
      setActiveJobId(null)
      onClearSelection()
    },
    onError: () => {
      setActiveJobId(null)
    },
  })

  // Validate folder mutation
  const validateMutation = useMutation({
    mutationFn: () => validateFolder(outputFolder),
    onSuccess: (result) => {
      setFolderValid(result.valid)
      setFolderMessage(result.message || '')
      if (result.valid) {
        setOutputFolderState(result.path)
        // Also save to project
        setOutputFolder(project.id, result.path)
          .then(() => queryClient.invalidateQueries({ queryKey: ['project', project.id] }))
      }
    },
  })

  // Export mutations
  const exportSingleMutation = useMutation({
    mutationFn: (clipId: number) => exportClip(project.id, {
      clip_id: clipId,
      output_folder: outputFolder || undefined,
    }),
    onSuccess: (job) => setActiveJobId(job.id),
  })

  const exportBatchMutation = useMutation({
    mutationFn: () => exportBatch(project.id, {
      clip_ids: selectedClips.map(c => c.id),
      output_folder: outputFolder || undefined,
    }),
    onSuccess: (job) => setActiveJobId(job.id),
  })

  const exportCompoundMutation = useMutation({
    mutationFn: (compoundId: number) => exportClip(project.id, {
      compound_clip_id: compoundId,
      output_folder: outputFolder || undefined,
    }),
    onSuccess: (job) => setActiveJobId(job.id),
  })

  const handleValidateFolder = () => {
    if (!outputFolder) {
      setFolderValid(false)
      setFolderMessage('Please enter a folder path')
      return
    }
    validateMutation.mutate()
  }

  const canExport = folderValid && selectedClips.length > 0 && !activeJobId
  const isExporting = activeJobId !== null

  return (
    <div className="bg-clip-surface border border-clip-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-clip-border">
        <h3 className="font-medium text-white flex items-center gap-2">
          <Download className="w-4 h-4" />
          Export
        </h3>
      </div>

      <div className="p-4 space-y-4">
        {/* Output folder */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-300">
            Output Folder
          </label>
          <div className="flex gap-2">
            <Input
              value={outputFolder}
              onChange={(e) => {
                setOutputFolderState(e.target.value)
                setFolderValid(null)
              }}
              placeholder="/Users/you/Desktop/clips"
              className="flex-1"
            />
            <Button
              variant="secondary"
              onClick={handleValidateFolder}
              loading={validateMutation.isPending}
            >
              Validate
            </Button>
          </div>
          {folderValid !== null && (
            <div className={clsx(
              'flex items-center gap-2 text-xs',
              folderValid ? 'text-clip-success' : 'text-clip-error'
            )}>
              {folderValid ? (
                <Check className="w-3 h-3" />
              ) : (
                <AlertCircle className="w-3 h-3" />
              )}
              {folderMessage}
            </div>
          )}
          <p className="text-xs text-gray-500">
            Tip: Drag a folder from Finder and paste the path here
          </p>
        </div>

        {/* Selected clips */}
        <div className="p-3 bg-clip-elevated rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-300">Selected Clips</span>
            <span className="text-sm font-medium text-white">{selectedClips.length}</span>
          </div>
          {selectedClips.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {selectedClips.slice(0, 5).map(clip => (
                <span key={clip.id} className="px-2 py-0.5 bg-clip-border rounded text-xs text-gray-400">
                  {clip.name || `Clip ${clip.ordering + 1}`}
                </span>
              ))}
              {selectedClips.length > 5 && (
                <span className="px-2 py-0.5 text-xs text-gray-500">
                  +{selectedClips.length - 5} more
                </span>
              )}
            </div>
          )}
        </div>

        {/* Export actions */}
        <div className="space-y-2">
          {selectedClips.length === 1 && (
            <Button
              variant="primary"
              className="w-full"
              onClick={() => exportSingleMutation.mutate(selectedClips[0].id)}
              loading={exportSingleMutation.isPending}
              disabled={!folderValid || isExporting}
              icon={<Download className="w-4 h-4" />}
            >
              Export Clip
            </Button>
          )}
          {selectedClips.length > 1 && (
            <Button
              variant="primary"
              className="w-full"
              onClick={() => exportBatchMutation.mutate()}
              loading={exportBatchMutation.isPending}
              disabled={!folderValid || isExporting}
              icon={<Download className="w-4 h-4" />}
            >
              Export {selectedClips.length} Clips
            </Button>
          )}
          {selectedClips.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-2">
              Select clips to export
            </p>
          )}
        </div>

        {/* Compound clips */}
        {compoundClips.length > 0 && (
          <div className="pt-4 border-t border-clip-border">
            <h4 className="text-sm font-medium text-gray-300 mb-2">Compound Clips</h4>
            <div className="space-y-2">
              {compoundClips.map(compound => (
                <div
                  key={compound.id}
                  className="flex items-center justify-between p-2 bg-clip-elevated rounded-lg"
                >
                  <div>
                    <span className="text-sm text-white">{compound.name}</span>
                    <span className="text-xs text-gray-500 ml-2">
                      {compound.items.length} clips
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => exportCompoundMutation.mutate(compound.id)}
                    disabled={!folderValid || isExporting}
                    loading={exportCompoundMutation.isPending}
                  >
                    Export
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active job progress */}
        {job && (
          <JobProgress job={job} />
        )}
      </div>
    </div>
  )
}

