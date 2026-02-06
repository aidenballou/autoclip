import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Plus,
  Trash2,
  Users,
  Youtube,
  Instagram,
  Twitter,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import {
  getNiches,
  createNiche,
  deleteNiche,
  getNicheAccounts,
  createAccount,
  deleteAccount,
  getOAuthUrl,
} from '../api/client'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { Modal } from '../components/Modal'
import type { Niche, Account, Platform, CreateNicheRequest, CreateAccountRequest } from '../types'
import clsx from 'clsx'

const PLATFORMS: { value: Platform; label: string; icon: React.ReactNode }[] = [
  { value: 'youtube_shorts', label: 'YouTube Shorts', icon: <Youtube className="w-4 h-4" /> },
  { value: 'tiktok', label: 'TikTok', icon: <span className="text-xs font-bold">TT</span> },
  { value: 'instagram_reels', label: 'Instagram Reels', icon: <Instagram className="w-4 h-4" /> },
  { value: 'twitter', label: 'X / Twitter', icon: <Twitter className="w-4 h-4" /> },
  { value: 'snapchat', label: 'Snapchat', icon: <span className="text-xs font-bold">SC</span> },
]

function getPlatformInfo(platform: Platform) {
  return PLATFORMS.find(p => p.value === platform) || { value: platform, label: platform, icon: null }
}

function AuthStatusBadge({ status }: { status: string }) {
  const config = {
    connected: { color: 'bg-green-500/20 text-green-400', icon: <CheckCircle className="w-3 h-3" /> },
    not_connected: { color: 'bg-gray-500/20 text-gray-400', icon: <XCircle className="w-3 h-3" /> },
    expired: { color: 'bg-yellow-500/20 text-yellow-400', icon: <AlertCircle className="w-3 h-3" /> },
    error: { color: 'bg-red-500/20 text-red-400', icon: <XCircle className="w-3 h-3" /> },
  }[status] || { color: 'bg-gray-500/20 text-gray-400', icon: null }

  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs', config.color)}>
      {config.icon}
      {status.replace('_', ' ')}
    </span>
  )
}

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const response = (error as {
      response?: { data?: { detail?: string; message?: string } }
    }).response
    if (response?.data?.detail) return response.data.detail
    if (response?.data?.message) return response.data.message

    const message = (error as { message?: string }).message
    if (message) return message
  }

  return 'Unable to connect account. Please try again.'
}

