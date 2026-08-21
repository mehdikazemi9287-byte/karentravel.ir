import type { Metadata } from 'next';
import { UnifiedSearchView } from '../../../components/operational/UnifiedSearchView';

export const metadata:Metadata={title:'جست‌وجوی یکپارچه سفر | کارن‌سیر',description:'جست‌وجو و مقایسه پیشنهادهای سفر با وضعیت تازگی و قیمت نهایی.',robots:{index:false,follow:false},alternates:{canonical:'/search/results'}};
export default function SearchResultsPage(){return <UnifiedSearchView/>}
