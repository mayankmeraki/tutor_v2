import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0a0d0b',
          surface: '#111413',
          elevated: '#191c1a',
          hover: '#1f2220',
        },
        border: {
          DEFAULT: 'rgba(255,255,255,0.07)',
          active: 'rgba(255,255,255,0.14)',
        },
        text: {
          DEFAULT: '#ececec',
          muted: '#9a9a9a',
          dim: '#5a5e5c',
        },
        accent: {
          DEFAULT: '#34d399',
          bright: '#5eead4',
          dim: '#1a7a55',
        },
        good: {
          DEFAULT: '#4ade80',
          dim: '#162e1e',
        },
        warn: {
          DEFAULT: '#fbbf24',
          dim: '#4a3a0a',
        },
        bad: {
          DEFAULT: '#f87171',
          dim: '#4a1a1a',
        },
        orange: '#fb923c',
        chalk: {
          white: '#d4e8dc',
          blue: '#5eead4',
          green: '#7ed99a',
          yellow: '#e8d47a',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
        board: ['"Bright Chalk"', 'Caveat', 'cursive'],
        display: ['Lexend', 'Inter', 'sans-serif'],
        hand: ['Caveat', 'Pangolin', 'cursive'],
      },
      borderRadius: {
        DEFAULT: '8px',
        lg: '12px',
      },
      transitionTimingFunction: {
        bounce: 'cubic-bezier(.16,1,.3,1)',
      },
      keyframes: {
        scFadeIn: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'none' },
        },
        scStaggerIn: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'sc-fade-in': 'scFadeIn .4s cubic-bezier(.16,1,.3,1)',
        'sc-stagger-in': 'scStaggerIn .5s cubic-bezier(.16,1,.3,1) forwards',
      },
    },
  },
  plugins: [],
};

export default config;
