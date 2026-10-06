import {JourneyShell} from '../../../components/journey/JourneyShell';
import {VisaArticle} from '../../../components/catalog/CatalogViews';
export const metadata={title:'راهنمای ویزا | کارن‌سیر'};
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <JourneyShell><VisaArticle id={id}/></JourneyShell>}
