import type { Metadata } from 'next';
import 'vazirmatn/Vazirmatn-Variable-font-face.css';
import './globals.css';
import { connection } from 'next/server';
import { AuthProvider } from '../lib/api/auth-context';
import { organizationLd, siteUrl, websiteLd } from '../lib/seo';
import { supportPhone } from '../lib/site-contact';
import { JsonLd } from '../components/seo/JsonLd';

// Search Console code from the owner. NEXT_PUBLIC_* is inlined at build time (Docker build arg); GOOGLE_SITE_VERIFICATION
// is read at runtime from the web container's env (this layout renders per request), so no rebuild is needed. Empty → no tag.
const googleVerification = (process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION || process.env.GOOGLE_SITE_VERIFICATION || '').trim();

// No alternates.canonical here: every page sets its own (lib/seo-pages.ts), so a page never inherits the homepage canonical.
export const metadata: Metadata = {
  title: { default: 'کارن تراول | بلیط هواپیما، قطار، هتل و تور', template: '%s | کارن تراول' },
  description: 'خرید بلیط هواپیما و قطار، رزرو هتل و تور داخلی و خارجی، با پشتیبانی کارشناسان کارن تراول.',
  metadataBase: new URL(siteUrl()),
  applicationName: 'کارن تراول',
  openGraph: { siteName: 'کارن تراول', locale: 'fa_IR', type: 'website' },
  ...(googleVerification ? { verification: { google: googleVerification } } : {}),
};
// Every page is rendered per request so Next.js can put the per-request CSP nonce (proxy.ts) on its scripts.
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  await connection();
  return <html lang="fa" dir="rtl"><body><JsonLd data={[organizationLd(supportPhone.href.replace(/^tel:/, '')), websiteLd()]}/><AuthProvider>{children}</AuthProvider></body></html>;
}
