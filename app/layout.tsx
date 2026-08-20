import type { Metadata } from 'next';
import 'vazirmatn/Vazirmatn-Variable-font-face.css';
import './globals.css';
import { AuthProvider } from '../lib/api/auth-context';

export const metadata: Metadata = {
  title: { default: 'کارن‌سیر | اکوسیستم هوشمند سفر و رفاه', template: '%s | کارن‌سیر' },
  description: 'جست‌وجو، مقایسه و برنامه‌ریزی سفر، تجربه‌های مقصد و خدمات رفاهی سازمانی در اکوسیستم کارن‌سیر.',
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fa" dir="rtl"><body><AuthProvider>{children}</AuthProvider></body></html>;
}
