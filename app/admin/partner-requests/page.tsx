import {PanelShell} from '../../../components/panel/PanelKit';
import {PartnerDesk} from '../../../components/panel/PartnerDeskPanel';
export const metadata = {title: 'درخواست‌های خدمات همکار | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="درخواست‌های خدمات همکار" intro="درخواست‌های رزرو شهرشاد را با شهرشاد هماهنگ کنید و نتیجه را ثبت کنید؛ درخواست‌های پادویرا و گیفت آسان در پنل همان مجموعه هم ثبت شده‌اند."><PartnerDesk/></PanelShell>;}
