import {PanelShell} from '../../../components/panel/PanelKit';
import {SettlementImport} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'ورود فایل تسویهٔ درگاه', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="ورود فایل تسویهٔ درگاه" intro="فایل تسویهٔ درگاه را بارگذاری کنید تا با پرداخت‌های ثبت‌شده تطبیق داده شود."><SettlementImport/></PanelShell>;}
