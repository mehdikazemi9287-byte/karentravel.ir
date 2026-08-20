import Link from 'next/link';
import { JourneyShell, MockNotice } from '../../components/journey/JourneyShell';
import { ServicesExplorer } from '../../components/journey/ServicesExplorer';
import { mockServices, mockTrip } from '../../lib/domain/mock-data';
export default function ServicesPage(){return <JourneyShell><main className="journey-main services-main"><div className="journey-title"><div><span>محصولات قابل اقدام</span><h1>خدمات سفر شیراز</h1><p>خدمت را ببین، انتخاب کن یا برای اتصال معتبر آماده نگه دار؛ این صفحه مقصد الهام‌بخش نیست.</p></div><MockNotice/></div><section className="service-context"><div><span>Trip Context فعال</span><b>{mockTrip.origin} ← {mockTrip.destination}</b><small>{mockTrip.startDate} · ۲ مسافر</small></div><Link href={`/trips/${mockTrip.id}`}>بازگشت به سفر من</Link></section><ServicesExplorer services={mockServices}/></main></JourneyShell>}
