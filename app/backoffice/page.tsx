import Link from 'next/link';
import { JourneyShell } from '../../components/journey/JourneyShell';
import { ConnectedRolePanel } from '../../components/operational/ConnectedViews';
export default function BackOfficePage(){return <JourneyShell><main className="journey-main"><Link className="button primary" href="/backoffice/trips">مرکز تغییرات سفر</Link><Link className="button secondary" href="/backoffice/records">رکوردهای عملیاتی</Link><Link className="button secondary" href="/backoffice/booking-requests">درخواست‌های تغییر و استرداد</Link><ConnectedRolePanel kind="backoffice"/></main></JourneyShell>}
