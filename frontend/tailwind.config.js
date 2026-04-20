/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        qubic: {
          bg: '#0A0F1E',
          card: '#0C1628',
          border: '#1a2540',
          teal: '#23FFFF',
          cyan: '#00CCCC',
        },
      },
      backdropBlur: {
        'glass': '20px',
      },
    },
  },
  plugins: [],
}
