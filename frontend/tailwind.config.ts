import defaultTheme from 'tailwindcss/defaultTheme';
import TailwindAnimate from 'tailwindcss-animate';
import TailwindLineClamp from '@tailwindcss/line-clamp';
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      fontFamily: {
        mono: ['var(--font-overpass-mono)', ...defaultTheme.fontFamily.mono],
        sans: ['var(--font-figtree)', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        black: '#000000',
        'black-300': '#666666',
        'black-400': '#333333',
        blue: '#3C70FF',
        'blue-600': '#4879FF',
        green: '#02B07C',
        orange: '#FD8E28',
        violet: '#AD6CFF',
        'gray-300': '#999999',
        red: '#F43F4C',
        'overlapping-eez': '#d60909'
      },
      maxWidth: {
        screen: '100vw',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'collapsible-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-collapsible-content-height)' },
        },
        'collapsible-up': {
          from: { height: 'var(--radix-collapsible-content-height)' },
          to: { height: '0' },
        },
        'collapsible-left': {
          from: { width: 'var(--radix-collapsible-content-width)' },
          to: { width: '0' },
        },
        'collapsible-right': {
          from: { width: '0' },
          to: { width: 'var(--radix-collapsible-content-width)' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'collapsible-down': 'collapsible-down 0.2s ease-out',
        'collapsible-up': 'collapsible-up 0.2s ease-out',
        'collapsible-left': 'collapsible-left 0.2s ease-out',
        'collapsible-right': 'collapsible-right 0.2s ease-out',
      },
    },
  },
  plugins: [TailwindAnimate, TailwindLineClamp],
};

export default config;
