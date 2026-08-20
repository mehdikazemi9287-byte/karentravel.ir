import type { Config } from 'tailwindcss';
const config: Config = { content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'], theme: { extend: { colors: { ink: '#08253D', ocean: '#0E7490', sun: '#F4B942', mist: '#F7FAFC' }, boxShadow: { soft: '0 18px 45px rgba(8,37,61,.10)' } } }, plugins: [] };
export default config;
