'use client';
/* Loyalty circle admin: on/off, earning rate, referral bonus, levels and their benefit text, members, manual adjustment. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Stats, Table, errorOf, fa, useLoad} from './PanelKit';
import {FormFields, Note, Tabs, type Row} from './CommercePanel';
import {LoyaltyCalls} from './LoyaltyCallsPanel';

type Msg = {ok: boolean; text: string} | null;

function Settings() {
  const {state, reload, api} = useLoad<Row>('/loyalty/settings');
  const [draft, setDraft] = useState<Row | null>(null); const [msg, setMsg] = useState<Msg>(null);
  return <Async state={state}>{s => {
    const v = draft ?? {...s, levels_text: s.levels.map((l: Row) => [l.key, l.name, l.min_points, l.benefits || ''].join(' | ')).join('\n')};
    async function save(e: FormEvent) {
      e.preventDefault(); setMsg(null);
      const levels = String(v.levels_text || '').split('\n').map((l: string) => l.trim()).filter(Boolean).map((l: string) => {const [key, name, min, benefits] = l.split('|').map(x => x.trim()); return {key, name, min_points: Number(min) || 0, benefits: benefits || ''};});
      try {await api.put('/loyalty/settings', {enabled: !!v.enabled, irr_per_point: v.irr_per_point, referral_bonus_points: v.referral_bonus_points || 0, levels}); setDraft(null); setMsg({ok: true, text: 'ذخیره شد.'}); reload();}
      catch (x) {setMsg({ok: false, text: errorOf(x).message});}
    }
    return <Card title="قواعد حلقه‌ی همسفران">
      <form className="pn-form" onSubmit={save}><FormFields value={v} set={setDraft} fields={[{key: 'enabled', label: 'فعال', type: 'bool'},
        {key: 'irr_per_point', label: 'هر چند ریال = ۱ امتیاز', type: 'money', required: true}, {key: 'referral_bonus_points', label: 'امتیاز معرف (پس از اولین سفر دوست)', type: 'number'},
        {key: 'levels_text', label: 'سطح‌ها', type: 'textarea', wide: true, hint: 'هر خط: کلید لاتین | نام | حداقل امتیاز | مزایا. سطح اول از صفر شروع شود.'}]}/>
        <p className="pn-muted">امتیاز فقط برای سفری داده می‌شود که «تکمیل شد» شده باشد. مزایای هر سطح همان متنی است که اینجا می‌نویسید؛ قیمت‌ها را خودکار تغییر نمی‌دهد.</p>
        <button className="pn-btn">ذخیره</button></form><Note msg={msg}/></Card>;
  }}</Async>;
}

function Members() {
  const {state, reload, api} = useLoad<Row>('/loyalty/members');
  const [v, setV] = useState<Row>({user_id: null, points: null, reason: ''}); const [msg, setMsg] = useState<Msg>(null);
  return <Async state={state}>{d => <>
    <Stats items={d.levels.map((l: Row) => ({label: l.name, value: fa(l.members), hint: `از ${fa(l.min_points)} امتیاز`}))}/>
    {!d.enabled && <p className="pn-note">حلقه‌ی همسفران خاموش است؛ امتیازی جمع نمی‌شود.</p>}
    <Card title="اعضا"><Table rows={d.items} rowKey={(r: Row) => String(r.user_id)} empty="هنوز عضوی ندارد." cols={[
      {label: 'نام', cell: (r: Row) => r.name}, {label: 'سطح', cell: (r: Row) => r.level}, {label: 'امتیاز کل', cell: (r: Row) => fa(r.points_earned)},
      {label: 'موجودی', cell: (r: Row) => fa(r.points_balance)}, {label: 'کد معرف', cell: (r: Row) => <span className="pn-ltr">{r.referral_code}</span>}, {label: 'معرفی‌شده', cell: (r: Row) => r.referred ? 'بله' : '—'}]}/></Card>
    <Card title="اصلاح دستی امتیاز"><form className="pn-form" onSubmit={async e => {e.preventDefault(); setMsg(null); try {await api.post('/loyalty/adjust', v); setMsg({ok: true, text: 'ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}}>
      <FormFields value={v} set={setV} fields={[{key: 'user_id', label: 'شناسه کاربر', type: 'number', required: true}, {key: 'points', label: 'امتیاز (منفی برای کسر)', required: true}, {key: 'reason', label: 'دلیل', required: true}]}/>
      <button className="pn-btn">ثبت</button></form><Note msg={msg}/></Card>
  </>}</Async>;
}

export function Loyalty() {return <Tabs tabs={[['اعضا و سطح‌ها', <Members key="m"/>], ['برنامه‌ی تماس', <LoyaltyCalls key="c"/>], ['قواعد', <Settings key="s"/>]]}/>;}
