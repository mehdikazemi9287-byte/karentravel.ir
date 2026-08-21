import {JourneyShell} from '../../components/journey/JourneyShell';
import {CruiseList} from '../../components/operational/TravelCommerceViews';
export const metadata={title:'سفر دریایی و کروز | کارن‌سیر',description:'کاتالوگ سفرهای دریایی با وضعیت صادقانه Provider'};
export default function Page(){return <JourneyShell><main className="journey-main"><CruiseList/></main></JourneyShell>}
