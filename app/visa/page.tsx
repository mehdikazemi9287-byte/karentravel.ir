import {JourneyShell} from '../../components/journey/JourneyShell';
import {VisaList} from '../../components/operational/TravelCommerceViews';
export const metadata={title:'خدمات ویزا | کارن‌سیر',description:'بررسی منبع‌دار و مدیریت پرونده ویزا بدون تضمین صدور'};
export default function Page(){return <JourneyShell><main className="journey-main"><VisaList/></main></JourneyShell>}
