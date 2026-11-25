import {PanelShell} from '../../../../components/panel/PanelKit';
import {MahanConsole} from '../../../../components/panel/MahanConsolePanel';
export const metadata = {title: 'آزمون اتصال ماهان', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="آزمون اتصال ماهان" intro="جست‌وجو، استعلام قیمت قطعی و رزرو موقت پرواز ماهان برای کارشناس عملیات. صدور بلیت غیرفعال است."><MahanConsole/></PanelShell>;}
