import type {Metadata, Viewport} from 'next';
import {AppShell} from '../../components/customer-app/AppShell';

export const metadata: Metadata = {
  title: {default: 'اپلیکیشن کارن تراول', template: '%s | اپ کارن تراول'},
  robots: {index: false},
  appleWebApp: {capable: true, title: 'کارن تراول', statusBarStyle: 'black-translucent'},
  icons: {apple: '/app-icons/apple-touch-icon.png'},
};
export const viewport: Viewport = {themeColor: '#3a1b3d', width: 'device-width', initialScale: 1, viewportFit: 'cover'};

export default function Layout({children}: {children: React.ReactNode}) {return <AppShell>{children}</AppShell>;}
