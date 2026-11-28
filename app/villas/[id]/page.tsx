import {JourneyShell} from '../../../components/journey/JourneyShell';
import {VacationRentalDetail} from '../../../components/operational/TravelCommerceViews';
export async function generateMetadata({params}:{params:Promise<{id:string}>}){const {id}=await params;return {title:'اجاره ویلا و اقامتگاه',alternates:{canonical:`/villas/${id}`}}}
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;return <JourneyShell><main className="journey-main"><VacationRentalDetail id={id}/></main></JourneyShell>}
