/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: '#1a1b2e', light: '#252640', lighter: '#2f3055' },
        accent: {
          blue: '#4f8fff',
          green: '#34d399',
          amber: '#fbbf24',
          red: '#ef4444',
          purple: '#a78bfa',
        },
      },
    },
  },
  plugins: [],
}
