import { ExperienceProductView } from '../../../components/operational/ExperienceProductView';
export const metadata={title:'جزئیات و رزرو | کارن‌سیر'};
export default async function ExperienceProductPage({params}:{params:Promise<{id:string}>}){const {id}=await params;return <ExperienceProductView productId={id}/>}
