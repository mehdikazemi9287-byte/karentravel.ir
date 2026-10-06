import { Shell } from '../page';
import { ServiceIntro } from '../../components/customer/CustomerHelp';
import { VisaGuide } from '../../components/catalog/CatalogViews';
export default function Page(){return <Shell><ServiceIntro title="ویزا و مدارک سفر" description="شرایط ویزا به ملیت، مقصد و هدف سفر بستگی دارد. هیچ نتیجه یا زمان صدوری تضمین نمی‌شود."/><div className="container customer-page"><VisaGuide/></div></Shell>}
