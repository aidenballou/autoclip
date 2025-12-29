import { useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Download,
  Play,
  Scissors,
  Layers,
  RefreshCw,
  CheckSquare,
  Square,
  AlertCircle,
  Clock,
  Film,
  Settings,
  ArrowUpDown,
  Star,
  ChevronDown,
  Sparkles,
  Zap,
} from 'lucide-react'
import {
  getProject,
  getClips,
  getCompoundClips,
  startDownload,
  startAnalysis,
  getVideoUrl,
} from '../api/client'
import { Button } from '../components/Button'
import { VideoPlayer } from '../components/VideoPlayer'
import { ClipCard } from '../components/ClipCard'
import { ClipEditor } from '../components/ClipEditor'
import { ExportPanel } from '../components/ExportPanel'
import { JobProgress } from '../components/JobProgress'
import { CompoundClipCreator } from '../components/CompoundClipCreator'
import { useJobPolling } from '../hooks/useJobPolling'
import { formatDuration, formatResolution, getStatusBgColor } from '../utils/format'
import type { Clip, SegmentationMode } from '../types'
import clsx from 'clsx'

type SortMode = 'timeline' | 'quality'

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const id = parseInt(projectId!, 10)

  // State
  const [activeClip, setActiveClip] = useState<Clip | null>(null)
  const [selectedClips, setSelectedClips] = useState<Set<number>>(new Set())
  const [activeJobId, setActiveJobId] = useState<number | null>(null)
  const [showCompoundCreator, setShowCompoundCreator] = useState(false)
  const [previewStart, setPreviewStart] = useState(0)
  const [previewEnd, setPreviewEnd] = useState<number | undefined>(undefined)
  const [sortMode, setSortMode] = useState<SortMode>('timeline')
  const [showAnalyzeMenu, setShowAnalyzeMenu] = useState(false)

  // Queries
  const { data: project, isLoading: projectLoading, error: projectError } = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id),
  })

  const { data: clips = [], isLoading: clipsLoading } = useQuery({
    queryKey: ['clips', id],
    queryFn: () => getClips(id),
    enabled: !!project && project.status === 'ready',
  })

  const { data: compoundClips = [] } = useQuery({
    queryKey: ['compound-clips', id],
    queryFn: () => getCompoundClips(id),
    enabled: !!project && project.status === 'ready',
  })

  // Job polling
  const { job } = useJobPolling({
    jobId: activeJobId,
    onComplete: () => {
      setActiveJobId(null)
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      queryClient.invalidateQueries({ queryKey: ['clips', id] })
    },
    onError: () => setActiveJobId(null),
  })

  // Mutations
  const downloadMutation = useMutation({
    mutationFn: () => startDownload(id),
    onSuccess: (job) => setActiveJobId(job.id),
  })

  const analyzeMutation = useMutation({
    mutationFn: (mode?: SegmentationMode) => startAnalysis(id, mode),
    onSuccess: (job) => {
      setActiveJobId(job.id)
      setShowAnalyzeMenu(false)
    },
  })

  // Handlers
  const handleClipClick = useCallback((clip: Clip) => {
    setActiveClip(clip)
    setPreviewStart(clip.start_time)
    setPreviewEnd(clip.end_time)
  }, [])

  const toggleClipSelection = useCallback((clipId: number) => {
    setSelectedClips(prev => {
      const next = new Set(prev)
      if (next.has(clipId)) {
        next.delete(clipId)
      } else {
        next.add(clipId)
      }
      return next
    })
  }, [])

  const selectAllClips = useCallback(() => {
    setSelectedClips(new Set(clips.map(c => c.id)))
  }, [clips])

  const clearSelection = useCallback(() => {
    setSelectedClips(new Set())
  }, [])

  // Derived state
  const selectedClipsList = useMemo(() => {
    return clips.filter(c => selectedClips.has(c.id))
  }, [clips, selectedClips])

  // Sorted clips
  const sortedClips = useMemo(() => {
    if (sortMode === 'quality') {
      // Sort by quality score descending, clips without scores go to the end
      return [...clips].sort((a, b) => {
        if (a.quality_score === null && b.quality_score === null) return a.ordering - b.ordering
        if (a.quality_score === null) return 1
        if (b.quality_score === null) return -1
        return b.quality_score - a.quality_score
      })
    }
    // Default: timeline (by ordering)
    return [...clips].sort((a, b) => a.ordering - b.ordering)
  }, [clips, sortMode])

  // Check if clips have quality scores (v2 pipeline was used)
  const hasQualityScores = useMemo(() => {
    return clips.some(c => c.quality_score !== null)
  }, [clips])

  // Get generation version from first clip
  const generationVersion = useMemo(() => {
    const clip = clips.find(c => c.generation_version)
    return clip?.generation_version || null
  }, [clips])

  const videoUrl = project?.source_path ? getVideoUrl(id) : null
  const canAnalyze = project?.status === 'downloaded' || project?.status === 'ready'
  const canDownload = project?.source_type === 'youtube' && project?.status === 'pending'
  const isProcessing = activeJobId !== null

  if (projectLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-64 bg-clip-surface rounded" />
          <div className="h-96 bg-clip-surface rounded-xl" />
        </div>
      </div>
    )
  }

  if (projectError || !project) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center">
        <AlertCircle className="w-12 h-12 text-clip-error mx-auto mb-4" />
        <h2 className="text-xl font-medium text-white mb-2">Project Not Found</h2>
        <p className="text-gray-500 mb-4">
          {projectError ? (projectError as Error).message : 'The project does not exist'}
        </p>
        <Button variant="secondary" onClick={() => navigate('/projects')}>
          Back to Projects
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-clip-bg">
      {/* Header */}
      <div className="bg-clip-surface border-b border-clip-border sticky top-16 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                to="/projects"
                className="p-2 rounded-lg hover:bg-clip-elevated text-gray-400 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <h1 className="text-xl font-semibold text-white">{project.name}</h1>
                <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                  <span className={clsx('px-2 py-0.5 rounded text-xs', getStatusBgColor(project.status))}>
                    {project.status}
                  </span>
                  {project.duration && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDuration(project.duration)}
                    </span>
                  )}
                  {project.width && project.height && (
                    <span>{formatResolution(project.width, project.height)}</span>
                  )}
                  {clips.length > 0 && (
                    <span className="flex items-center gap-1">
                      <Film className="w-3 h-3" />
                      {clips.length} clips
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              {canDownload && (
                <Button
                  variant="primary"
                  onClick={() => downloadMutation.mutate()}
                  loading={downloadMutation.isPending || isProcessing}
                  icon={<Download className="w-4 h-4" />}
                >
                  Download Video
                </Button>
              )}
              {canAnalyze && (
                <div className="relative">
                  <div className="flex">
                    <Button
                      variant="primary"
                      onClick={() => analyzeMutation.mutate()}
                      loading={analyzeMutation.isPending || isProcessing}
                      icon={<Scissors className="w-4 h-4" />}
                      className="rounded-r-none"
                    >
                      {project.status === 'ready' ? 'Re-analyze' : 'Analyze & Split'}
                    </Button>
                    <Button
                      variant="primary"
                      onClick={() => setShowAnalyzeMenu(!showAnalyzeMenu)}
                      loading={analyzeMutation.isPending || isProcessing}
                      className="rounded-l-none border-l border-clip-accent/30 px-2"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </Button>
                  </div>
                  
                  {/* Analysis mode dropdown */}
                  {showAnalyzeMenu && (
                    <div className="absolute right-0 mt-2 w-64 bg-clip-surface border border-clip-border rounded-lg shadow-xl z-50">
                      <div className="p-2 border-b border-clip-border">
                        <p className="text-xs text-gray-500 uppercase tracking-wide">Pipeline Mode</p>
                      </div>
                      <div className="p-1">
                        <button
                          className="w-full flex items-start gap-3 p-3 text-left hover:bg-clip-elevated rounded-lg transition-colors"
                          onClick={() => analyzeMutation.mutate('v2')}
                        >
                          <Sparkles className="w-5 h-5 text-clip-accent flex-shrink-0 mt-0.5" />
                          <div>
                            <div className="font-medium text-white">V2 Highlight-Aware</div>
                            <div className="text-xs text-gray-500 mt-0.5">
                              Smart detection with quality scores. Best for highlights.
                            </div>
                          </div>
                        </button>
                        <button
                          className="w-full flex items-start gap-3 p-3 text-left hover:bg-clip-elevated rounded-lg transition-colors"
                          onClick={() => analyzeMutation.mutate('v1')}
                        >
                          <Zap className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                          <div>
                            <div className="font-medium text-white">V1 Scene-Based</div>
                            <div className="text-xs text-gray-500 mt-0.5">
                              Fast scene-cut detection. Good for quick splits.
                            </div>
                          </div>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Job progress */}
          {job && (
            <div className="mt-4">
              <JobProgress job={job} />
            </div>
          )}

          {/* Error state */}
          {project.status === 'error' && project.error_message && (
            <div className="mt-4 p-4 bg-clip-error/10 border border-clip-error/30 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-clip-error flex-shrink-0" />
                <div>
                  <h3 className="font-medium text-clip-error">Error</h3>
                  <p className="text-sm text-gray-400 mt-1">{project.error_message}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        {project.status === 'ready' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Video + Editor */}
            <div className="lg:col-span-2 space-y-4">
              {/* Video player */}
              {videoUrl && (
                <div className="bg-clip-surface border border-clip-border rounded-xl overflow-hidden">
                  <VideoPlayer
                    src={videoUrl}
                    startTime={previewStart}
                    endTime={previewEnd}
                    autoSeek={!!activeClip}
                  />
                </div>
              )}

              {/* Clip editor */}
              {activeClip && project.duration && (
                <ClipEditor
                  clip={activeClip}
                  projectId={id}
                  projectDuration={project.duration}
                  onClose={() => setActiveClip(null)}
                />
              )}

              {/* Selection toolbar */}
              {clips.length > 0 && (
                <div className="flex items-center justify-between p-3 bg-clip-surface border border-clip-border rounded-lg">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={selectedClips.size === clips.length ? clearSelection : selectAllClips}
                      icon={selectedClips.size === clips.length ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                    >
                      {selectedClips.size === clips.length ? 'Deselect All' : 'Select All'}
                    </Button>
                    {selectedClips.size > 0 && (
                      <span className="text-sm text-gray-500">
                        {selectedClips.size} selected
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {/* Sort toggle */}
                    {hasQualityScores && (
                      <div className="flex items-center gap-1 bg-clip-elevated rounded-lg p-1">
                        <button
                          className={clsx(
                            'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors',
                            sortMode === 'timeline'
                              ? 'bg-clip-accent text-white'
                              : 'text-gray-400 hover:text-white'
                          )}
                          onClick={() => setSortMode('timeline')}
                        >
                          <Clock className="w-3.5 h-3.5" />
                          Timeline
                        </button>
                        <button
                          className={clsx(
                            'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors',
                            sortMode === 'quality'
                              ? 'bg-clip-accent text-white'
                              : 'text-gray-400 hover:text-white'
                          )}
                          onClick={() => setSortMode('quality')}
                        >
                          <Star className="w-3.5 h-3.5" />
                          Quality
                        </button>
                      </div>
                    )}
                    
                    {/* Generation version badge */}
                    {generationVersion && (
                      <span className={clsx(
                        'text-xs px-2 py-1 rounded',
                        generationVersion === 'v2' 
                          ? 'bg-clip-accent/20 text-clip-accent' 
                          : 'bg-gray-700 text-gray-400'
                      )}>
                        {generationVersion === 'v2' ? '✨ V2 Pipeline' : 'V1 Pipeline'}
                      </span>
                    )}
                    
                    {selectedClips.size >= 2 && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setShowCompoundCreator(true)}
                        icon={<Layers className="w-4 h-4" />}
                      >
                        Combine Clips
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {/* Clips grid */}
              {clipsLoading ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="aspect-video bg-clip-surface rounded-lg shimmer" />
                  ))}
                </div>
              ) : clips.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                  {sortedClips.map((clip, index) => (
                    <ClipCard
                      key={clip.id}
                      clip={clip}
                      projectId={id}
                      active={activeClip?.id === clip.id}
                      selected={selectedClips.has(clip.id)}
                      onClick={() => handleClipClick(clip)}
                      onToggleSelection={() => toggleClipSelection(clip.id)}
                      showQualityScore={sortMode === 'quality'}
                      rank={sortMode === 'quality' ? index + 1 : undefined}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 bg-clip-surface border border-clip-border rounded-xl">
                  <Scissors className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-white mb-2">No clips yet</h3>
                  <p className="text-gray-500 mb-4">
                    Click "Analyze & Split" to automatically generate clips
                  </p>
                </div>
              )}
            </div>

            {/* Right: Export panel */}
            <div className="space-y-4">
              <ExportPanel
                project={project}
                selectedClips={selectedClipsList}
                compoundClips={compoundClips}
                onClearSelection={clearSelection}
              />
            </div>
          </div>
        )}

        {/* Pending/downloading states */}
        {(project.status === 'pending' || project.status === 'downloading') && (
          <div className="text-center py-16">
            <Download className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h3 className="text-xl font-medium text-white mb-2">
              {project.status === 'pending' ? 'Ready to Download' : 'Downloading...'}
            </h3>
            <p className="text-gray-500 mb-6">
              {project.status === 'pending' 
                ? 'Click the download button to fetch the video from YouTube'
                : 'Please wait while the video is being downloaded'
              }
            </p>
          </div>
        )}

        {/* Downloaded state */}
        {project.status === 'downloaded' && (
          <div className="text-center py-16">
            <Scissors className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h3 className="text-xl font-medium text-white mb-2">Video Ready</h3>
            <p className="text-gray-500 mb-6">
              Click "Analyze & Split" to detect scenes and generate clips
            </p>
          </div>
        )}

        {/* Analyzing state */}
        {project.status === 'analyzing' && (
          <div className="text-center py-16">
            <RefreshCw className="w-16 h-16 text-clip-accent mx-auto mb-4 animate-spin" />
            <h3 className="text-xl font-medium text-white mb-2">Analyzing Video</h3>
            <p className="text-gray-500 mb-6">
              Detecting scenes and generating clips...
            </p>
          </div>
        )}
      </div>

      {/* Compound clip creator modal */}
      {showCompoundCreator && (
        <CompoundClipCreator
          projectId={id}
          selectedClips={selectedClipsList}
          onClose={() => setShowCompoundCreator(false)}
          onSuccess={() => setSelectedClips(new Set())}
        />
      )}
    </div>
  )
}

