import { Shell } from '../page';
import { ServiceIntro } from '../../components/customer/CustomerHelp';
import { VisaGuide } from '../../components/catalog/CatalogViews';
export default function Page(){return <Shell><ServiceIntro title="ویزا و مدارک سفر" description="کشور مقصد و تاریخ سفرت را بنویس؛ کارشناس مدارک لازم، هزینه و زمان تقریبی صدور ویزا را اعلام می‌کند."/><div className="container customer-page"><VisaGuide/></div></Shell>}
