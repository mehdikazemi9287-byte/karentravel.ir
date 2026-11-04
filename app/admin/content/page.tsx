import {PanelShell} from '../../../components/panel/PanelKit';
import {SiteContentManager} from '../../../components/panel/SiteContentPanel';
export const metadata = {title: 'مدیریت محتوای سایت', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="مدیریت محتوای سایت" intro="متن‌ها، تصویرها و لینک‌های صفحه‌ی اصلی و پانویس. هر تغییر اول پیش‌نویس است و با «انتشار» روی سایت می‌رود. قیمت و تخفیف اینجا ثبت نمی‌شود."><SiteContentManager/></PanelShell>;}
