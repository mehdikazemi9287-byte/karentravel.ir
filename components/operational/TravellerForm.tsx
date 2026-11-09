'use client';
/* Traveller form with identity fields (کد ملی، تاریخ تولد، جنسیت، تابعیت، گذرنامه). The API validates again and is authoritative;
   this form checks the national-code digit and the per-trip requirement first so the customer sees a Persian message right away. */
import {FormEvent, useId, useState} from 'react';
import type {KarenSeirApi} from '../../lib/api/karenseir-client';
import {ApiError} from '../../lib/api/karenseir-client';
import {isValidNationalCode, NATIONAL_CODE_ERROR, normalizeDigits} from '../../lib/national-code';
import {currentJalaliYear, JalaliDateInput} from '../forms/JalaliDateInput';

export type SavedTraveller = {id: string; full_name: string; profile_reference?: string | null; national_code_masked?: string | null; passport_number_masked?: string | null;
  birth_date?: string | null; gender?: string | null; nationality?: string | null; passport_expiry?: string | null; has_national_code?: boolean; has_passport?: boolean};
/** domestic: flight/train inside Iran; international: flight abroad; none: other services. */
export type IdentityRequirement = 'none' | 'domestic' | 'international';

export const NATIONALITIES: Array<[string, string]> = [['IR', 'ایرانی'], ['AF', 'افغانستان'], ['IQ', 'عراق'], ['TR', 'ترکیه'], ['AE', 'امارات'], ['PK', 'پاکستان'], ['AZ', 'آذربایجان'], ['AM', 'ارمنستان'], ['DE', 'آلمان'], ['GB', 'بریتانیا'], ['US', 'آمریکا'], ['CN', 'چین'], ['RU', 'روسیه']];

/** What is still missing for a saved traveller under a trip requirement (empty = ready). */
export function missingIdentity(t: SavedTraveller, requirement: IdentityRequirement): string | null {
  if (requirement === 'none') return null;
  const passport = Boolean(t.has_passport && t.passport_expiry);
  if (requirement === 'international') return passport ? null : 'شماره و تاریخ انقضای گذرنامه لازم است';
  if ((t.nationality || 'IR') === 'IR') return t.has_national_code ? null : 'کد ملی لازم است';
  return passport ? null : 'شماره و تاریخ انقضای گذرنامه لازم است';
}

export function TravellerForm({api, requirement = 'none', traveller, onSaved, nameLabel = 'نام و نام خانوادگی مسافر', submitLabel = 'افزودن مسافر'}: {
  api: KarenSeirApi; requirement?: IdentityRequirement; traveller?: SavedTraveller; onSaved: (row: SavedTraveller) => void; nameLabel?: string; submitLabel?: string;
}) {
  const id = useId();
  const editing = Boolean(traveller);
  const [name, setName] = useState(traveller?.full_name || '');
  const [nationality, setNationality] = useState(traveller?.nationality || 'IR');
  const [nationalCode, setNationalCode] = useState('');
  const [gender, setGender] = useState(traveller?.gender || '');
  const [birthDate, setBirthDate] = useState(traveller?.birth_date || '');
  const [passport, setPassport] = useState('');
  const [passportExpiry, setPassportExpiry] = useState(traveller?.passport_expiry || '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const iranian = nationality === 'IR';
  const year = currentJalaliYear();
  const codeInvalid = Boolean(nationalCode) && !isValidNationalCode(nationalCode);
  const needPassport = requirement === 'international' || (requirement === 'domestic' && !iranian);
  const needCode = requirement === 'domestic' && iranian;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (name.trim().length < 3) return setError('نام و نام خانوادگی را کامل وارد کنید');
    if (codeInvalid) return setError(NATIONAL_CODE_ERROR);
    if (needCode && !nationalCode && !traveller?.has_national_code) return setError('برای این سفر کد ملی مسافر لازم است');
    const hasPassport = Boolean(passport) || Boolean(traveller?.has_passport);
    if (needPassport && (!hasPassport || !passportExpiry)) return setError('برای این سفر شماره و تاریخ انقضای گذرنامه لازم است');
    if (passport && !passportExpiry) return setError('تاریخ انقضای گذرنامه را انتخاب کنید');
    const body: Record<string, string> = {full_name: name.trim(), nationality};
    if (nationalCode) body.national_code = normalizeDigits(nationalCode);
    if (gender) body.gender = gender;
    if (birthDate) body.birth_date = birthDate;
    if (passport) body.passport_number = normalizeDigits(passport).toUpperCase();
    if (passportExpiry && (passport || traveller?.has_passport)) body.passport_expiry = passportExpiry;
    setBusy(true); setError('');
    try {
      const row = traveller ? await api.put<SavedTraveller>(`/me/travellers/${traveller.id}`, body) : await api.post<SavedTraveller>('/me/travellers', body);
      onSaved(row);
      if (!editing) { setName(''); setNationalCode(''); setPassport(''); setBirthDate(''); setPassportExpiry(''); setGender(''); }
    } catch (e) {
      setError(e instanceof ApiError && e.status < 500 ? e.message : 'ارتباط برقرار نشد؛ دوباره تلاش کنید.');
    } finally { setBusy(false); }
  }

  return <form className="traveller-form" onSubmit={submit} noValidate aria-describedby={error ? id + '-error' : undefined}>
    <label>{nameLabel}<input required minLength={3} maxLength={160} autoComplete="name" value={name} onChange={e => setName(e.target.value)}/></label>
    <label>تابعیت<select value={nationality} onChange={e => setNationality(e.target.value)}>{NATIONALITIES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
    {iranian && <label>کد ملی{needCode ? ' (الزامی)' : ''}
      <input inputMode="numeric" dir="ltr" maxLength={12} autoComplete="off" value={nationalCode} placeholder={traveller?.national_code_masked || ''}
        aria-invalid={codeInvalid} aria-describedby={id + '-code'} onChange={e => setNationalCode(e.target.value)}/>
      <small id={id + '-code'}>{codeInvalid ? NATIONAL_CODE_ERROR : traveller?.national_code_masked ? 'کد ملی ثبت شده است؛ برای تغییر، کد جدید را وارد کنید.' : '۱۰ رقم، بدون خط تیره'}</small>
    </label>}
    <label>جنسیت<select value={gender} onChange={e => setGender(e.target.value)}><option value="">انتخاب کنید</option><option value="female">زن</option><option value="male">مرد</option></select></label>
    <JalaliDateInput label="تاریخ تولد" value={birthDate} onChange={setBirthDate} fromYear={year - 110} toYear={year}/>
    {(needPassport || !iranian || requirement !== 'domestic') && <>
      <label>شماره گذرنامه{needPassport ? ' (الزامی)' : ''}<input dir="ltr" maxLength={12} autoComplete="off" value={passport} placeholder={traveller?.passport_number_masked || ''} onChange={e => setPassport(e.target.value)}/></label>
      <JalaliDateInput label="تاریخ انقضای گذرنامه" value={passportExpiry} onChange={setPassportExpiry} fromYear={year} toYear={year + 15} required={needPassport}/>
    </>}
    {error && <p id={id + '-error'} role="alert" className="form-error">{error}</p>}
    <button className="button secondary" disabled={busy}>{busy ? 'در حال ثبت…' : submitLabel}</button>
  </form>;
}
