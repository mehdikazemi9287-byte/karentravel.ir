import { notFound } from 'next/navigation';
import { JourneyShell } from '../../../components/journey/JourneyShell';
import { ConnectedManageBooking } from '../../../components/operational/ConnectedViews';
export default async function ManageBookingPage({params}:{params:Promise<{bookingId:string}>}){const {bookingId}=await params;if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(bookingId))notFound();return <JourneyShell><main className="journey-main manage-booking-page"><ConnectedManageBooking reservationId={bookingId}/></main></JourneyShell>}
