import { JourneyShell } from '../../components/journey/JourneyShell';
import { ReviewsView } from '../../components/operational/EcosystemViews';
export const metadata={title:'نظرهای تأییدشده | کارن‌سیر',description:'نظرهای مسافران با تفکیک رزرو تأییدشده و پاسخ تأمین‌کننده'};
export default function ReviewsPage(){return <JourneyShell><main className="journey-main"><ReviewsView/></main></JourneyShell>}
