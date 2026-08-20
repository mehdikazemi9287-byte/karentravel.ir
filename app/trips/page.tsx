import Link from 'next/link';
import { JourneyShell, MockNotice } from '../../components/journey/JourneyShell';
import { TripSummaryCard } from '../../components/journey/TripCards';
import { mockNotifications, mockTrip } from '../../lib/domain/mock-data';
export default function TripsPage(){return <JourneyShell><main className="journey-main"><div className="journey-title"><div><span>مرکز سفرهای من</span><h1>سفرها، مدارک و کارهای باقی‌مانده</h1><p>اطلاعات مقصد و مسافران در هر سفر نگه‌داری می‌شود تا دوباره از تو پرسیده نشود.</p></div><MockNotice/></div><section className="trips-overview"><TripSummaryCard trip={mockTrip}/><aside className="notification-panel"><header><h2>اعلان‌های مفید</h2><span>نسخه نمایشی</span></header>{mockNotifications.slice(0,2).map(n=><Link href={n.deepLink} key={n.id}><b>{n.title}</b><small>{n.body}</small><i>←</i></Link>)}</aside></section></main></JourneyShell>}
