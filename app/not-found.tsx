import Link from 'next/link';
import { Shell } from './page';

// Before this file existed, any unknown URL fell through to Next.js's built-in
// default 404 - a plain black screen with English-only text ("This page could
// not be found"), no site header/footer/branding, and no way back into the
// site. This reuses the same Shell (Header/MobileNav/Footer) every other page
// already uses, with the same .page-hero styling Hotels/Compare/etc. use for
// their headings - no new design.
export default function NotFound() {
  return <Shell>
    <div className="page-hero">
      <span className="eyebrow">۴۰۴</span>
      <h1>این صفحه پیدا نشد.</h1>
      <p>ممکن است آدرس اشتباه باشد یا صفحه جابه‌جا شده باشد.</p>
    </div>
    <div className="container" style={{ paddingBottom: 70 }}>
      <Link href="/" className="button primary">بازگشت به صفحه اصلی</Link>
    </div>
  </Shell>;
}
