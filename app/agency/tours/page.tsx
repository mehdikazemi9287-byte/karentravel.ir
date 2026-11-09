import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyTours} from '../../../components/panel/SafarsazPanel';
export const metadata = {title: 'تورهای من', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="تورهای من" intro="تورهای آژانس خود را با برنامه، هتل، نرخ هر اتاق و حرکت‌ها ثبت کنید و رزروهای دریافتی هر حرکت را ببینید. پس از «ارسال برای انتشار» و تأیید کارن تراول، تور در صفحه‌ی تورهای سایت نمایش داده می‌شود."><AgencyTours/></PanelShell>;}
