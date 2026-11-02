'use client';
/* Revenue from applied markup/discount rules, per service. Only bookings created with a rule appear; nothing is estimated. */
import {useState} from 'react';
import {Async, Card, Stats, Table, dateFa, fa, money, serviceFa, useLoad} from './PanelKit';
import {FormFields, type Row} from './CommercePanel';

export function MarkupRevenue() {
  const [f, setF] = useState<Row>({date_from: '', date_to: '', service_type: ''});
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v).map(([k, v]) => [k, String(v)])).toString();
  const {state} = useLoad<{by_service: Row[]; items: Row[]; total: number}>(`/commerce/markup-revenue${qs ? `?${qs}` : ''}`);
  return <>
    <Card title="فیلتر"><div className="pn-form"><FormFields value={f} set={setF} fields={[{key: 'date_from', label: 'از تاریخ', type: 'date'}, {key: 'date_to', label: 'تا تاریخ', type: 'date'},
      {key: 'service_type', label: 'خدمت', type: 'select', options: [['', 'همه'], ['flight', 'پرواز'], ['hotel', 'هتل'], ['tour', 'تور'], ['train', 'قطار'], ['bus', 'اتوبوس'], ['insurance', 'بیمه'], ['visa', 'ویزا'], ['package', 'پرواز + هتل'], ['transfer', 'ترانسفر']]}]}/></div></Card>
    <Async state={state}>{d => {
      const irr = d.by_service.filter(g => g.currency === 'IRR');
      const sum = (k: string) => irr.reduce((a, g) => a + (g[k] as number), 0);
      return <>
        <Stats items={[{label: 'رزرو با قانون فروش', value: fa(d.total)}, {label: 'سود افزوده (ریال)', value: money(sum('markup'), 'IRR')}, {label: 'تخفیف داده‌شده (ریال)', value: money(sum('discount'), 'IRR')}, {label: 'درآمد خالص (ریال)', value: money(sum('revenue'), 'IRR')}]}/>
        <Card title="به تفکیک خدمت"><Table rows={d.by_service} rowKey={g => `${g.service_type}-${g.currency}`} empty="هنوز رزروی با قانون سود/تخفیف ثبت نشده است." cols={[
          {label: 'خدمت', cell: g => serviceFa(g.service_type)}, {label: 'تعداد', cell: g => fa(g.bookings)}, {label: 'خالص', cell: g => money(g.net_total, g.currency)},
          {label: 'فروش', cell: g => money(g.sell_total, g.currency)}, {label: 'سود', cell: g => money(g.markup, g.currency)}, {label: 'تخفیف', cell: g => money(g.discount, g.currency)}, {label: 'درآمد', cell: g => money(g.revenue, g.currency)}]}/></Card>
        <Card title="ریز رزروها"><Table rows={d.items} rowKey={r => r.id} empty="—" cols={[
          {label: 'رزرو', cell: r => r.booking_reference ?? r.reservation_id}, {label: 'خدمت', cell: r => serviceFa(r.service_type)}, {label: 'قانون', cell: r => r.rule_title ?? '—'},
          {label: 'تعداد', cell: r => fa(r.units)}, {label: 'خالص واحد', cell: r => money(r.net_unit, r.currency)}, {label: 'فروش واحد', cell: r => money(r.sell_unit, r.currency)},
          {label: 'سود/تخفیف', cell: r => money(r.markup_total, r.currency)}, {label: 'سند', cell: r => <span className={`pn-badge ${r.posted ? 'ok' : ''}`}>{r.posted ? 'ثبت در دفتر' : 'بدون سند'}</span>}, {label: 'تاریخ', cell: r => dateFa(r.created_at)}]}/></Card>
      </>;
    }}</Async>
  </>;
}
