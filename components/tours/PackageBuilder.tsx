'use client';
/* Stitch round 6 — «سفارشی‌سازی خدمات اختصاصی». Options and prices come only from the organiser's departure; the total is re-quoted by the server. */
import './tours-round6.css';

export type Addon = {code: string; title: string; price?: number; unit: 'person' | 'booking'; category: string; description?: string};
const CATEGORY_FA: Record<string, string> = {food: 'رژیم و ترجیحات غذایی', accessibility: 'پایش توان جسمی و حرکتی', transport: 'ترابری و حمل‌ونقل سفر', room: 'ارتقای اقامت', activity: 'برنامه‌های تکمیلی', insurance: 'بیمه و پوشش', other: 'سایر خدمات'};

export function PackageBuilder({addons, selected, onChange, disabled}: {addons: Addon[]; selected: string[]; onChange: (codes: string[]) => void; disabled?: boolean}) {
  if (!addons.length) return null;
  const groups = addons.reduce<Record<string, Addon[]>>((acc, a) => {(acc[a.category] ||= []).push(a); return acc;}, {});
  const toggle = (code: string) => onChange(selected.includes(code) ? selected.filter(c => c !== code) : [...selected, code]);
  return <section className="package-builder" aria-label="سفارشی‌سازی پکیج">
    <h3>سفارشی‌سازی خدمات اختصاصی</h3><p className="pb-intro">برنامه را متناسب با نیازها و آسایش خود شخصی‌سازی کنید. مبلغ نهایی پس از انتخاب، دوباره از سامانه استعلام می‌شود.</p>
    {Object.entries(groups).map(([cat, items]) => <fieldset key={cat} className="pb-group" disabled={disabled}><legend>{CATEGORY_FA[cat] || cat}</legend>
      {items.map(a => <label key={a.code} className={`pb-option${selected.includes(a.code) ? ' on' : ''}`}>
        <input type="checkbox" checked={selected.includes(a.code)} onChange={() => toggle(a.code)}/>
        <span><b>{a.title}</b>{a.description && <small>{a.description}</small>}</span>
        <em>{typeof a.price === 'number' ? (a.price === 0 ? 'رایگان' : `${a.price.toLocaleString('fa-IR')} ریال${a.unit === 'person' ? ' برای هر نفر' : ' برای کل رزرو'}`) : 'قیمت پس از ورود'}</em>
      </label>)}
    </fieldset>)}
  </section>;
}
