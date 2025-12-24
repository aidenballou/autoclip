/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Custom dark theme inspired by modern video editors
        'clip': {
          bg: '#0a0a0f',
          surface: '#12121a',
          elevated: '#1a1a24',
          border: '#2a2a38',
          accent: '#6366f1',
          'accent-hover': '#818cf8',
          success: '#22c55e',
          warning: '#f59e0b',
          error: '#ef4444',
        }
      },
      fontFamily: {
        'sans': ['JetBrains Mono', 'SF Pro Display', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        'mono': ['JetBrains Mono', 'SF Mono', 'ui-monospace', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 },
        },
        fadeIn: {
          '0%': { opacity: 0 },
          '100%': { opacity: 1 },
        },
      },
    },
  },
  plugins: [],
}

