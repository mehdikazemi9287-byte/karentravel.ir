import {JourneyShell} from '../../../../components/journey/JourneyShell';
import {TourRouteView} from '../../../../components/tours/TourRouteView';
export const metadata = {title: 'شبیه‌ساز مسیر تور', robots: {index: false}};
export default async function Page({params}: {params: Promise<{id: string}>}) {const {id} = await params; return <JourneyShell><main className="journey-main"><TourRouteView id={id}/></main></JourneyShell>;}
