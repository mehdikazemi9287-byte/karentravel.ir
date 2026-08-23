import { JourneyShell } from '../../components/journey/JourneyShell';
import { SupportComposer } from '../../components/operational/CustomerAccount';
import { SupportLanding } from '../../components/operational/ConnectedViews';

export default async function SupportPage({searchParams}:{searchParams:Promise<{booking?:string}>}){const {booking}=await searchParams;if(booking&&/^[0-9a-f-]{36}$/i.test(booking))return <JourneyShell><main className="journey-main support-page"><SupportComposer reservationId={booking}/></main></JourneyShell>;return <JourneyShell><main className="journey-main support-page"><SupportLanding/></main></JourneyShell>}
