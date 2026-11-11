import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
export const metadata = {title: 'خرید تور اقساطی', description: 'خرید تور اقساطی با نوپی، وامی‌پی، دیباکارت یا اقساط سازمانی برای کارکنان سازمان‌های طرف قرارداد کارن تراول.'};
export default function Page() {return <JourneyShell><main className="journey-main"><TourCollection collection="installment"/></main></JourneyShell>;}
