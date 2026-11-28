import {Suspense} from 'react';
import { ExperienceProductView } from '../../../components/operational/ExperienceProductView';
export async function generateMetadata({params}:{params:Promise<{id:string}>}){const {id}=await params;return {title:'جزئیات و رزرو',alternates:{canonical:`/experience-products/${id}`}}}
export default async function ExperienceProductPage({params}:{params:Promise<{id:string}>}){const {id}=await params;return <Suspense fallback={<p role="status">در حال دریافت جزئیات…</p>}><ExperienceProductView productId={id}/></Suspense>}
