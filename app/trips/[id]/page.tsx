import { notFound } from 'next/navigation';
import { JourneyShell } from '../../../components/journey/JourneyShell';
import { ConnectedTripTimeline } from '../../../components/operational/ConnectedViews';
import { TripChanges } from '../../../components/operational/TripChangeViews';
export default async function TripDetailPage({params}:{params:Promise<{id:string}>}){const {id}=await params;if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id))notFound();return <JourneyShell><main className="journey-main"><TripChanges tripId={id}/><ConnectedTripTimeline tripId={id}/></main></JourneyShell>}
