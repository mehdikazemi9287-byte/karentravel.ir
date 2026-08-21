import { JourneyShell } from '../../components/journey/JourneyShell';
import { DestinationListView } from '../../components/operational/EcosystemViews';
export const metadata={title:'مقصدهای سفر',description:'کاتالوگ مقصدها و خدمات تازه سفر در کارن‌سیر',alternates:{canonical:'/destinations'},openGraph:{title:'مقصدهای سفر | کارن‌سیر',description:'کشف مقصد و مشاهده خدمات تازه و قابل رزرو',url:'/destinations',type:'website'}};
export default function DestinationsPage(){return <JourneyShell><main className="journey-main"><DestinationListView/></main></JourneyShell>}
