import { JourneyShell, MockNotice } from '../../components/journey/JourneyShell';
import { NearbyExplorer } from '../../components/journey/NearbyExplorer';
import { mockPlaceProvider } from '../../lib/providers/mock-place-provider';
export default async function NearbyPage(){const places=await mockPlaceProvider.searchNearby({latitude:29.615,longitude:52.535,radius:5000,sort:'distance'});return <JourneyShell><main className="journey-main nearby-main"><div className="journey-title"><div><span>همراه محلی سفر</span><h1>اطراف من</h1><p>رستوران، دیدنی‌ها و خدمات ضروری را با منبع و رابطه تجاری شفاف ببین.</p></div><MockNotice>نسخه نمایشی — مکان‌ها، فاصله‌ها و مختصات این بخش نمونه‌اند.</MockNotice></div><NearbyExplorer places={places}/></main></JourneyShell>}
