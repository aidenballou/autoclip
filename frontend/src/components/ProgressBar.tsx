import clsx from 'clsx'

interface ProgressBarProps {
  progress: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  variant?: 'default' | 'success' | 'warning' | 'error'
  className?: string
}

export function ProgressBar({
  progress,
  size = 'md',
  showLabel = true,
  variant = 'default',
  className,
}: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress))
  
  const heights = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  }
  
  const variants = {
    default: 'bg-clip-accent',
    success: 'bg-clip-success',
    warning: 'bg-clip-warning',
    error: 'bg-clip-error',
  }

  return (
    <div className={clsx('w-full', className)}>
      <div className={clsx('w-full bg-clip-border rounded-full overflow-hidden', heights[size])}>
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-300 ease-out progress-bar',
            variants[variant]
          )}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
      {showLabel && (
        <p className="text-xs text-gray-500 mt-1 text-right">
          {clampedProgress.toFixed(0)}%
        </p>
      )}
    </div>
  )
}

