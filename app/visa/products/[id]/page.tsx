import {JourneyShell} from '../../../../components/journey/JourneyShell';
import {VisaDetail} from '../../../../components/operational/TravelCommerceViews';
// Visa service (backoffice visa product) detail where a signed-in customer starts a human-reviewed
// application. /visa/[id] now renders the public visa guides, so products live under /visa/products.
export const metadata={title:'درخواست ویزا',robots:{index:false,follow:false}};
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;return <JourneyShell><main className="journey-main"><VisaDetail id={id}/></main></JourneyShell>}
