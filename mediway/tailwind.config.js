/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // MediWay Design System — "Editorial Clinical Excellence"
        primary: {
          DEFAULT: '#004e9f',
          container: '#0066cc',
          light: '#3b82f6',
        },
        surface: {
          DEFAULT: '#f9f9fb',
          'container-lowest': '#ffffff',
          'container-low': '#f3f3f5',
          'container': '#ededef',
          'container-high': '#e8e8ea',
          'container-highest': '#e2e2e4',
        },
        on: {
          surface: '#1a1c1d',
          'surface-variant': '#414753',
          primary: '#ffffff',
          'secondary-fixed': '#1a1c2e',
        },
        secondary: {
          fixed: '#e8eaf6',
        },
        outline: {
          variant: '#c4c6d0',
        },
        error: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
        },
        // POI category colors
        poi: {
          clinic: '#dbeafe',
          lab: '#fef3c7',
          imaging: '#ede9fe',
          pharmacy: '#d1fae5',
          admin: '#e0e7ff',
          elevator: '#f3f4f6',
          checkup: '#ecfeff',
          consultation: '#fdf2f8',
        },
      },
      borderRadius: {
        xl: '1.5rem',
      },
      fontFamily: {
        sans: [
          'Pretendard',
          '-apple-system',
          'BlinkMacSystemFont',
          'system-ui',
          'Roboto',
          'sans-serif',
        ],
      },
      backdropBlur: {
        glass: '20px',
      },
      boxShadow: {
        ambient: '0 4px 60px rgba(0, 78, 159, 0.06)',
        'ambient-lg': '0 8px 60px rgba(0, 78, 159, 0.08)',
      },
      keyframes: {
        'dash-move': {
          to: { 'stroke-dashoffset': '-24' },
        },
        pulse: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.6', transform: 'scale(1.3)' },
        },
      },
      animation: {
        'dash-move': 'dash-move 0.8s linear infinite',
        'poi-pulse': 'pulse 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
