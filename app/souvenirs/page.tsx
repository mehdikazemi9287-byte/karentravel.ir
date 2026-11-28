import {JourneyShell} from '../../components/journey/JourneyShell';
import {GiftasanSouvenir} from '../../components/catalog/GiftasanSouvenir';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/souvenirs');
export default function Page() {return <JourneyShell><main className="journey-main"><h1>سوغات شهرها</h1><p>شهر را انتخاب کن و بگو چه سوغاتی می‌خواهی.</p><GiftasanSouvenir/></main></JourneyShell>;}
