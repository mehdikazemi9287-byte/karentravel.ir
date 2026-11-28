import {JourneyShell} from '../../components/journey/JourneyShell';
import {StayLanding} from '../../components/marketplace/StayLanding';
import {seoFor} from '../../lib/seo-pages';
import {RelatedLinks} from '../../components/seo/RelatedLinks';
export const metadata = seoFor('/hotels');
export default function Page(){return <JourneyShell><StayLanding/><RelatedLinks group="hotels"/></JourneyShell>}
