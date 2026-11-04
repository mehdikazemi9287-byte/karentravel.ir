import {CarRentalSearch} from '../../components/marketplace/CarRentalSearch';
import {Shell} from '../page';
import {ContactOptions} from '../../components/customer/CustomerHelp';
import {Suspense} from 'react';
import {VenueDirectory} from '../../components/catalog/CatalogViews';
export default function Page(){return <Shell><section className="container customer-page"><h1>اجارهٔ خودرو</h1><p>شهر و تاریخ تحویل را انتخاب کن تا خودروهای قابل اجاره را ببینی.</p><CarRentalSearch/><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><VenueDirectory kinds={['car_rental']} title="مراکز اجارهٔ خودرو ثبت‌شده"/></Suspense><ContactOptions/></section></Shell>}
