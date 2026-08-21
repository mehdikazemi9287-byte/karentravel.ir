import {JourneyShell} from '../../../../components/journey/JourneyShell';
import {VisaCaseView} from '../../../../components/operational/VisaCaseView';
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;return <JourneyShell><main className="journey-main"><VisaCaseView id={id}/></main></JourneyShell>}
