/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        risk: {
          critical: '#DC2626',
          high: '#EA580C',
          moderate: '#D97706',
          low: '#16A34A',
        },
      },
    },
  },
  plugins: [],
}
