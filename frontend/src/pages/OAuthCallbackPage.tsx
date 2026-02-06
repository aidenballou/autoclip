import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { RefreshCw, AlertCircle } from 'lucide-react'
import { completeOAuth } from '../api/client'
import { Button } from '../components/Button'

type CallbackStatus = 'processing' | 'error'

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

  return 'OAuth connection failed. Please try again.'
}

function getProviderError(searchParams: URLSearchParams): string | null {
  const providerError = searchParams.get('error')
  if (!providerError) return null

  const providerDescription = searchParams.get('error_description')
  if (providerDescription) return providerDescription

  return providerError.replace(/_/g, ' ')
}

export function OAuthCallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<CallbackStatus>('processing')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const hasStarted = useRef(false)

  useEffect(() => {
    if (hasStarted.current) return
    hasStarted.current = true

    const providerError = getProviderError(searchParams)
    if (providerError) {
      setStatus('error')
      setErrorMessage(`Authorization failed: ${providerError}`)
      return
    }

    const code = searchParams.get('code')
    const state = searchParams.get('state')

    if (!code) {
      setStatus('error')
      setErrorMessage('Missing OAuth authorization code from provider.')
      return
    }

    if (!state) {
      setStatus('error')
      setErrorMessage('Missing OAuth state. Cannot determine which account to connect.')
      return
    }

    const accountId = Number(state)
    if (!Number.isInteger(accountId) || accountId <= 0) {
      setStatus('error')
      setErrorMessage('Invalid OAuth state. Expected a valid account ID.')
      return
    }

    const redirectUri = `${window.location.origin}/oauth/callback`

    const run = async () => {
      try {
        const result = await completeOAuth(accountId, code, redirectUri)
        if (result.status === 'connected') {
          navigate('/niches?oauth=connected', { replace: true })
          return
        }
        navigate(
          `/oauth/youtube-channel-select?account_id=${result.account_id}&selection_token=${encodeURIComponent(result.selection_token)}`,
          {
            replace: true,
            state: { channels: result.channels },
          }
        )
      } catch (error) {
        setStatus('error')
        setErrorMessage(getErrorMessage(error))
      }
    }

    void run()
  }, [navigate, searchParams])

  return (
    <div className="min-h-screen bg-clip-bg flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-clip-surface border border-clip-border rounded-xl p-6">
        {status === 'processing' && (
          <div className="text-center">
            <RefreshCw className="w-8 h-8 text-clip-accent animate-spin mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-white mb-2">Connecting Account</h1>
            <p className="text-sm text-gray-400">
              Completing OAuth. You will be redirected shortly.
            </p>
          </div>
        )}

        {status === 'error' && (
          <div>
            <div className="flex items-start gap-3 mb-4">
              <AlertCircle className="w-6 h-6 text-red-400 mt-0.5" />
              <div>
                <h1 className="text-lg font-semibold text-white">Connection Failed</h1>
                <p className="text-sm text-gray-300 mt-2">
                  {errorMessage || 'OAuth callback failed.'}
                </p>
              </div>
            </div>
            <Button variant="secondary" onClick={() => navigate('/niches')}>
              Back to Niches
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
