import {JourneyShell} from '../../../components/journey/JourneyShell';
import {PlaceDetail} from '../../../components/catalog/PlaceDetail';
export const metadata = {title: 'رزرو | کارن‌سیر'};
export default async function Page({params}: {params: Promise<{id: string}>}) {const {id} = await params; return <JourneyShell><main className="journey-main"><PlaceDetail id={decodeURIComponent(id)}/></main></JourneyShell>;}
