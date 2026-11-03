import {PanelShell} from '../../../components/panel/PanelKit';
import {DocumentQueue} from '../../../components/panel/TravellerDocumentsPanel';
export const metadata = {title: 'صف مدارک مسافران | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="صف مدارک مسافران" intro="بررسی مدارک با پیش‌نمایش پوشانده؛ دیدن اصل مدرک فقط با ثبت دلیل در سوابق ممیزی. فایل‌ها پس از مهلت نگهداری خودکار حذف می‌شوند."><DocumentQueue/></PanelShell>;}
