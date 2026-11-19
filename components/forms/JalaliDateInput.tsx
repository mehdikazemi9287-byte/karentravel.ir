'use client';
import '../marketplace/stitch-pages-2026-11.css';
import {useState, type ChangeEvent} from 'react';
import {isoToJalali, jalaliToIso, jalaliMonths, jalaliMonthLength, persianDigits, todayJalali} from '../../lib/domain/jalali';

type Draft = {jy?: number; jm?: number; jd?: number};
type Props = {
  value?: string; defaultValue?: string; name?: string; required?: boolean; disabled?: boolean; min?: string;
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void; 'aria-label'?: string; className?: string;
  yearsBack?: number; yearsAhead?: number;
};

/** Shamsi (Jalali) date picker: day / month / year selects. Emits and stores ISO (Gregorian) yyyy-mm-dd like <input type="date">. */
export function JalaliDateInput(props: Props) {
  const controlled = props.value !== undefined;
  const [inner, setInner] = useState(props.defaultValue || '');
  const iso = controlled ? (props.value || '') : inner;
  const [draft, setDraft] = useState<Draft>(() => (iso ? isoToJalali(iso) : {}));
  const [seenIso, setSeenIso] = useState(iso);
  if (iso !== seenIso) { setSeenIso(iso); if (iso) setDraft(isoToJalali(iso)); } // sync draft when the value changes from outside (render-phase, no effect)
  const today = todayJalali();
  const minYear = props.min ? isoToJalali(props.min).jy : today.jy - (props.yearsBack ?? 0);
  const years: number[] = [];
  for (let y = minYear; y <= today.jy + (props.yearsAhead ?? 2); y++) years.push(y);
  const maxDay = draft.jy && draft.jm ? jalaliMonthLength(draft.jy, draft.jm) : 31;
  const update = (key: keyof Draft, raw: string) => {
    const next: Draft = {...draft, [key]: raw ? Number(raw) : undefined};
    setDraft(next);
    if (next.jy && next.jm && next.jd) {
      const out = jalaliToIso({jy: next.jy, jm: next.jm, jd: Math.min(next.jd, jalaliMonthLength(next.jy, next.jm))});
      if (!controlled) setInner(out);
      props.onChange?.({target: {value: out, name: props.name ?? ''}, currentTarget: {value: out}} as unknown as ChangeEvent<HTMLInputElement>);
    }
  };
  const label = props['aria-label'] || 'تاریخ';
  return <span className={`jdate${props.className ? ' ' + props.className : ''}`} role="group" aria-label={label} dir="rtl">
    <select aria-label={`${label} — روز`} value={draft.jd ?? ''} required={props.required} disabled={props.disabled} onChange={e => update('jd', e.target.value)}>
      <option value="">روز</option>
      {Array.from({length: maxDay}, (_, i) => i + 1).map(d => <option key={d} value={d}>{persianDigits(d)}</option>)}
    </select>
    <select aria-label={`${label} — ماه`} value={draft.jm ?? ''} required={props.required} disabled={props.disabled} onChange={e => update('jm', e.target.value)}>
      <option value="">ماه</option>
      {jalaliMonths.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
    </select>
    <select aria-label={`${label} — سال`} value={draft.jy ?? ''} required={props.required} disabled={props.disabled} onChange={e => update('jy', e.target.value)}>
      <option value="">سال</option>
      {years.map(y => <option key={y} value={y}>{persianDigits(y)}</option>)}
    </select>
    {props.name && <input type="hidden" name={props.name} value={iso}/>}
  </span>;
}
