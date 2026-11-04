import {PanelShell} from '../../../components/panel/PanelKit';
import {AdminCommerce} from '../../../components/panel/CommercePanel';
export const metadata = {title: 'قوانین فروش', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="قوانین فروش" intro="مارک‌آپ و تخفیف، گروه‌های کاربری، جریمه‌ی کنسلی، بار مجاز و نرخ ارز."><AdminCommerce/></PanelShell>;}
