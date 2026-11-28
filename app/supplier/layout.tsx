import type {Metadata} from 'next';
// Private area (panel, account, booking flow or internal search): never indexed. Renders its pages unchanged.
export const metadata: Metadata = {robots: {index: false, follow: false}};
export default function PrivateLayout({children}: {children: React.ReactNode}) {return children;}
