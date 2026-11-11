import type { Metadata } from 'next';
import 'vazirmatn/Vazirmatn-Variable-font-face.css';
import './globals.css';
import { connection } from 'next/server';
import { AuthProvider } from '../lib/api/auth-context';

export const metadata: Metadata = {
  title: { default: 'کارن تراول | بلیط هواپیما، قطار، هتل و تور', template: '%s | کارن تراول' },
  description: 'خرید بلیط هواپیما و قطار، رزرو هتل و تور داخلی و خارجی، با پشتیبانی کارشناسان کارن تراول.',
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
};
// Every page is rendered per request so Next.js can put the per-request CSP nonce (proxy.ts) on its scripts.
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  await connection();
  return <html lang="fa" dir="rtl"><body><AuthProvider>{children}</AuthProvider></body></html>;
}
