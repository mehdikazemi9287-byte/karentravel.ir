import {CarRentalSearch} from '../../components/marketplace/CarRentalSearch';
import {Shell} from '../page';
import {ContactOptions} from '../../components/customer/CustomerHelp';
export default function Page(){return <Shell><section className="container customer-page"><h1>اجارهٔ خودرو</h1><p>ظرفیت‌های قراردادی برای شهر و بازهٔ مشخص بررسی می‌شوند. پیش از رزرو، ساعت تحویل و بازگشت، شرایط راننده، ودیعه، بیمه و مسافت مجاز را در جزئیات بخوانید. تأیید نهایی خدمت پس از بررسی تأمین‌کننده و صدور مدارک انجام می‌شود.</p><CarRentalSearch/><ContactOptions/></section></Shell>}
