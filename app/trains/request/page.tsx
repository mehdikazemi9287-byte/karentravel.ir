import {Suspense} from 'react';
import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TrainRequestForm} from '../../../components/panel/TrainRequestsPanel';
export const metadata = {title: 'درخواست بلیت قطار | کارن‌سیر', robots: {index: false}};
export default function Page() {return <JourneyShell><main className="journey-main flight-entry"><h1>درخواست بلیت قطار</h1><p>مسیر، تاریخ و نوع واگن را بنویس؛ کارشناس قطارهای موجود را با ساعت و قیمت برایت می‌فرستد.</p><Suspense fallback={<p role="status">در حال آماده‌سازی…</p>}><TrainRequestForm/></Suspense></main></JourneyShell>;}
