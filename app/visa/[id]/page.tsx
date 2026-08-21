import {JourneyShell} from '../../../components/journey/JourneyShell';
import {VisaDetail} from '../../../components/operational/TravelCommerceViews';
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;return <JourneyShell><main className="journey-main"><VisaDetail id={id}/></main></JourneyShell>}
