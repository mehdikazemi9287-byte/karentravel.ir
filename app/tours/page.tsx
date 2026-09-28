import { Shell } from '../page';
import { TourList } from '../../components/operational/TravelCommerceViews';
import { ServiceIntro } from '../../components/customer/CustomerHelp';
export default function Page(){return <Shell><ServiceIntro title="تور و سفر گروهی" description="برای استعلام تور، مقصد، تاریخ و خدمات مورد نظرتان را آماده کنید." vertical="tour"/><TourList/></Shell>}