export function NichesPage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedNicheId, setSelectedNicheId] = useState<number | null>(null)
  const [showCreateNicheModal, setShowCreateNicheModal] = useState(false)
  const [showCreateAccountModal, setShowCreateAccountModal] = useState(false)
  const [connectError, setConnectError] = useState<string | null>(null)
  const [connectSuccess, setConnectSuccess] = useState<string | null>(null)
  const [connectingAccountId, setConnectingAccountId] = useState<number | null>(null)

  // Queries
  const { data: niches = [], isLoading } = useQuery({
    queryKey: ['niches'],
    queryFn: getNiches,
  })

  const { data: accounts = [], isLoading: accountsLoading } = useQuery({
    queryKey: ['accounts', selectedNicheId],
    queryFn: () => selectedNicheId ? getNicheAccounts(selectedNicheId) : Promise.resolve([]),
    enabled: !!selectedNicheId,
  })

  const selectedNiche = niches.find(n => n.id === selectedNicheId)

  // Mutations
  const deleteNicheMutation = useMutation({
    mutationFn: deleteNiche,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['niches'] })
      if (selectedNicheId) setSelectedNicheId(null)
    },
  })

  const deleteAccountMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedNicheId] })
      queryClient.invalidateQueries({ queryKey: ['niches'] })
    },
  })

  const handleDeleteNiche = async (niche: Niche) => {
    if (confirm(`Delete "${niche.name}" and all its accounts?`)) {
      deleteNicheMutation.mutate(niche.id)
    }
  }

  const handleDeleteAccount = async (account: Account) => {
    if (confirm(`Remove ${account.handle} from this niche?`)) {
      deleteAccountMutation.mutate(account.id)
    }
  }

  const handleConnectAccount = async (account: Account) => {
    if (account.platform !== 'youtube_shorts') return

    setConnectError(null)
    setConnectSuccess(null)
    setConnectingAccountId(account.id)

    try {
      const redirectUri = `${window.location.origin}/oauth/callback`
      const { url } = await getOAuthUrl(account.id, redirectUri)

      if (!url) {
        throw new Error('OAuth URL was not returned from the server')
      }

      window.location.assign(url)
    } catch (error) {
      setConnectError(getErrorMessage(error))
      setConnectingAccountId(null)
    }
  }

  useEffect(() => {
    if (searchParams.get('oauth') !== 'connected') return

    setConnectSuccess('Account connected successfully.')
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('oauth')
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams])

  return (
    <div className="min-h-screen bg-clip-bg">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Niches & Accounts</h1>
            <p className="text-gray-500 mt-1">
              Manage your content niches and connected social media accounts
            </p>
          </div>
          <Button
            variant="primary"
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setShowCreateNicheModal(true)}
          >
            Create Niche
          </Button>
        </div>

        {(connectError || connectSuccess) && (
          <div className={clsx(
            'mb-6 px-4 py-3 rounded-lg border text-sm',
            connectError
              ? 'bg-red-500/10 text-red-300 border-red-500/20'
              : 'bg-green-500/10 text-green-300 border-green-500/20'
          )}>
            {connectError || connectSuccess}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Niches List */}
          <div className="lg:col-span-1">
            <div className="bg-clip-surface border border-clip-border rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-clip-border">
                <h2 className="font-medium text-white">Your Niches</h2>
              </div>
              
              {isLoading ? (
                <div className="p-8 text-center">
                  <RefreshCw className="w-6 h-6 text-gray-500 animate-spin mx-auto" />
                </div>
              ) : niches.length === 0 ? (
                <div className="p-8 text-center">
                  <Users className="w-10 h-10 text-gray-600 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">No niches yet</p>
                  <p className="text-gray-600 text-xs mt-1">Create a niche to get started</p>
                </div>
              ) : (
                <div className="divide-y divide-clip-border">
                  {niches.map(niche => (
                    <button
                      key={niche.id}
                      onClick={() => setSelectedNicheId(niche.id)}
                      className={clsx(
                        'w-full px-4 py-3 text-left hover:bg-clip-elevated transition-colors',
                        selectedNicheId === niche.id && 'bg-clip-elevated'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium text-white">{niche.name}</h3>
                          {niche.description && (
                            <p className="text-xs text-gray-500 mt-0.5 truncate max-w-[200px]">
                              {niche.description}
                            </p>
                          )}
                        </div>
                        <span className="text-xs text-gray-500">
                          {niche.account_count || 0} accounts
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Accounts Panel */}
          <div className="lg:col-span-2">
            {selectedNiche ? (
              <div className="bg-clip-surface border border-clip-border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-clip-border flex items-center justify-between">
                  <div>
                    <h2 className="font-medium text-white">{selectedNiche.name}</h2>
                    {selectedNiche.description && (
                      <p className="text-sm text-gray-500">{selectedNiche.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Plus className="w-4 h-4" />}
                      onClick={() => setShowCreateAccountModal(true)}
                    >
                      Add Account
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Trash2 className="w-4 h-4" />}
                      onClick={() => handleDeleteNiche(selectedNiche)}
                      className="text-red-400 hover:text-red-300"
                    />
                  </div>
                </div>

                {/* Default Settings */}
                {(selectedNiche.default_hashtags.length > 0 || selectedNiche.default_caption_template) && (
                  <div className="px-4 py-3 border-b border-clip-border bg-clip-elevated/30">
                    <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-2">Default Settings</h3>
                    {selectedNiche.default_hashtags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {selectedNiche.default_hashtags.map(tag => (
                          <span key={tag} className="px-2 py-0.5 bg-clip-accent/20 text-clip-accent text-xs rounded">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                    {selectedNiche.default_caption_template && (
                      <p className="text-xs text-gray-400 italic">
                        "{selectedNiche.default_caption_template}"
                      </p>
                    )}
                  </div>
                )}

                {/* Accounts List */}
                {accountsLoading ? (
                  <div className="p-8 text-center">
                    <RefreshCw className="w-6 h-6 text-gray-500 animate-spin mx-auto" />
                  </div>
                ) : accounts.length === 0 ? (
                  <div className="p-8 text-center">
                    <Users className="w-10 h-10 text-gray-600 mx-auto mb-3" />
                    <p className="text-gray-500 text-sm">No accounts in this niche</p>
                    <p className="text-gray-600 text-xs mt-1">Add accounts to publish clips</p>
                  </div>
                ) : (
                  <div className="divide-y divide-clip-border">
                    {accounts.map(account => {
                      const platform = getPlatformInfo(account.platform)
                      const isYouTubeAccount = account.platform === 'youtube_shorts'
                      const isNotConnected = account.auth_status !== 'connected'
                      const needsYouTubeReconnect =
                        isYouTubeAccount &&
                        account.auth_status === 'connected' &&
                        !account.platform_user_id
                      return (
                        <div key={account.id} className="px-4 py-3 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-clip-elevated flex items-center justify-center">
                              {platform.icon}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-white">{account.handle}</span>
                                <AuthStatusBadge status={account.auth_status} />
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-500">{platform.label}</span>
                                {!isYouTubeAccount && (
                                  <span className="text-xs px-2 py-0.5 rounded bg-clip-elevated text-gray-400 border border-clip-border">
                                    Export-only
                                  </span>
                                )}
                                {needsYouTubeReconnect && (
                                  <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/15 text-yellow-300 border border-yellow-500/30">
                                    Reconnect required
                                  </span>
                                )}
                              </div>
                              {isYouTubeAccount && account.auth_status === 'connected' && account.platform_user_id && (
                                <div className="text-xs text-gray-500 mt-0.5">
                                  Channel: {account.display_name || account.handle}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {isNotConnected && isYouTubeAccount && (
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => handleConnectAccount(account)}
                                loading={connectingAccountId === account.id}
                                disabled={connectingAccountId !== null && connectingAccountId !== account.id}
                              >
                                Connect
                              </Button>
                            )}
                            {needsYouTubeReconnect && (
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => handleConnectAccount(account)}
                                loading={connectingAccountId === account.id}
                                disabled={connectingAccountId !== null && connectingAccountId !== account.id}
                              >
                                Reconnect
                              </Button>
                            )}
                            {isNotConnected && !isYouTubeAccount && (
                              <Button variant="secondary" size="sm" disabled>
                                Export-only
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={<Trash2 className="w-4 h-4" />}
                              onClick={() => handleDeleteAccount(account)}
                              className="text-red-400 hover:text-red-300"
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-clip-surface border border-clip-border rounded-xl p-12 text-center">
                <Users className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-white mb-2">Select a Niche</h3>
                <p className="text-gray-500 text-sm">
                  Choose a niche from the list to view and manage its accounts
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Create Niche Modal */}
      <CreateNicheModal
        open={showCreateNicheModal}
        onClose={() => setShowCreateNicheModal(false)}
        onSuccess={(niche) => {
          setShowCreateNicheModal(false)
          setSelectedNicheId(niche.id)
        }}
      />

      {/* Create Account Modal */}
      {selectedNicheId && (
        <CreateAccountModal
          open={showCreateAccountModal}
          onClose={() => setShowCreateAccountModal(false)}
          nicheId={selectedNicheId}
        />
      )}
    </div>
  )
}

function CreateNicheModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean
  onClose: () => void
  onSuccess: (niche: Niche) => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [captionTemplate, setCaptionTemplate] = useState('')

  const mutation = useMutation({
    mutationFn: (data: CreateNicheRequest) => createNiche(data),
    onSuccess: (niche) => {
      queryClient.invalidateQueries({ queryKey: ['niches'] })
      setName('')
      setDescription('')
      setHashtags('')
      setCaptionTemplate('')
      onSuccess(niche)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    mutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
      default_hashtags: hashtags
        .split(/[,\s]+/)
        .map(t => t.replace(/^#/, '').trim())
        .filter(Boolean),
      default_caption_template: captionTemplate.trim() || undefined,
    })
  }

  if (!open) return null

  return (
    <Modal open={open} title="Create Niche" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Niche Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., NBA Highlights"
          required
        />
        <Input
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What this niche is about"
        />
        <Input
          label="Default Hashtags (comma separated)"
          value={hashtags}
          onChange={(e) => setHashtags(e.target.value)}
          placeholder="nba, basketball, highlights"
        />
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">
            Default Caption Template
          </label>
          <textarea
            value={captionTemplate}
            onChange={(e) => setCaptionTemplate(e.target.value)}
            placeholder="Check out this amazing play! 🏀"
            rows={2}
            className="w-full px-3 py-2 bg-clip-elevated border border-clip-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-clip-accent focus:border-transparent resize-none"
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            loading={mutation.isPending}
            disabled={!name.trim()}
          >
            Create Niche
          </Button>
        </div>
        {mutation.isError && (
          <p className="text-sm text-clip-error">
            {(mutation.error as Error).message}
          </p>
        )}
      </form>
    </Modal>
  )
}

function CreateAccountModal({
  open,
  onClose,
  nicheId,
}: {
  open: boolean
  onClose: () => void
  nicheId: number
}) {
  const queryClient = useQueryClient()
  const [platform, setPlatform] = useState<Platform>('youtube_shorts')
  const [handle, setHandle] = useState('')
  const [displayName, setDisplayName] = useState('')

  const mutation = useMutation({
    mutationFn: (data: CreateAccountRequest) => createAccount(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts', nicheId] })
      queryClient.invalidateQueries({ queryKey: ['niches'] })
      setHandle('')
      setDisplayName('')
      onClose()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!handle.trim()) return

    mutation.mutate({
      niche_id: nicheId,
      platform,
      handle: handle.trim(),
      display_name: displayName.trim() || undefined,
    })
  }

  if (!open) return null

  return (
    <Modal open={open} title="Add Account" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">
            Platform
          </label>
          <div className="grid grid-cols-2 gap-2">
            {PLATFORMS.map(p => (
              <button
                key={p.value}
                type="button"
                onClick={() => setPlatform(p.value)}
                className={clsx(
                  'flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors',
                  platform === p.value
                    ? 'border-clip-accent bg-clip-accent/10 text-white'
                    : 'border-clip-border bg-clip-elevated text-gray-400 hover:text-white'
                )}
              >
                {p.icon}
                <span className="text-sm">{p.label}</span>
              </button>
            ))}
          </div>
        </div>
        <Input
          label="Handle / Username"
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
          placeholder="@yourhandle"
          required
        />
        <Input
          label="Display Name (optional)"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Channel or page name"
        />
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            loading={mutation.isPending}
            disabled={!handle.trim()}
          >
            Add Account
          </Button>
        </div>
        {mutation.isError && (
          <p className="text-sm text-clip-error">
            {(mutation.error as Error).message}
          </p>
        )}
      </form>
    </Modal>
  )
}
