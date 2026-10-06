import {JourneyShell} from '../../../components/journey/JourneyShell';
import {HotelDetail} from '../../../components/catalog/CatalogViews';
import type {Metadata} from 'next';
import {catalogSeo} from '../../../lib/catalog-seo';
export async function generateMetadata({params}:{params:Promise<{slug:string}>}): Promise<Metadata> {const {slug}=await params;const seo=await catalogSeo(`/catalog/hotels/${encodeURIComponent(slug)}`);return seo?{title:seo.title,description:seo.description||'مشخصات اقامتگاه. قیمت پس از استعلام اعلام می‌شود.',alternates:{canonical:`/hotels/${slug}`}}:{title:'مشخصات هتل | کارن‌سیر',description:'نام، موقعیت، درجه و امکانات ثبت‌شدهٔ اقامتگاه. قیمت پس از انتخاب تاریخ و استعلام اعلام می‌شود.'}}
export default async function Page({params}:{params:Promise<{slug:string}>}){const {slug}=await params;return <JourneyShell><HotelDetail slug={slug}/></JourneyShell>}
