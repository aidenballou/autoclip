import { ReactNode, ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import clsx from 'clsx'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: ReactNode
  children?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles = 'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-clip-bg disabled:opacity-50 disabled:cursor-not-allowed'
  
  const variants = {
    primary: 'bg-clip-accent hover:bg-clip-accent-hover text-white focus:ring-clip-accent',
    secondary: 'bg-clip-elevated hover:bg-clip-border text-gray-200 border border-clip-border focus:ring-clip-border',
    ghost: 'hover:bg-clip-elevated text-gray-400 hover:text-white focus:ring-clip-border',
    danger: 'bg-clip-error/20 hover:bg-clip-error/30 text-clip-error focus:ring-clip-error',
  }
  
  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  }

  return (
    <button
      className={clsx(
        baseStyles,
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : icon ? (
        icon
      ) : null}
      {children}
    </button>
  )
}

