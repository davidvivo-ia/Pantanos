/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        agua: {
          50:  '#eff8fb',
          100: '#d8eef5',
          200: '#b2dcea',
          300: '#84c4dc',
          400: '#52a7c8',
          500: '#358bb0',
          600: '#2b7295',
          700: '#265d79',
          800: '#234d63',
          900: '#1f3f53',
          950: '#102837',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
