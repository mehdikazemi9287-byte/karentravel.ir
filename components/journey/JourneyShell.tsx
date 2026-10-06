import {ApprovedHeader,ApprovedFooter} from '../marketplace/ApprovedFigmaHome';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { SupportDock } from './SupportDock';
export function JourneyShell({children,destination,disruption=false}:{children:ReactNode;destination?:string;disruption?:boolean}){return <div className="journey-page approved-site"><div className="approved-shared-header"><ApprovedHeader/></div>{children}<SupportDock destination={destination} disruption={disruption}/><ApprovedFooter/></div>}
export function MockNotice({children='نسخه نمایشی — اطلاعات این بخش نمونه است.'}:{children?:ReactNode}){return <div className="journey-mock" role="note">● {children}</div>}
export { SupportDock };
