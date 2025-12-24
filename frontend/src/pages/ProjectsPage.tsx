import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, FolderOpen, Clock, Film, Trash2, AlertTriangle, Youtube, HardDrive } from 'lucide-react'
import { getProjects, deleteProject, getHealth } from '../api/client'
import { Button } from '../components/Button'
import { CreateProjectModal } from '../components/CreateProjectModal'
import { formatDuration, formatRelativeTime, getStatusBgColor } from '../utils/format'
import type { Project } from '../types'
import clsx from 'clsx'

export function ProjectsPage() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  // Health check
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    staleTime: 30000,
  })

  // Projects list
  const { data: projects, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setDeleteConfirm(null)
    },
  })

  const missingDeps = health && (
    !health.ffmpeg_available || 
    !health.ffprobe_available || 
    !health.ytdlp_available
  )

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Projects</h1>
          <p className="text-gray-500 mt-1">Manage your video clip extraction projects</p>
        </div>
        <Button
          variant="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={() => setShowCreateModal(true)}
        >
          New Project
        </Button>
      </div>

      {/* Dependencies warning */}
      {missingDeps && (
        <div className="mb-6 p-4 bg-clip-warning/10 border border-clip-warning/30 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-clip-warning flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-clip-warning">Missing Dependencies</h3>
            <p className="text-sm text-gray-400 mt-1">
              {health?.message}
            </p>
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-48 bg-clip-surface rounded-xl shimmer" />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="text-center py-12">
          <p className="text-clip-error">Failed to load projects</p>
          <p className="text-sm text-gray-500 mt-1">{(error as Error).message}</p>
        </div>
      )}

      {/* Empty state */}
      {projects && projects.length === 0 && (
        <div className="text-center py-16">
          <div className="w-16 h-16 mx-auto bg-clip-elevated rounded-full flex items-center justify-center mb-4">
            <FolderOpen className="w-8 h-8 text-gray-500" />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">No projects yet</h3>
          <p className="text-gray-500 mb-6">
            Create your first project to start extracting clips
          </p>
          <Button
            variant="primary"
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setShowCreateModal(true)}
          >
            Create Project
          </Button>
        </div>
      )}

      {/* Projects grid */}
      {projects && projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDelete={() => setDeleteConfirm(project.id)}
            />
          ))}
        </div>
      )}

      {/* Delete confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDeleteConfirm(null)} />
          <div className="relative bg-clip-surface border border-clip-border rounded-xl p-6 max-w-sm mx-4">
            <h3 className="text-lg font-medium text-white mb-2">Delete Project?</h3>
            <p className="text-gray-400 text-sm mb-4">
              This will permanently delete the project and all its clips. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setDeleteConfirm(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => deleteMutation.mutate(deleteConfirm)}
                loading={deleteMutation.isPending}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Create modal */}
      <CreateProjectModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
      />
    </div>
  )
}

interface ProjectCardProps {
  project: Project
  onDelete: () => void
}

function ProjectCard({ project, onDelete }: ProjectCardProps) {
  return (
    <div className="group bg-clip-surface border border-clip-border rounded-xl overflow-hidden hover:border-gray-600 transition-colors">
      {/* Thumbnail placeholder */}
      <div className="aspect-video bg-clip-elevated flex items-center justify-center relative">
        <Film className="w-12 h-12 text-gray-600" />
        
        {/* Source type badge */}
        <div className="absolute top-2 left-2">
          {project.source_type === 'youtube' ? (
            <div className="flex items-center gap-1 px-2 py-1 bg-red-600/80 rounded text-xs text-white">
              <Youtube className="w-3 h-3" />
              YouTube
            </div>
          ) : (
            <div className="flex items-center gap-1 px-2 py-1 bg-clip-elevated/80 rounded text-xs text-gray-300">
              <HardDrive className="w-3 h-3" />
              Local
            </div>
          )}
        </div>

        {/* Status badge */}
        <div className={clsx(
          'absolute top-2 right-2 px-2 py-1 rounded text-xs font-medium',
          getStatusBgColor(project.status)
        )}>
          {project.status}
        </div>

        {/* Delete button */}
        <button
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onDelete()
          }}
          className="absolute bottom-2 right-2 p-1.5 rounded bg-black/50 text-gray-400 hover:text-clip-error opacity-0 group-hover:opacity-100 transition-all"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Info */}
      <Link to={`/projects/${project.id}`} className="block p-4">
        <h3 className="font-medium text-white truncate group-hover:text-clip-accent transition-colors">
          {project.name}
        </h3>
        
        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
          {project.duration && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(project.duration)}
            </span>
          )}
          {project.clip_count !== null && project.clip_count > 0 && (
            <span className="flex items-center gap-1">
              <Film className="w-3 h-3" />
              {project.clip_count} clips
            </span>
          )}
        </div>

        <p className="text-xs text-gray-600 mt-2">
          Created {formatRelativeTime(project.created_at)}
        </p>
      </Link>
    </div>
  )
}

