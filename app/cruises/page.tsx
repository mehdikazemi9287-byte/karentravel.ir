import { Shell } from '../page';
import { ServiceIntro } from '../../components/customer/CustomerHelp';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/cruises');
export default function Page(){return <Shell><ServiceIntro title="سفر دریایی" description="مسیر و تاریخ سفر دریایی موردنظرت را بنویس تا کارشناس گزینه‌ها و قیمت را اعلام کند."/></Shell>}
