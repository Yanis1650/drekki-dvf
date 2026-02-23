/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sage: {
          50: '#f2f7f8',
          100: '#e1eaec',
          200: '#c5d8dc',
          300: '#9dbcc3',
          400: '#709ba6',
          500: '#527f8c',
          600: '#3f6775',
          700: '#39616d', // Reference Sage
          800: '#314b54',
          900: '#2b3f46',
          950: '#1a292f',
        },
        terracotta: {
          50: '#fef5f2',
          100: '#ffe8df',
          200: '#fed2bf',
          300: '#fdb393',
          400: '#fb885f',
          500: '#f56236',
          600: '#c63806', // Reference Terracotta
          700: '#a32b0a',
          800: '#86250f',
          900: '#6f2111',
          950: '#3c0e06',
        },
        cream: {
          50: '#fdfcfa', // Light variant
          100: '#f9f7f2', // Light variant
          200: '#f2efe6',
          300: '#e1dbcb', // Reference Cream
          400: '#cbbfa6',
          500: '#b6a284',
          600: '#a38b6d',
          700: '#87715a',
          800: '#6f5d4d',
          900: '#5b4d40',
          950: '#302821',
        },
        rouge: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#c0393e', // Reference Rouge
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
          950: '#450a0a',
        },
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', 'serif'],
        sans: ['"DM Sans"', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 4px 6px -1px rgba(57, 97, 109, 0.1), 0 2px 4px -1px rgba(57, 97, 109, 0.06)', // Soft sage shadow
        'glow': '0 0 15px rgba(57, 97, 109, 0.5)', // Sage glow
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'float': 'float 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
      },
    },
  },
  plugins: [],
}
