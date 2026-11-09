'use client';
/* Jalali (شمسی) date entry as day / month / year selects; the value in and out is an ISO Gregorian date (YYYY-MM-DD).
   Selects are easier than a calendar grid for birth dates and passport expiry, and work with keyboard and screen readers. */
import {useId, useState} from 'react';
import {isoToJalali, jalaliMonthLength, jalaliMonths, jalaliToIso, persianDigits, todayJalali} from '../../lib/domain/jalali';

type Parts = {jy: string; jm: string; jd: string};

export function JalaliDateInput({label, value, onChange, fromYear, toYear, required, hint}: {label: string; value: string; onChange: (iso: string) => void; fromYear: number; toYear: number; required?: boolean; hint?: string}) {
  const id = useId();
  const [parts, setParts] = useState<Parts>(() => toParts(value));
  const [seen, setSeen] = useState(value);
  if (value !== seen) { setSeen(value); if (value !== fromParts(parts)) setParts(toParts(value)); }
  const years: number[] = [];
  for (let y = toYear; y >= fromYear; y--) years.push(y);
  const days = parts.jy && parts.jm ? jalaliMonthLength(Number(parts.jy), Number(parts.jm)) : 31;
  function update(next: Partial<Parts>) {
    const merged = {...parts, ...next};
    if (merged.jd && merged.jy && merged.jm && Number(merged.jd) > jalaliMonthLength(Number(merged.jy), Number(merged.jm))) merged.jd = '';
    setParts(merged);
    onChange(fromParts(merged));
  }
  return <fieldset className="jalali-date" aria-describedby={hint ? id + '-hint' : undefined}>
    <legend>{label}{required ? ' (الزامی)' : ''}</legend>
    <div className="jalali-date-row">
      <label>روز<select value={parts.jd} required={required} onChange={e => update({jd: e.target.value})}><option value="">روز</option>{Array.from({length: days}, (_, i) => i + 1).map(d => <option key={d} value={d}>{persianDigits(d)}</option>)}</select></label>
      <label>ماه<select value={parts.jm} required={required} onChange={e => update({jm: e.target.value})}><option value="">ماه</option>{jalaliMonths.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
      <label>سال<select value={parts.jy} required={required} onChange={e => update({jy: e.target.value})}><option value="">سال</option>{years.map(y => <option key={y} value={y}>{persianDigits(y)}</option>)}</select></label>
    </div>
    {hint && <small id={id + '-hint'}>{hint}</small>}
  </fieldset>;
}

function toParts(iso: string): Parts {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || '')) return {jy: '', jm: '', jd: ''};
  const d = isoToJalali(iso);
  return {jy: String(d.jy), jm: String(d.jm), jd: String(d.jd)};
}

function fromParts(p: Parts): string {
  return p.jy && p.jm && p.jd ? jalaliToIso({jy: Number(p.jy), jm: Number(p.jm), jd: Number(p.jd)}) : '';
}

export const currentJalaliYear = () => todayJalali().jy;
