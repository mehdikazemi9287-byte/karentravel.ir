import {PanelShell} from '../../../components/panel/PanelKit';
import {PlatformTenants} from '../../../components/panel/PlatformTenantsPanel';
export const metadata = {title: 'مستأجرها و وایت‌لیبل | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="مستأجرها و وایت‌لیبل" intro="ساخت مستأجر تازه با مدیر خودش، برند، دامنه‌ی اختصاصی و خدمات فعال؛ فقط برای مدیر پلتفرم."><PlatformTenants/></PanelShell>;}
