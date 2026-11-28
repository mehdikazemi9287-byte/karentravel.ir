import {Shell} from '../root-pages';
import {FaqView} from '../../components/catalog/TourCollections';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/faq');
export default function Page() {return <Shell><FaqView/></Shell>;}
