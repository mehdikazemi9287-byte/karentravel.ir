import {JourneyShell} from '../../../../components/journey/JourneyShell';
import {TourReferenceDetail} from '../../../../components/catalog/CatalogViews';
export const metadata={title:'برنامهٔ تور | کارن‌سیر'};
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <JourneyShell><TourReferenceDetail id={id}/></JourneyShell>}
