import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Send,
  Folder,
  CheckSquare,
  Square,
  Youtube,
  Instagram,
  Twitter,
  AlertCircle,
  CheckCircle,
  Type,
  Music,
} from 'lucide-react'
import {
  getNiches,
  getNicheAccounts,
  publishClip,
  validateFolder,
} from '../api/client'
import { Modal } from './Modal'
import { Button } from './Button'
import { Input } from './Input'
import { JobProgress } from './JobProgress'
import { useJobPolling } from '../hooks/useJobPolling'
import type {
  Clip,
  Niche,
  Account,
  Platform,
  TextOverlaySettings,
  AudioOverlaySettings,
  VerticalFramingMode,
  VerticalResolutionMode,
} from '../types'
import clsx from 'clsx'

interface PublishModalProps {
  open: boolean
  onClose: () => void
  projectId: number
  clip: Clip
  initialTextOverlay?: TextOverlaySettings
  initialAudioOverlay?: AudioOverlaySettings
}

const PLATFORM_ICONS: Record<Platform, React.ReactNode> = {
  youtube_shorts: <Youtube className="w-4 h-4" />,
  tiktok: <span className="text-xs font-bold">TT</span>,
  instagram_reels: <Instagram className="w-4 h-4" />,
  twitter: <Twitter className="w-4 h-4" />,
  snapchat: <span className="text-xs font-bold">SC</span>,
}

