import { JourneyShell } from '../../components/journey/JourneyShell';
import { ReviewsView } from '../../components/operational/EcosystemViews';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/reviews');
export default function ReviewsPage(){return <JourneyShell><main className="journey-main"><ReviewsView/></main></JourneyShell>}
