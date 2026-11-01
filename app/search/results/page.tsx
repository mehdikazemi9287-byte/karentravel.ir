import type { Metadata } from 'next';
import { Suspense } from 'react';
import Link from 'next/link';
import { UnifiedSearchView } from '../../../components/operational/UnifiedSearchView';

export const metadata:Metadata={title:'جست‌وجوی یکپارچه سفر | کارن‌سیر',description:'جست‌وجو و مقایسه پیشنهادهای سفر با وضعیت تازگی و قیمت نهایی.',robots:{index:false,follow:false},alternates:{canonical:'/search/results'}};
function SearchResultsFallback(){
  return <main className="search-results-page" dir="rtl">
    <nav className="results-breadcrumb" aria-label="مسیر بازگشت"><Link href="/"><span className="brand-mark" aria-hidden="true">ک</span>کارن‌سیر</Link><i aria-hidden="true">←</i><span>نتایج جست‌وجو</span></nav>
    <div className="results-gate">در حال بازیابی جست‌وجو…</div>
  </main>;
}

export default function SearchResultsPage(){return <Suspense fallback={<SearchResultsFallback/>}><UnifiedSearchView/></Suspense>}
