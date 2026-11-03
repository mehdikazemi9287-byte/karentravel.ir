import {PanelShell} from '../../../components/panel/PanelKit';
import {Ledger} from '../../../components/panel/LedgerPanel';
export const metadata = {title: 'دفتر کل و بستن دوره | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="دفتر کل و بستن دوره" intro="سند دوطرفه‌ی تراز از ردیف‌های صندوق و سند دستی، تراز آزمایشی، بستن ماه و خروجی اسناد برای فرانگر."><Ledger/></PanelShell>;}
