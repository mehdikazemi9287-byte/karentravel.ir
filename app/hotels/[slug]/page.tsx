import {JourneyShell} from '../../../components/journey/JourneyShell';
import {HotelDetail} from '../../../components/catalog/CatalogViews';
export const metadata={title:'مشخصات هتل | کارن‌سیر',description:'نام، موقعیت، درجه و امکانات ثبت‌شدهٔ اقامتگاه. قیمت پس از انتخاب تاریخ و استعلام اعلام می‌شود.'};
export default async function Page({params}:{params:Promise<{slug:string}>}){const {slug}=await params;return <JourneyShell><HotelDetail slug={slug}/></JourneyShell>}
