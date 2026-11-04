import {PanelShell} from '../../../components/panel/PanelKit';
import {CharterQuotas} from '../../../components/panel/CharterQuotaPanel';
export const metadata = {title: 'سهمیه‌ی صندلی همکاران', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="سهمیه‌ی صندلی همکاران" intro="کنار گذاشتن صندلی پروازهای چارتری برای آژانس‌های همکار، با برگشت خودکار در پایان مهلت سهمیه."><CharterQuotas/></PanelShell>;}
