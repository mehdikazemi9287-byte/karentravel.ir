import type {MetadataRoute} from 'next';

// Installable customer app (PWA). Opens on the mobile app shell; every screen reads real account data.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'کارن‌سیر — سفر و رفاه',
    short_name: 'کارن‌سیر',
    description: 'جستجو و رزرو سفر، سفرهای من، کیف پول و حساب کاربری کارن‌سیر.',
    id: '/app',
    start_url: '/app',
    scope: '/',
    display: 'standalone',
    orientation: 'portrait',
    dir: 'rtl',
    lang: 'fa',
    background_color: '#fdf5ea',
    theme_color: '#3a1b3d',
    categories: ['travel'],
    icons: [
      {src: '/app-icons/icon-192.png', sizes: '192x192', type: 'image/png'},
      {src: '/app-icons/icon-512.png', sizes: '512x512', type: 'image/png'},
      {src: '/app-icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable'},
    ],
    shortcuts: [
      {name: 'سفرهای من', url: '/app/trips'},
      {name: 'کیف پول', url: '/app/wallet'},
    ],
  };
}
