import { JourneyShell } from '../../../components/journey/JourneyShell';
import { DestinationDetailView } from '../../../components/operational/EcosystemViews';
import type { Metadata } from 'next';
export async function generateMetadata({params}:{params:Promise<{slug:string}>}):Promise<Metadata>{const {slug}=await params;const label=decodeURIComponent(slug).replace(/-/g,' ');return {title:`سفر به ${label}`,description:`راهنمای مقصد، موقعیت و خدمات سفر ${label} در کارن‌سیر`,alternates:{canonical:`/destinations/${slug}`},openGraph:{title:`سفر به ${label} | کارن‌سیر`,description:'اقامت، حمل‌ونقل، تجربه و خدمات تازه مقصد',url:`/destinations/${slug}`,type:'website'}}}
export default async function DestinationPage({params}:{params:Promise<{slug:string}>}){const {slug}=await params;return <JourneyShell><main className="journey-main"><DestinationDetailView slug={slug}/></main></JourneyShell>}
