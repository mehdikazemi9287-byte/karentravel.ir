import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerRefunds} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'لغو و استرداد | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="لغو و استرداد" intro="شرایط لغو هر رزرو و وضعیت استردادها."><CustomerRefunds/></PanelShell>;}
