import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Scissors, FolderOpen, Settings } from 'lucide-react'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-clip-bg">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-clip-surface/80 backdrop-blur-md border-b border-clip-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-clip-accent to-purple-600 flex items-center justify-center group-hover:scale-105 transition-transform">
                <Scissors className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-white tracking-tight">AutoClip</h1>
                <p className="text-xs text-gray-500 -mt-0.5">Video Clip Extractor</p>
              </div>
            </Link>

            {/* Navigation */}
            <nav className="flex items-center gap-1">
              <NavLink 
                to="/projects" 
                active={location.pathname.startsWith('/projects')}
              >
                <FolderOpen className="w-4 h-4" />
                <span>Projects</span>
              </NavLink>
            </nav>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="pt-16 min-h-screen">
        {children}
      </main>
    </div>
  )
}

interface NavLinkProps {
  to: string
  active: boolean
  children: ReactNode
}

function NavLink({ to, active, children }: NavLinkProps) {
  return (
    <Link
      to={to}
      className={`
        flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
        ${active 
          ? 'bg-clip-accent/20 text-clip-accent' 
          : 'text-gray-400 hover:text-white hover:bg-clip-elevated'
        }
      `}
    >
      {children}
    </Link>
  )
}

