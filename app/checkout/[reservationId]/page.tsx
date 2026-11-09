import { JourneyShell } from '../../../components/journey/JourneyShell';
import { CheckoutView } from '../../../components/operational/EcosystemViews';
export const metadata={title:'تکمیل امن رزرو',robots:{index:false,follow:false}};
export default async function CheckoutPage({params}:{params:Promise<{reservationId:string}>}){const {reservationId}=await params;return <JourneyShell><main className="journey-main a11y-page"><CheckoutView reservationId={reservationId}/></main></JourneyShell>}
