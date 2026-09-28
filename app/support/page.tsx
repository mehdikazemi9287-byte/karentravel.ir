import { JourneyShell } from '../../components/journey/JourneyShell';
import { SupportComposer } from '../../components/operational/CustomerAccount';
import { ServiceInquiry } from '../../components/operational/ServiceInquiry';
import {Suspense} from 'react';
import { SupportLanding } from '../../components/operational/ConnectedViews';

export default async function SupportPage({searchParams}:{searchParams:Promise<{booking?:string;inquiry?:string}>}){const {booking,inquiry}=await searchParams;if(inquiry&&['event_hall','restaurant','pool_sport','attraction'].includes(inquiry))return <JourneyShell><main className="journey-main leisure-product"><Suspense fallback={<p role="status">آماده‌سازی درخواست…</p>}><ServiceInquiry/></Suspense></main></JourneyShell>;if(booking&&/^[0-9a-f-]{36}$/i.test(booking))return <JourneyShell><main className="journey-main support-page"><SupportComposer reservationId={booking}/></main></JourneyShell>;return <JourneyShell><main className="journey-main support-page"><SupportLanding/></main></JourneyShell>}
