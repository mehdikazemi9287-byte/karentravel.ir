import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerSaved} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'ذخیره‌شده‌ها و پیشنهادها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="ذخیره‌شده‌ها و پیشنهادها" intro="سفرهای ذخیره‌شده، برنامه‌ها، پیشنهادهای قیمت و نظرها."><CustomerSaved/></PanelShell>;}
