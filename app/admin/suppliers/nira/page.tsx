import {PanelShell} from '../../../../components/panel/PanelKit';
import {NiraConsole} from '../../../../components/panel/NiraConsolePanel';
export const metadata = {title: 'آزمون اتصال نیرا', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="آزمون اتصال نیرا" intro="وضعیت ایرلاین‌های متصل به نیرا و یک جست‌وجوی تکی برای هر ایرلاین، با پاسخ خام بدون نام کاربری و رمز. رزرو و صدور بلیت از این صفحه ممکن نیست."><NiraConsole/></PanelShell>;}
