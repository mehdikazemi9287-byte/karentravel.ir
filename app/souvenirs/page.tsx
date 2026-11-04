import {JourneyShell} from '../../components/journey/JourneyShell';
import {GiftasanSouvenir} from '../../components/catalog/GiftasanSouvenir';
export const metadata = {title: 'سوغات شهرها | کارن‌سیر', description: 'سوغات ۳۳ شهر ایران را بدون رفتن به آن شهر سفارش بده؛ تهیه، بسته‌بندی و ارسال تا درِ خانه.'};
export default function Page() {return <JourneyShell><main className="journey-main"><h1>سوغات شهرها</h1><p>شهر را انتخاب کن و بگو چه سوغاتی می‌خواهی.</p><GiftasanSouvenir/></main></JourneyShell>;}
