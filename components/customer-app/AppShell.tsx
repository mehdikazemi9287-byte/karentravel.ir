'use client';
/* Mobile app shell of the customer PWA: top bar + fixed bottom navigation (خانه، جستجو، سفرهای من، کیف پول، حساب من). */
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {useEffect, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import './customer-app.css';

const TABS: {href: string; label: string; icon: ReactNode}[] = [
  {href: '/app', label: 'خانه', icon: <path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>},
  {href: '/search', label: 'جستجو', icon: <><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></>},
  {href: '/app/trips', label: 'سفرهای من', icon: <><path d="M3 13h18"/><path d="M5 13 9 5h6l4 8"/><path d="M7 13v6m10-6v6"/></>},
  {href: '/app/wallet', label: 'کیف پول', icon: <><rect x="3" y="6" width="18" height="13" rx="2.5"/><path d="M16 12.5h2"/><path d="M3 9.5h18"/></>},
  {href: '/app/account', label: 'حساب من', icon: <><circle cx="12" cy="8.5" r="3.6"/><path d="M4.5 20c1.2-3.6 4-5.4 7.5-5.4s6.3 1.8 7.5 5.4"/></>},
];

export function AppShell({children}: {children: ReactNode}) {
  const path = usePathname();
  const {session} = useAuth();
  useEffect(() => {
    // Offline fallback for the installed app; scoped to /app so the rest of the site is unaffected.
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
      navigator.serviceWorker.register('/sw.js', {scope: '/app'}).catch(() => {});
    }
  }, []);
  const active = (href: string) => (href === '/app' ? path === '/app' : path?.startsWith(href));
  return <div className="ca">
    <header className="ca-top">
      <Link href="/app" className="ca-brand" aria-label="کارن تراول — خانه">کارن تراول</Link>
      {session?.user ? <Link href="/account/notifications" className="ca-top-link">اعلان‌ها</Link> : <Link href="/login?redirect=/app" className="ca-top-link strong">ورود</Link>}
    </header>
    <main className="ca-main">{children}</main>
    <nav className="ca-tabs" aria-label="منوی اصلی اپ">
      {TABS.map(t => <Link key={t.href} href={t.href} aria-current={active(t.href) ? 'page' : undefined}>
        <svg viewBox="0 0 24 24" aria-hidden="true">{t.icon}</svg><span>{t.label}</span></Link>)}
    </nav>
  </div>;
}
