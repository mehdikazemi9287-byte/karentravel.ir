import {JourneyShell} from '../../components/journey/JourneyShell';
import {StayLanding} from '../../components/marketplace/StayLanding';
export const metadata={title:'هتل و اقامتگاه | کارن‌سیر',description:'جست‌وجوی هتل و کشف انواع اقامتگاه با بررسی تاریخ، ظرفیت و شرایط اقامت.',alternates:{canonical:'/hotels'}};
export default function Page(){return <JourneyShell><StayLanding/></JourneyShell>}
