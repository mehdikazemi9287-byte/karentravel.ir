import { JourneyShell } from '../../../components/journey/JourneyShell';
import { CheckoutView } from '../../../components/operational/EcosystemViews';
import '../../../components/operational/stitch-account-2026-11.css';
export const metadata={title:'تکمیل امن رزرو',robots:{index:false,follow:false}};
/* Stitch _39 (desktop) / _31 (mobile): styled from stitch-account-2026-11.css only; CheckoutJourney logic and markup are unchanged. */
export default async function CheckoutPage({params}:{params:Promise<{reservationId:string}>}){const {reservationId}=await params;return <JourneyShell><main className="journey-main a11y-page"><CheckoutView reservationId={reservationId}/></main></JourneyShell>}
