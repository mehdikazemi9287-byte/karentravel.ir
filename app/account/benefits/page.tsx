import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerBenefits} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'مزایای سازمانی | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="مزایای سازمانی" intro="عضویت سازمانی و اعتبار تخصیص‌یافته به شما."><CustomerBenefits/></PanelShell>;}
