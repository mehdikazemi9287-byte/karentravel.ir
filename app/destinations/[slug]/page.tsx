import { JourneyShell } from '../../../components/journey/JourneyShell';
import { DestinationDetailView } from '../../../components/operational/EcosystemViews';
export default async function DestinationPage({params}:{params:Promise<{slug:string}>}){const {slug}=await params;return <JourneyShell><main className="journey-main"><DestinationDetailView slug={slug}/></main></JourneyShell>}
