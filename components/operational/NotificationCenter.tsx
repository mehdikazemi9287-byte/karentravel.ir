'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError } from '../../lib/api/karenseir-client';

type Notice = { id: string; topic: string; title: string; message: string; deep_link?: string | null; status: string; created_at: string };
type Pref = { topic: string; channel: string; enabled: boolean };
type Channel = { channel: string; deliverable_now: boolean; note: string };

const CH_LABEL: Record<string, string> = { web: 'وب', app: 'اپ', push: 'نوتیفیکیشن (Push)', sms: 'پیامک (SMS)' };
const msgOf = (e: unknown) => (e instanceof ApiError ? e.message : 'خطای پیش‌بینی‌نشده رخ داد.');
const faTime = (iso: string) => new Date(iso).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' });

export function NotificationCenter() {
  const { api, session } = useAuth();
  const [items, setItems] = useState<Notice[] | null>(null);
  const [prefs, setPrefs] = useState<Pref[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [err, setErr] = useState<{ status: number; message: string } | null>(null);
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const [n, p, c] = await Promise.all([
        api.get<Notice[]>('/me/notifications'),
        api.get<Pref[]>('/me/notification-preferences'),
        api.get<Channel[]>('/me/notification-channels'),
      ]);
      setItems(n); setPrefs(p); setChannels(c); setErr(null);
    } catch (e) { setErr(e instanceof ApiError ? { status: e.status, message: e.message } : { status: 0, message: msgOf(e) }); }
  }, [api]);
  useEffect(() => { if (session) load(); }, [session, load]);

  const topics = Array.from(new Set(prefs.map(p => p.topic))).sort();
  const enabledFor = (topic: string, channel: string) => {
    const row = prefs.find(p => p.topic === topic && p.channel === channel);
    return row ? row.enabled : true; // default-on unless explicitly disabled
  };
  async function setPref(topic: string, channel: string, enabled: boolean) {
    setNotice('در حال ذخیره ترجیح…');
    try {
      await api.put('/me/notification-preferences', { topic, channel, enabled });
      setNotice('ترجیح ذخیره شد.');
      setPrefs(await api.get<Pref[]>('/me/notification-preferences'));
    } catch (e) { setNotice(msgOf(e)); }
  }

  if (!session) return <div className="container"><p role="alert" className="rounded-2xl bg-rose-50 p-6 text-rose-700">برای مشاهده اعلان‌ها وارد شوید.</p><Link className="button primary" href="/login?redirect=%2Fnotifications">ورود و مشاهده اعلان‌ها</Link></div>;
  if (err) return <div className="container"><p role="alert" className="rounded-2xl bg-rose-50 p-6 text-rose-700">اعلان‌ها دریافت نشدند؛ دوباره تلاش کنید.</p><button className="button secondary" onClick={()=>void load()}>تلاش دوباره</button><Link href="/support">پشتیبانی</Link></div>;
  if (!items) return <div className="container"><p role="status" className="my-8 animate-pulse rounded-2xl bg-white p-8 text-center text-slate-600">در حال دریافت اعلان‌ها…</p></div>;

  const unread = items.filter(i => i.status !== 'read' && i.status !== 'delivered').length;

  return <div className="container" style={{ maxWidth: 820 }}>
    <div className="page-hero"><span className="eyebrow">مرکز اعلان‌ها · داده احرازشده</span>
      <h1>اعلان‌ها و ترجیحات</h1>
      <p>{unread > 0 ? `${unread.toLocaleString('fa-IR')} اعلان خوانده‌نشده` : 'همه‌ی اعلان‌ها خوانده شده‌اند'}</p></div>
    {notice && <p role="status" className="mb-4 rounded-xl bg-cyan-50 p-4 text-sm">{notice}</p>}

    <section className="panel mb-5">
      <h2 className="font-black">جریان اعلان‌ها</h2>
      {items.length === 0
        ? <p className="mt-3 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-600">اعلانی ندارید.</p>
        : <ul className="mt-4 space-y-3">{items.map(n => {
            const isNew = n.status !== 'read' && n.status !== 'delivered';
            return <li key={n.id} className={`rounded-xl p-4 ${isNew ? 'bg-cyan-50' : 'bg-slate-50'}`}>
              <div className="flex items-start justify-between gap-3">
                <div><b className="block">{n.title}{isNew && <span className="mr-2 rounded-full bg-cyan-600 px-2 py-0.5 text-xs text-white">جدید</span>}</b>
                  <small className="text-slate-600">{n.message}</small></div>
                <time className="shrink-0 text-xs text-slate-500">{faTime(n.created_at)}</time>
              </div>
              <div className="mt-2 flex items-center gap-3 text-xs">
                <span className="rounded bg-slate-200 px-2 py-0.5">{n.topic}</span>
                {n.deep_link && <Link className="text-link" href={n.deep_link}>مشاهده ←</Link>}
              </div>
            </li>;
          })}</ul>}
    </section>

    <section className="panel">
      <h2 className="font-black">ترجیحات کانال</h2>
      <div className="mt-3 space-y-1 text-xs text-slate-600">
        {channels.map(c => <p key={c.channel}>
          <b>{CH_LABEL[c.channel]}:</b> {c.deliverable_now ? 'فعال' : `غیرفعال — ${c.note}`}
        </p>)}
      </div>
      {topics.length === 0
        ? <p className="mt-3 text-sm text-slate-600">هنوز ترجیحی تنظیم نشده است؛ همه‌ی کانال‌ها به‌صورت پیش‌فرض فعال‌اند.</p>
        : <div className="mt-4 overflow-x-auto"><table className="w-full text-sm">
            <thead><tr><th className="p-2 text-right">موضوع</th>{['web', 'app', 'push', 'sms'].map(ch => <th key={ch} className="p-2">{CH_LABEL[ch]}</th>)}</tr></thead>
            <tbody>{topics.map(topic => <tr key={topic} className="border-t">
              <td className="p-2 font-bold">{topic}</td>
              {['web', 'app', 'push', 'sms'].map(ch => {
                const cap = channels.find(c => c.channel === ch);
                return <td key={ch} className="p-2 text-center">
                  <input type="checkbox" aria-label={`${topic} - ${CH_LABEL[ch]}`} checked={enabledFor(topic, ch)}
                    onChange={e => setPref(topic, ch, e.target.checked)} />
                  {cap && !cap.deliverable_now && <small className="block text-[10px] text-amber-600">ذخیره می‌شود؛ تحویل خیر</small>}
                </td>;
              })}
            </tr>)}</tbody>
          </table></div>}
    </section>
  </div>;
}
