import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Link2, Upload, Folder } from 'lucide-react'
import { Modal } from './Modal'
import { Input } from './Input'
import { Button } from './Button'
import { createProjectYoutube, createProjectLocal } from '../api/client'
import clsx from 'clsx'

interface CreateProjectModalProps {
  open: boolean
  onClose: () => void
}

type TabType = 'youtube' | 'local' | 'upload'

export function CreateProjectModal({ open, onClose }: CreateProjectModalProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabType>('youtube')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [localPath, setLocalPath] = useState('')
  const [projectName, setProjectName] = useState('')
  const [error, setError] = useState('')

  const youtubeMutation = useMutation({
    mutationFn: () => createProjectYoutube({
      youtube_url: youtubeUrl,
      name: projectName || undefined,
    }),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      handleClose()
      navigate(`/projects/${project.id}`)
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create project')
    },
  })

  const localMutation = useMutation({
    mutationFn: () => createProjectLocal({
      file_path: localPath,
      name: projectName || undefined,
    }),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      handleClose()
      navigate(`/projects/${project.id}`)
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create project')
    },
  })

  const handleClose = () => {
    setYoutubeUrl('')
    setLocalPath('')
    setProjectName('')
    setError('')
    onClose()
  }

  const handleSubmit = () => {
    setError('')
    if (activeTab === 'youtube') {
      if (!youtubeUrl) {
        setError('Please enter a YouTube URL')
        return
      }
      youtubeMutation.mutate()
    } else if (activeTab === 'local') {
      if (!localPath) {
        setError('Please enter a file path')
        return
      }
      localMutation.mutate()
    }
  }

  const isLoading = youtubeMutation.isPending || localMutation.isPending

  const tabs = [
    { id: 'youtube' as const, label: 'YouTube URL', icon: <Link2 className="w-4 h-4" /> },
    { id: 'local' as const, label: 'Local File', icon: <Folder className="w-4 h-4" /> },
  ]

  return (
    <Modal open={open} onClose={handleClose} title="Create New Project" size="lg">
      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-clip-elevated rounded-lg mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all',
              activeTab === tab.id
                ? 'bg-clip-accent text-white'
                : 'text-gray-400 hover:text-white'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="space-y-4">
        {activeTab === 'youtube' && (
          <>
            <Input
              label="YouTube URL"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              hint="Paste a YouTube video URL"
            />
            <Input
              label="Project Name (optional)"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="Will be fetched from YouTube if empty"
            />
          </>
        )}

        {activeTab === 'local' && (
          <>
            <Input
              label="File Path"
              value={localPath}
              onChange={(e) => setLocalPath(e.target.value)}
              placeholder="/Users/you/Videos/my-video.mp4"
              hint="Full path to a video file on your computer"
            />
            <div className="p-3 bg-clip-elevated rounded-lg text-xs text-gray-400">
              <p className="font-medium text-gray-300 mb-1">Tip: Get the file path easily</p>
              <p>In Finder, right-click your video file while holding Option, then select "Copy as Pathname"</p>
            </div>
            <Input
              label="Project Name (optional)"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="Will use filename if empty"
            />
          </>
        )}

        {error && (
          <div className="p-3 bg-clip-error/10 border border-clip-error/30 rounded-lg text-sm text-clip-error">
            {error}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3 mt-6">
        <Button variant="secondary" onClick={handleClose}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={handleSubmit}
          loading={isLoading}
        >
          Create Project
        </Button>
      </div>
    </Modal>
  )
}

