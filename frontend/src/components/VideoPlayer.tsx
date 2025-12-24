import { useRef, useEffect, useState, useCallback } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize } from 'lucide-react'
import { formatDuration } from '../utils/format'
import clsx from 'clsx'

interface VideoPlayerProps {
  src: string
  startTime?: number
  endTime?: number
  autoSeek?: boolean
  onTimeUpdate?: (currentTime: number) => void
  className?: string
}

export function VideoPlayer({
  src,
  startTime = 0,
  endTime,
  autoSeek = false,
  onTimeUpdate,
  className,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState(1)

  // Seek to start time when it changes
  useEffect(() => {
    if (autoSeek && videoRef.current && startTime >= 0) {
      videoRef.current.currentTime = startTime
      setCurrentTime(startTime)
    }
  }, [startTime, autoSeek])

  // Stop at end time
  useEffect(() => {
    if (endTime && currentTime >= endTime && isPlaying) {
      videoRef.current?.pause()
      setIsPlaying(false)
    }
  }, [currentTime, endTime, isPlaying])

  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      const time = videoRef.current.currentTime
      setCurrentTime(time)
      onTimeUpdate?.(time)
    }
  }, [onTimeUpdate])

  const handleLoadedMetadata = useCallback(() => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration)
    }
  }, [])

  const togglePlay = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        // If at end, seek to start
        if (endTime && currentTime >= endTime) {
          videoRef.current.currentTime = startTime
        }
        videoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }, [isPlaying, currentTime, endTime, startTime])

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value)
    if (videoRef.current) {
      videoRef.current.currentTime = time
      setCurrentTime(time)
    }
  }, [])

  const toggleMute = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted
      setIsMuted(!isMuted)
    }
  }, [isMuted])

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = parseFloat(e.target.value)
    if (videoRef.current) {
      videoRef.current.volume = vol
      setVolume(vol)
      setIsMuted(vol === 0)
    }
  }, [])

  const handleFullscreen = useCallback(() => {
    if (videoRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen()
      } else {
        videoRef.current.requestFullscreen()
      }
    }
  }, [])

  // Display bounds
  const displayStart = startTime
  const displayEnd = endTime || duration
  const displayDuration = displayEnd - displayStart

  return (
    <div className={clsx('relative group bg-black rounded-lg overflow-hidden', className)}>
      <video
        ref={videoRef}
        src={src}
        className="w-full aspect-video"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Controls overlay */}
      <div className="absolute inset-0 flex flex-col justify-end opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-t from-black/80 via-transparent to-transparent">
        {/* Progress bar */}
        <div className="px-4 mb-2">
          <input
            type="range"
            min={0}
            max={duration}
            step={0.01}
            value={currentTime}
            onChange={handleSeek}
            className="w-full cursor-pointer"
          />
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 px-4 pb-4">
          {/* Play/Pause */}
          <button
            onClick={togglePlay}
            className="p-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
          >
            {isPlaying ? (
              <Pause className="w-5 h-5 text-white" />
            ) : (
              <Play className="w-5 h-5 text-white" />
            )}
          </button>

          {/* Time display */}
          <div className="text-sm text-white font-mono">
            <span>{formatDuration(currentTime)}</span>
            <span className="text-gray-400"> / </span>
            <span className="text-gray-400">{formatDuration(duration)}</span>
          </div>

          {/* Clip bounds indicator */}
          {(startTime > 0 || endTime) && (
            <div className="text-xs text-clip-accent font-mono">
              [{formatDuration(displayStart)} - {formatDuration(displayEnd)}]
            </div>
          )}

          <div className="flex-1" />

          {/* Volume */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggleMute}
              className="p-1.5 rounded text-gray-400 hover:text-white transition-colors"
            >
              {isMuted || volume === 0 ? (
                <VolumeX className="w-4 h-4" />
              ) : (
                <Volume2 className="w-4 h-4" />
              )}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              className="w-20"
            />
          </div>

          {/* Fullscreen */}
          <button
            onClick={handleFullscreen}
            className="p-1.5 rounded text-gray-400 hover:text-white transition-colors"
          >
            <Maximize className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Play button overlay when paused */}
      {!isPlaying && (
        <button
          onClick={togglePlay}
          className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:bg-transparent transition-colors"
        >
          <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center group-hover:scale-110 transition-transform">
            <Play className="w-8 h-8 text-white ml-1" />
          </div>
        </button>
      )}
    </div>
  )
}

