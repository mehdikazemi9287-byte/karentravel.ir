import { JourneyShell } from '../../../components/journey/JourneyShell';
import { CheckoutView } from '../../../components/operational/EcosystemViews';
export const metadata={title:'تکمیل امن رزرو | کارن‌سیر',robots:{index:false,follow:false}};
export default async function CheckoutPage({params}:{params:Promise<{reservationId:string}>}){const {reservationId}=await params;return <JourneyShell><main className="journey-main"><CheckoutView reservationId={reservationId}/></main></JourneyShell>}
