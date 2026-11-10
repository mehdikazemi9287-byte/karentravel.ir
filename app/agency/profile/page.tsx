import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyProfilePage} from '../../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'پروفایل و مجوزها', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="پروفایل و مجوزها" intro="ویرایش فیلدهای حقوقی پس از فعال‌شدن حساب فقط با درخواست تغییر و تأیید عملیات ممکن است."><AgencyProfilePage/></PanelShell>;}
