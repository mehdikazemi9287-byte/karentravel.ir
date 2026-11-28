import type {Metadata} from 'next';
import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourDetail} from '../../../components/operational/TravelCommerceViews';
import {TourReferenceDetail} from '../../../components/catalog/CatalogViews';
import {catalogSeo} from '../../../lib/catalog-seo';
import {TourReviews} from '../../../components/catalog/TourReviews';
import {JsonLd} from '../../../components/seo/JsonLd';
import {breadcrumbLd, touristTripLd} from '../../../lib/seo';
// A UUID is a supplier's sellable tour product; anything else is the slug of a reference tour programme.
const SELLABLE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export async function generateMetadata({params}:{params:Promise<{id:string}>}): Promise<Metadata> {const {id}=await params;if(SELLABLE.test(id))return {title:'جزئیات و رزرو تور',description:'برنامهٔ سفر، تاریخ‌های حرکت، ظرفیت، هتل و حمل‌ونقل این تور در کارن تراول؛ قیمت نهایی و شرایط کنسلی پیش از پرداخت نمایش داده می‌شود.',alternates:{canonical:`/tours/${id}`}};const seo=await catalogSeo(`/catalog/tours/${encodeURIComponent(decodeURIComponent(id))}`);return seo?{title:seo.title,description:seo.description,alternates:{canonical:`/tours/${id}`}}:{title:'برنامهٔ تور',robots:{index:false}}}
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;
  // JSON-LD only from server-side catalogue data (same cached lookup as the metadata); nothing is invented for sellable tours.
  const seo=SELLABLE.test(id)?null:await catalogSeo(`/catalog/tours/${encodeURIComponent(decodeURIComponent(id))}`);
  const ld=<JsonLd data={[breadcrumbLd([['کارن تراول','/'],['تورها','/tours'],[seo?.title??'جزئیات تور',`/tours/${id}`]]),...(seo?[touristTripLd({name:seo.title,description:seo.description,path:`/tours/${id}`})]:[])]}/>;
  return SELLABLE.test(id)?<JourneyShell>{ld}<main className="journey-main"><TourDetail id={id}/><TourReviews tourId={id}/></main></JourneyShell>:<JourneyShell>{ld}<TourReferenceDetail id={decodeURIComponent(id)}/></JourneyShell>}
