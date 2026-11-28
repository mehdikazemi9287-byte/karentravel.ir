import { Shell } from '../root-pages';
import { ServiceIntro } from '../../components/customer/CustomerHelp';
import { VisaGuide } from '../../components/catalog/CatalogViews';
import {seoFor} from '../../lib/seo-pages';
import {RelatedLinks} from '../../components/seo/RelatedLinks';
export const metadata = seoFor('/visa');
export default function Page(){return <Shell><ServiceIntro title="ویزا و مدارک سفر" description="کشور مقصد و تاریخ سفرت را بنویس؛ کارشناس مدارک لازم، هزینه و زمان تقریبی صدور ویزا را اعلام می‌کند."/><div className="container customer-page"><VisaGuide/></div><RelatedLinks group="visa"/></Shell>}
