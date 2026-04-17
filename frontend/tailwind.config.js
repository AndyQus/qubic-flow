/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        qubic: {
          bg: '#0d1117',
          card: '#161b22',
          border: '#30363d',
          teal: '#2dd4bf',
          cyan: '#06b6d4',
        },
      },
      backdropBlur: {
        'glass': '20px',
      },
    },
  },
  plugins: [],
}
