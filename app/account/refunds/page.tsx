import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerRefundList} from '../../../components/panel/aftersales/CustomerAfterSales';
export const metadata = {title: 'لغو و استرداد', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="لغو و استرداد" intro="وضعیت هر درخواست، گام بعدی و موعد آن."><CustomerRefundList/></PanelShell>;}
