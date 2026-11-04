import {Shell} from '../page';
import {ContactOptions} from '../../components/customer/CustomerHelp';
import {Suspense} from 'react';
import {VenueDirectory} from '../../components/catalog/CatalogViews';
export default function Page(){return <Shell><section className="container customer-page"><h1>صنایع‌دستی با تحویل حضوری</h1><p>صنایع‌دستی اصیل هر شهر را پیدا کن و در مقصد تحویل بگیر.</p><form action="/search/results" className="panel"><input type="hidden" name="vertical" value="handicraft"/><label style={{display:'block'}}>شهر تحویل<input name="destination" required/></label><button className="button primary">جست‌وجوی صنایع‌دستی</button></form><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><VenueDirectory kinds={['handicraft']} title="فروشگاه‌ها و کارگاه‌های صنایع‌دستی"/></Suspense><ContactOptions/></section></Shell>}
