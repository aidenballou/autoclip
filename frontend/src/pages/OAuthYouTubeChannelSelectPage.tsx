import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { AlertCircle, RefreshCw, Youtube } from 'lucide-react'

import {
  finalizeYouTubeChannelSelection,
  getPendingYouTubeChannels,
} from '../api/client'
import type { YouTubeChannelOption } from '../types'
import { Button } from '../components/Button'

function parsePositiveInt(value: string | null): number | null {
  if (!value) return null
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) return null
  return parsed
}

export function OAuthYouTubeChannelSelectPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const location = useLocation()

  const accountId = useMemo(
    () => parsePositiveInt(searchParams.get('account_id')),
    [searchParams]
  )
  const selectionToken = searchParams.get('selection_token')

  const [channels, setChannels] = useState<YouTubeChannelOption[]>(
    () => (location.state as { channels?: YouTubeChannelOption[] } | null)?.channels || []
  )
  const [selectedChannelId, setSelectedChannelId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      if (!accountId || !selectionToken) {
        setError('Missing channel selection context. Please reconnect your account.')
        setLoading(false)
        return
      }

      // If we have channels from navigation state, still validate pending state in background.
      if (channels.length > 0) {
        setLoading(false)
      }

      try {
        const pending = await getPendingYouTubeChannels(accountId, selectionToken)
        setChannels(pending.channels)
        if (!selectedChannelId && pending.channels.length > 0) {
          setSelectedChannelId(pending.channels[0].channel_id)
        }
      } catch (e) {
        if (channels.length === 0) {
          setError((e as Error).message || 'Unable to load channels. Please reconnect.')
        }
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [accountId, selectionToken])

  const onFinalize = async () => {
    if (!accountId || !selectionToken || !selectedChannelId) {
      setError('Select a channel before continuing.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await finalizeYouTubeChannelSelection(accountId, selectionToken, selectedChannelId)
      navigate('/niches?oauth=connected', { replace: true })
    } catch (e) {
      setError((e as Error).message || 'Failed to connect selected channel.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-clip-bg flex items-center justify-center px-4">
      <div className="w-full max-w-xl bg-clip-surface border border-clip-border rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-3">
          <Youtube className="w-6 h-6 text-red-400" />
          <div>
            <h1 className="text-lg font-semibold text-white">Choose YouTube Channel</h1>
            <p className="text-sm text-gray-400">
              This Google login has multiple channels. Pick the one to bind to this account.
            </p>
          </div>
        </div>

        {loading && (
          <div className="text-center py-6">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-clip-accent mb-2" />
            <p className="text-sm text-gray-400">Loading available channels...</p>
          </div>
        )}

        {!loading && channels.length > 0 && (
          <div className="space-y-2">
            {channels.map(channel => (
              <button
                key={channel.channel_id}
                type="button"
                onClick={() => setSelectedChannelId(channel.channel_id)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedChannelId === channel.channel_id
                    ? 'border-clip-accent bg-clip-accent/10'
                    : 'border-clip-border bg-clip-elevated hover:border-gray-500'
                }`}
              >
                <div className="font-medium text-white">{channel.title}</div>
                <div className="text-xs text-gray-400 mt-0.5">{channel.handle}</div>
              </button>
            ))}
          </div>
        )}

        {!loading && channels.length === 0 && (
          <div className="p-3 rounded-lg border border-yellow-500/20 bg-yellow-500/10 text-yellow-200 text-sm">
            No selectable channels found for this OAuth session. Reconnect and try again.
          </div>
        )}

        {error && (
          <div className="p-3 rounded-lg border border-red-500/20 bg-red-500/10 text-red-200 text-sm flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={() => navigate('/niches')}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={onFinalize}
            disabled={!selectedChannelId || channels.length === 0}
            loading={submitting}
          >
            Connect Channel
          </Button>
        </div>
      </div>
    </div>
  )
}

