import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueries, useQueryClient } from '@tanstack/react-query'
import { Download, Check, AlertCircle, Upload, Youtube } from 'lucide-react'
import { Button } from './Button'
import { Input } from './Input'
import { JobProgress } from './JobProgress'
import { useJobPolling } from '../hooks/useJobPolling'
import {
  exportClip,
  exportBatch,
  setOutputFolder,
  validateFolder,
  getNiches,
  getNicheAccounts,
  getJob,
  uploadSelectedClips,
} from '../api/client'
import type {
  Clip,
  CompoundClip,
  Project,
  Niche,
  Account,
  VerticalFramingMode,
  VerticalResolutionMode,
} from '../types'
import clsx from 'clsx'

interface ExportPanelProps {
  project: Project
  selectedClips: Clip[]
  compoundClips: CompoundClip[]
  onClearSelection: () => void
}

function UploadJobsProgress({ jobIds }: { jobIds: number[] }) {
  const queries = useQueries({
    queries: jobIds.map((jobId) => ({
      queryKey: ['job', jobId],
      queryFn: () => getJob(jobId),
      refetchInterval: (query: { state: { data?: { status?: string } } }) => {
        const status = query.state.data?.status
        return status === 'completed' || status === 'failed' || status === 'cancelled' ? false : 1500
      },
    })),
  })

  if (queries.length === 0) return null

  return (
    <div className="space-y-2">
      {queries.map((query, index) => {
        if (query.isLoading || !query.data) {
          return (
            <div key={jobIds[index]} className="text-xs text-gray-500">
              Upload job #{jobIds[index]} starting...
            </div>
          )
        }
        return <JobProgress key={jobIds[index]} job={query.data} />
      })}
    </div>
  )
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
  const [selectedNicheId, setSelectedNicheId] = useState<number | null>(null)
  const [selectedUploadAccountId, setSelectedUploadAccountId] = useState<number | null>(null)
  const [uploadPrivacy, setUploadPrivacy] = useState<'private' | 'public' | 'unlisted'>('private')
  const [uploadJobIds, setUploadJobIds] = useState<number[]>([])
  const [uploadErrors, setUploadErrors] = useState<{ clip_id: number; error: string }[]>([])
  const [useVerticalPreset, setUseVerticalPreset] = useState(true)
  const [verticalFraming, setVerticalFraming] = useState<VerticalFramingMode>('fill')
  const [verticalResolution, setVerticalResolution] = useState<VerticalResolutionMode>('limit_upscale')

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

  const { data: niches = [] } = useQuery({
    queryKey: ['niches'],
    queryFn: getNiches,
  })

  const { data: uploadAccounts = [] } = useQuery({
    queryKey: ['accounts', selectedNicheId],
    queryFn: () => selectedNicheId ? getNicheAccounts(selectedNicheId) : Promise.resolve([]),
    enabled: !!selectedNicheId,
  })

  const connectedYouTubeAccounts = useMemo(() => {
    return uploadAccounts.filter(
      (account: Account) =>
        account.platform === 'youtube_shorts' &&
        account.auth_status === 'connected' &&
        !!account.platform_user_id
    )
  }, [uploadAccounts])

  const uploadSelectedMutation = useMutation({
    mutationFn: () => {
      if (!selectedNicheId || !selectedUploadAccountId || selectedClips.length === 0) {
        throw new Error('Select a niche, a connected YouTube account, and at least one clip')
      }
      return uploadSelectedClips(project.id, {
        clip_ids: selectedClips.map(c => c.id),
        account_id: selectedUploadAccountId,
        niche_id: selectedNicheId,
        privacy_status: uploadPrivacy,
        use_vertical_preset: useVerticalPreset,
        vertical_framing: useVerticalPreset ? verticalFraming : undefined,
        vertical_resolution: useVerticalPreset ? verticalResolution : undefined,
      })
    },
    onMutate: () => {
      setUploadErrors([])
      setUploadJobIds([])
    },
    onSuccess: (result) => {
      setUploadJobIds(result.jobs.map(job => job.job_id))
      setUploadErrors(result.errors)
    },
  })

  const handleValidateFolder = () => {
    if (!outputFolder) {
      setFolderValid(false)
      setFolderMessage('Please enter a folder path')
      return
    }
    validateMutation.mutate()
  }

  const handleNicheChange = (value: string) => {
    const nextNicheId = value ? Number(value) : null
    setSelectedNicheId(nextNicheId)
    setSelectedUploadAccountId(null)
  }

  const canExport = folderValid && selectedClips.length > 0 && !activeJobId
  const isExporting = activeJobId !== null
  const canUploadSelected =
    selectedClips.length > 0 &&
    !!selectedNicheId &&
    !!selectedUploadAccountId &&
    !uploadSelectedMutation.isPending

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

        {/* Direct YouTube upload */}
        <div className="pt-4 border-t border-clip-border space-y-3">
          <h4 className="text-sm font-medium text-gray-300 flex items-center gap-2">
            <Youtube className="w-4 h-4 text-red-400" />
            Direct Upload (YouTube Shorts)
          </h4>

          <div className="space-y-2">
            <label className="block text-xs text-gray-400">Niche</label>
            <select
              value={selectedNicheId ?? ''}
              onChange={(e) => handleNicheChange(e.target.value)}
              className="w-full px-3 py-2 bg-clip-elevated border border-clip-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-clip-accent"
            >
              <option value="">Select niche</option>
              {niches.map((niche: Niche) => (
                <option key={niche.id} value={niche.id}>{niche.name}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="block text-xs text-gray-400">Connected YouTube Account</label>
            <select
              value={selectedUploadAccountId ?? ''}
              onChange={(e) => setSelectedUploadAccountId(e.target.value ? Number(e.target.value) : null)}
              disabled={!selectedNicheId}
              className="w-full px-3 py-2 bg-clip-elevated border border-clip-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-clip-accent disabled:opacity-50"
            >
              <option value="">Select account</option>
              {connectedYouTubeAccounts.map((account: Account) => (
                <option key={account.id} value={account.id}>
                  {account.display_name || account.handle}
                </option>
              ))}
            </select>
            {selectedNicheId && connectedYouTubeAccounts.length === 0 && (
              <p className="text-xs text-yellow-300">
                No connected YouTube accounts for this niche. Connect/reconnect in Niches.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="block text-xs text-gray-400">Privacy</label>
            <select
              value={uploadPrivacy}
              onChange={(e) => setUploadPrivacy(e.target.value as 'private' | 'public' | 'unlisted')}
              className="w-full px-3 py-2 bg-clip-elevated border border-clip-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-clip-accent"
            >
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </div>

          <div className="p-3 bg-clip-elevated rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white">Vertical Format (9:16)</p>
                <p className="text-xs text-gray-500">Shorts framing and resolution</p>
              </div>
              <button
                onClick={() => setUseVerticalPreset(!useVerticalPreset)}
                className={clsx(
                  'w-10 h-5 rounded-full transition-colors',
                  useVerticalPreset ? 'bg-clip-accent' : 'bg-gray-600'
                )}
              >
                <div className={clsx(
                  'w-4 h-4 rounded-full bg-white transition-transform mx-0.5',
                  useVerticalPreset && 'translate-x-5'
                )} />
              </button>
            </div>

            {useVerticalPreset && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="block text-xs text-gray-400">Framing</label>
                  <select
                    value={verticalFraming}
                    onChange={(e) => setVerticalFraming(e.target.value as VerticalFramingMode)}
                    className="w-full px-3 py-2 bg-clip-elevated border border-clip-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-clip-accent"
                  >
                    <option value="fill">Fill (crop to 9:16)</option>
                    <option value="fit">Fit (letterbox)</option>
                    <option value="blur">Blur background</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="block text-xs text-gray-400">Resolution</label>
                  <select
                    value={verticalResolution}
                    onChange={(e) => setVerticalResolution(e.target.value as VerticalResolutionMode)}
                    className="w-full px-3 py-2 bg-clip-elevated border border-clip-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-clip-accent"
                  >
                    <option value="limit_upscale">Limit upscale</option>
                    <option value="fixed_1080">Always 1080x1920</option>
                    <option value="match_source">Match source height</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          <Button
            variant="primary"
            className="w-full"
            onClick={() => uploadSelectedMutation.mutate()}
            loading={uploadSelectedMutation.isPending}
            disabled={!canUploadSelected}
            icon={<Upload className="w-4 h-4" />}
          >
            Upload {selectedClips.length} Selected to YouTube
          </Button>

          {uploadSelectedMutation.isError && (
            <p className="text-xs text-clip-error">{(uploadSelectedMutation.error as Error).message}</p>
          )}

          {uploadErrors.length > 0 && (
            <div className="p-2 rounded border border-red-500/20 bg-red-500/10 space-y-1">
              {uploadErrors.map((err) => (
                <div key={`${err.clip_id}-${err.error}`} className="text-xs text-red-200">
                  Clip #{err.clip_id}: {err.error}
                </div>
              ))}
            </div>
          )}

          {uploadJobIds.length > 0 && (
            <UploadJobsProgress jobIds={uploadJobIds} />
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
