import type { Metadata } from 'next';
import 'vazirmatn/Vazirmatn-Variable-font-face.css';
import './globals.css';
import { AuthProvider } from '../lib/api/auth-context';

export const metadata: Metadata = {
  title: { default: 'کارن تراول | بلیط هواپیما، قطار، هتل و تور', template: '%s | کارن تراول' },
  description: 'خرید بلیط هواپیما و قطار، رزرو هتل و تور داخلی و خارجی، با پشتیبانی کارشناسان کارن تراول.',
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fa" dir="rtl"><body><AuthProvider>{children}</AuthProvider></body></html>;
}
