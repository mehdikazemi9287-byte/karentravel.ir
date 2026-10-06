import type {Metadata} from 'next';
import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourDetail} from '../../../components/operational/TravelCommerceViews';
import {TourReferenceDetail} from '../../../components/catalog/CatalogViews';
import {catalogSeo} from '../../../lib/catalog-seo';
// A UUID is a supplier's sellable tour product; anything else is the slug of a reference tour programme.
const SELLABLE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export async function generateMetadata({params}:{params:Promise<{id:string}>}): Promise<Metadata> {const {id}=await params;if(SELLABLE.test(id))return {};const seo=await catalogSeo(`/catalog/tours/${encodeURIComponent(decodeURIComponent(id))}`);return seo?{title:seo.title,description:seo.description,alternates:{canonical:`/tours/${id}`}}:{title:'برنامهٔ تور | کارن‌سیر',robots:{index:false}}}
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;return SELLABLE.test(id)?<JourneyShell><main className="journey-main"><TourDetail id={id}/></main></JourneyShell>:<JourneyShell><TourReferenceDetail id={decodeURIComponent(id)}/></JourneyShell>}
