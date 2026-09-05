import { JourneyShell } from '../../components/journey/JourneyShell';
import { ConnectedTrips } from '../../components/operational/ConnectedViews';
export default function TripsPage(){return <JourneyShell><main className="journey-main"><div className="journey-title"><div><span>مرکز سفرهای من</span><h1>سفرها، مدارک و کارهای باقی‌مانده</h1><p>این اطلاعات مستقیماً از حساب و سازمان احرازشده دریافت می‌شود.</p></div></div><ConnectedTrips/></main></JourneyShell>}
