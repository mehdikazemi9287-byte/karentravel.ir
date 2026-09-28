import { Shell } from '../page';
import { ServiceIntro } from '../../components/customer/CustomerHelp';
import {VacationRentalList} from '../../components/operational/TravelCommerceViews';
export default function Page(){return <Shell><ServiceIntro title="ویلا و اقامتگاه" description="پیش از انتخاب اقامتگاه، ظرفیت، موقعیت و قوانین اقامت را بررسی کنید." vertical="vacation_rental"/><VacationRentalList/></Shell>}
