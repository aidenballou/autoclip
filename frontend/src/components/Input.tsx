import { InputHTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className, ...props }, ref) => {
    return (
      <div className="space-y-1.5">
        {label && (
          <label className="block text-sm font-medium text-gray-300">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={clsx(
            'w-full px-4 py-2.5 bg-clip-elevated border rounded-lg text-white placeholder-gray-500',
            'focus:outline-none focus:ring-2 focus:ring-clip-accent focus:border-transparent',
            'transition-all',
            error ? 'border-clip-error' : 'border-clip-border',
            className
          )}
          {...props}
        />
        {error && (
          <p className="text-xs text-clip-error">{error}</p>
        )}
        {hint && !error && (
          <p className="text-xs text-gray-500">{hint}</p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'

