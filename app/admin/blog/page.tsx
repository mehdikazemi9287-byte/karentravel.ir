import {PanelShell} from '../../../components/panel/PanelKit';
import {BlogManager} from '../../../components/panel/BlogPanel';
export const metadata = {title: 'وبلاگ', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="وبلاگ" intro="راهنمای مقصد، نکته‌های سفر و خبرها. هر مطلب اول پیش‌نویس است و با «انتشار» روی سایت می‌رود. قیمت و تخفیف در مطلب ثبت نمی‌شود."><BlogManager/></PanelShell>;}
