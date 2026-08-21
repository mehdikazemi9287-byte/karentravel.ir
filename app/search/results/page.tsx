import type { Metadata } from 'next';
import { Suspense } from 'react';
import { UnifiedSearchView } from '../../../components/operational/UnifiedSearchView';

export const metadata:Metadata={title:'جست‌وجوی یکپارچه سفر | کارن‌سیر',description:'جست‌وجو و مقایسه پیشنهادهای سفر با وضعیت تازگی و قیمت نهایی.',robots:{index:false,follow:false},alternates:{canonical:'/search/results'}};
export default function SearchResultsPage(){return <Suspense fallback={<main className="search-results-page" dir="rtl"><div className="results-gate">در حال بازیابی جست‌وجو…</div></main>}><UnifiedSearchView/></Suspense>}
