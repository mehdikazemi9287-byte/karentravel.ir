import {JourneyShell} from '../../../components/journey/JourneyShell';
import {PlaceDetail} from '../../../components/catalog/PlaceDetail';
export async function generateMetadata({params}:{params:Promise<{id:string}>}){const {id}=await params;return {title:'رزرو',alternates:{canonical:`/places/${id}`}}}
export default async function Page({params}: {params: Promise<{id: string}>}) {const {id} = await params; return <JourneyShell><main className="journey-main"><PlaceDetail id={decodeURIComponent(id)}/></main></JourneyShell>;}
