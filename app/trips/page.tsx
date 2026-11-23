import { JourneyShell } from '../../components/journey/JourneyShell';
import { ConnectedTrips } from '../../components/operational/ConnectedViews';
import '../../components/operational/stitch-account-2026-11.css';
/* Stitch screens _32 (light) / _20 (dark): «سفرهای من». Data, auth and API calls live in ConnectedTrips, unchanged. */
export default function TripsPage(){return <JourneyShell><main className="journey-main a11y-page sa-page"><header className="sa-head"><span className="sa-head-ic" aria-hidden="true">🧳</span><div><h1>سفرهای من</h1><p>مدیریت و پیگیری سفرها، رزروها و مدارک — مستقیماً از حساب احرازشدهٔ شما.</p></div></header><ConnectedTrips/></main></JourneyShell>}
