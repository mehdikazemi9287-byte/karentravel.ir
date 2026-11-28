/* Homepage route. The page body (and the shared <Shell>) live in ./root-pages, a client module; this server wrapper
   exists so the homepage can export its own metadata (title, description, canonical). The rendered page is unchanged. */
import RootPage from './root-pages';
import {seoFor} from '../lib/seo-pages';
export {Shell} from './root-pages';
export const metadata = seoFor('/');
export default function Page() {return <RootPage/>;}