export function PublishModal({
  open,
  onClose,
  projectId,
  clip,
  initialTextOverlay,
  initialAudioOverlay,
}: PublishModalProps) {
  const queryClient = useQueryClient()

  // State
  const [step, setStep] = useState<'select' | 'configure' | 'publishing' | 'complete'>('select')
  const [selectedNicheId, setSelectedNicheId] = useState<number | null>(null)
  const [selectedAccountIds, setSelectedAccountIds] = useState<Set<number>>(new Set())
  const [outputFolder, setOutputFolder] = useState('')
  const [folderValid, setFolderValid] = useState<boolean | null>(null)
  const [caption, setCaption] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [useVerticalPreset, setUseVerticalPreset] = useState(true)
  const [verticalFraming, setVerticalFraming] = useState<VerticalFramingMode>('fill')
  const [verticalResolution, setVerticalResolution] = useState<VerticalResolutionMode>('limit_upscale')
  const [publishJobId, setPublishJobId] = useState<number | null>(null)
  const [publishResult, setPublishResult] = useState<any>(null)

  // Text overlay state (from initial or manual)
  const [textOverlay, setTextOverlay] = useState<TextOverlaySettings | undefined>(initialTextOverlay)
  const [audioOverlay, setAudioOverlay] = useState<AudioOverlaySettings | undefined>(initialAudioOverlay)

  // Queries
  const { data: niches = [] } = useQuery({
    queryKey: ['niches'],
    queryFn: getNiches,
    enabled: open,
  })

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts', selectedNicheId],
    queryFn: () => selectedNicheId ? getNicheAccounts(selectedNicheId) : Promise.resolve([]),
    enabled: !!selectedNicheId && open,
  })

  const selectedNiche = niches.find(n => n.id === selectedNicheId)

  // Job polling
  const { job } = useJobPolling({
    jobId: publishJobId,
    onComplete: (job) => {
      setStep('complete')
      try {
        setPublishResult(JSON.parse(job.result || '{}'))
      } catch {
        setPublishResult({})
      }
    },
    onError: () => {
      setStep('complete')
    },
  })

  // Mutations
  const publishMutation = useMutation({
    mutationFn: () => {
      if (!selectedNicheId || selectedAccountIds.size === 0 || !outputFolder) {
        throw new Error('Missing required fields')
      }

        return publishClip(projectId, {
          clip_id: clip.id,
          niche_id: selectedNicheId,
          account_ids: Array.from(selectedAccountIds),
          output_folder: outputFolder,
          caption: caption || undefined,
          hashtags: hashtags
            .split(/[,\s]+/)
            .map(t => t.replace(/^#/, '').trim())
            .filter(Boolean),
          text_overlay: textOverlay,
          audio_overlay: audioOverlay,
          use_vertical_preset: useVerticalPreset,
          vertical_framing: useVerticalPreset ? verticalFraming : undefined,
          vertical_resolution: useVerticalPreset ? verticalResolution : undefined,
        })
      },
    onSuccess: (job) => {
      setPublishJobId(job.id)
      setStep('publishing')
    },
  })

  const validateFolderMutation = useMutation({
    mutationFn: validateFolder,
    onSuccess: (result) => {
      setFolderValid(result.valid)
      if (result.valid) {
        setOutputFolder(result.path)
      }
    },
  })

  // Handlers
  const handleNicheSelect = (nicheId: number) => {
    setSelectedNicheId(nicheId)
    setSelectedAccountIds(new Set())
    
    // Apply niche defaults
    const niche = niches.find(n => n.id === nicheId)
    if (niche) {
      if (niche.default_hashtags.length > 0) {
        setHashtags(niche.default_hashtags.join(', '))
      }
      if (niche.default_caption_template) {
        setCaption(niche.default_caption_template)
      }
    }
  }

  const toggleAccount = (accountId: number) => {
    setSelectedAccountIds(prev => {
      const next = new Set(prev)
      if (next.has(accountId)) {
        next.delete(accountId)
      } else {
        next.add(accountId)
      }
      return next
    })
  }

  const handleValidateFolder = () => {
    if (outputFolder.trim()) {
      validateFolderMutation.mutate(outputFolder.trim())
    }
  }

  const handlePublish = () => {
    publishMutation.mutate()
  }

  const handleClose = () => {
    // Reset state
    setStep('select')
    setSelectedNicheId(null)
    setSelectedAccountIds(new Set())
    setPublishJobId(null)
    setPublishResult(null)
    onClose()
  }

  // Derived state
  const canProceed = selectedNicheId && selectedAccountIds.size > 0
  const canPublish = canProceed && folderValid && outputFolder.trim()

  if (!open) return null

  return (
    <Modal
      title={step === 'complete' ? 'Publish Complete' : 'Publish Clip'}
      onClose={handleClose}
      className="max-w-2xl"
    >
      {/* Step: Select niche and accounts */}
      {step === 'select' && (
        <div className="space-y-6">
          {/* Clip info */}
          <div className="flex items-center gap-3 p-3 bg-clip-elevated rounded-lg">
            {clip.thumbnail_url && (
              <img
                src={clip.thumbnail_url}
                alt={clip.name || 'Clip'}
                className="w-20 h-12 object-cover rounded"
              />
            )}
            <div>
              <p className="font-medium text-white">{clip.name || `Clip ${clip.ordering + 1}`}</p>
              <p className="text-xs text-gray-500">
                {clip.duration.toFixed(1)}s duration
              </p>
            </div>
          </div>

          {/* Niche selection */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Select Niche
            </label>
            <div className="grid grid-cols-2 gap-2">
              {niches.map(niche => (
                <button
                  key={niche.id}
                  onClick={() => handleNicheSelect(niche.id)}
                  className={clsx(
                    'p-3 rounded-lg border text-left transition-colors',
                    selectedNicheId === niche.id
                      ? 'border-clip-accent bg-clip-accent/10'
                      : 'border-clip-border bg-clip-elevated hover:border-gray-600'
                  )}
                >
                  <p className="font-medium text-white">{niche.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {niche.account_count || 0} accounts
                  </p>
                </button>
              ))}
            </div>
            {niches.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">
                No niches yet. Create one in Niches & Accounts.
              </p>
            )}
          </div>

          {/* Account selection */}
          {selectedNicheId && (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Select Accounts to Publish To
              </label>
              {accounts.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">
                  No accounts in this niche. Add accounts first.
                </p>
              ) : (
                <div className="space-y-2">
                  {accounts.map(account => (
                    <button
                      key={account.id}
                      onClick={() => toggleAccount(account.id)}
                      className={clsx(
                        'w-full flex items-center gap-3 p-3 rounded-lg border transition-colors',
                        selectedAccountIds.has(account.id)
                          ? 'border-clip-accent bg-clip-accent/10'
                          : 'border-clip-border bg-clip-elevated hover:border-gray-600'
                      )}
                    >
                      <div className={clsx(
                        'w-5 h-5 rounded flex items-center justify-center',
                        selectedAccountIds.has(account.id)
                          ? 'bg-clip-accent text-white'
                          : 'bg-clip-bg border border-clip-border'
                      )}>
                        {selectedAccountIds.has(account.id) && (
                          <CheckSquare className="w-4 h-4" />
                        )}
                      </div>
                      <div className="w-8 h-8 rounded-full bg-clip-bg flex items-center justify-center">
                        {PLATFORM_ICONS[account.platform]}
                      </div>
                      <div className="flex-1 text-left">
                        <p className="font-medium text-white">{account.handle}</p>
                        <p className="text-xs text-gray-500">{account.platform.replace('_', ' ')}</p>
                      </div>
                      {account.auth_status === 'connected' ? (
                        <CheckCircle className="w-4 h-4 text-green-400" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-yellow-400" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-clip-border">
            <Button variant="secondary" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={() => setStep('configure')}
              disabled={!canProceed}
            >
              Next: Configure
            </Button>
          </div>
        </div>
      )}

      {/* Step: Configure publish settings */}
      {step === 'configure' && (
        <div className="space-y-4">
          {/* Output folder */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Output Folder
            </label>
            <div className="flex gap-2">
              <Input
                value={outputFolder}
                onChange={(e) => {
                  setOutputFolder(e.target.value)
                  setFolderValid(null)
                }}
                placeholder="/path/to/export/folder"
                className="flex-1"
              />
              <Button
                variant="secondary"
                onClick={handleValidateFolder}
                loading={validateFolderMutation.isPending}
                icon={<Folder className="w-4 h-4" />}
              >
                Validate
              </Button>
            </div>
            {folderValid === true && (
              <p className="text-xs text-green-400 mt-1">✓ Folder is valid and writable</p>
            )}
            {folderValid === false && (
              <p className="text-xs text-red-400 mt-1">✗ Invalid folder or no write permission</p>
            )}
          </div>

          {/* Caption */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Caption
            </label>
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Write a caption for your post..."
              rows={2}
              className="w-full px-3 py-2 bg-clip-elevated border border-clip-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-clip-accent focus:border-transparent resize-none"
            />
          </div>

          {/* Hashtags */}
          <Input
            label="Hashtags"
            value={hashtags}
            onChange={(e) => setHashtags(e.target.value)}
            placeholder="sports, highlights, viral"
          />

          {/* Vertical preset */}
          <div className="flex items-center justify-between p-3 bg-clip-elevated rounded-lg">
            <div>
              <p className="font-medium text-white">Use Vertical Format (9:16)</p>
              <p className="text-xs text-gray-500">Optimized for Shorts, Reels, TikTok</p>
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

          {/* Overlay indicators */}
          {(textOverlay || audioOverlay) && (
            <div className="p-3 bg-clip-elevated/50 rounded-lg">
              <p className="text-xs text-gray-400 mb-2">Overlays to apply:</p>
              <div className="flex gap-2">
                {textOverlay && (
                  <span className="inline-flex items-center gap-1 px-2 py-1 bg-clip-accent/20 text-clip-accent text-xs rounded">
                    <Type className="w-3 h-3" />
                    Text: "{textOverlay.text.substring(0, 20)}..."
                  </span>
                )}
                {audioOverlay && (
                  <span className="inline-flex items-center gap-1 px-2 py-1 bg-purple-500/20 text-purple-400 text-xs rounded">
                    <Music className="w-3 h-3" />
                    Background Audio
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="flex justify-between gap-3 pt-4 border-t border-clip-border">
            <Button variant="ghost" onClick={() => setStep('select')}>
              Back
            </Button>
            <div className="flex gap-3">
              <Button variant="secondary" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handlePublish}
                loading={publishMutation.isPending}
                disabled={!canPublish}
                icon={<Send className="w-4 h-4" />}
              >
                Publish to {selectedAccountIds.size} Account{selectedAccountIds.size > 1 ? 's' : ''}
              </Button>
            </div>
          </div>

          {publishMutation.isError && (
            <p className="text-sm text-clip-error">
              {(publishMutation.error as Error).message}
            </p>
          )}
        </div>
      )}

      {/* Step: Publishing progress */}
      {step === 'publishing' && job && (
        <div className="space-y-4">
          <JobProgress job={job} />
          <p className="text-sm text-gray-400 text-center">
            Exporting clips for {selectedAccountIds.size} platform{selectedAccountIds.size > 1 ? 's' : ''}...
          </p>
        </div>
      )}

      {/* Step: Complete */}
      {step === 'complete' && (
        <div className="space-y-4">
          {publishResult?.exports?.length > 0 ? (
            <>
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle className="w-5 h-5" />
                <span className="font-medium">Successfully exported to {publishResult.exports.length} platform(s)</span>
              </div>
              <div className="space-y-2">
                {publishResult.exports.map((exp: any, i: number) => (
                  <div key={i} className="p-3 bg-clip-elevated rounded-lg">
                    <p className="font-medium text-white capitalize">{exp.platform.replace('_', ' ')}</p>
                    <p className="text-xs text-gray-500 mt-1 font-mono truncate">{exp.video_path}</p>
                    <p className="text-xs text-gray-600 mt-0.5">
                      Accounts: {exp.accounts.join(', ')}
                    </p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="text-center py-4">
              <AlertCircle className="w-8 h-8 text-clip-error mx-auto mb-2" />
              <p className="text-clip-error">No exports were successful</p>
            </div>
          )}

          {publishResult?.errors?.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm text-clip-error">Errors:</p>
              {publishResult.errors.map((err: any, i: number) => (
                <div key={i} className="p-2 bg-clip-error/10 border border-clip-error/30 rounded text-sm text-clip-error">
                  {err.platform}: {err.error}
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end pt-4 border-t border-clip-border">
            <Button variant="primary" onClick={handleClose}>
              Done
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
