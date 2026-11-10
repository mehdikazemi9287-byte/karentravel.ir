import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
export const metadata = {title: 'تورهای نوروزی', description: 'تورهای داخلی و خارجی با حرکت در تعطیلات نوروز.'};
export default function Page() {return <JourneyShell><main className="journey-main"><TourCollection collection="nowruz"/></main></JourneyShell>;}
