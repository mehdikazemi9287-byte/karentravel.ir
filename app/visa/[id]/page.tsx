import {JourneyShell} from '../../../components/journey/JourneyShell';
import {VisaArticle} from '../../../components/catalog/CatalogViews';
export async function generateMetadata({params}:{params:Promise<{id:string}>}){const {id}=await params;return {title:'راهنمای ویزا',alternates:{canonical:`/visa/${id}`}}}
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <JourneyShell><VisaArticle id={id}/></JourneyShell>}
