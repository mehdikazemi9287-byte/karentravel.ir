import { JourneyShell } from '../../components/journey/JourneyShell';
import { TourList } from '../../components/operational/TravelCommerceViews';
export const metadata={title:'تورهای سفر',description:'جست‌وجو و مقایسه تورها با قیمت و موجودی timestampدار',alternates:{canonical:'/tours'},openGraph:{title:'تورهای سفر | کارن‌سیر',description:'تور را کشف، مقایسه و با بررسی زنده انتخاب کنید',url:'/tours',type:'website'}};
export default function ToursPage(){return <JourneyShell><main className="journey-main"><TourList/></main></JourneyShell>}
