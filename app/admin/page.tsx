import {PanelShell} from '../../components/panel/PanelKit';
import {ConnectedAdmin} from '../../components/operational/ConnectedViews';
export const metadata = {title: 'کاربران و نقش‌ها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="کاربران و نقش‌ها" intro="کاربران این مجموعه و نقش هر کدام."><ConnectedAdmin/></PanelShell>;}
