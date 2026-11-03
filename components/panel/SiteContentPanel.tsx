'use client';
/* Site content management: edit homepage/footer slots as drafts, publish, restore earlier versions, and keep a media library.
   Fields are fixed per slot; prices and discounts are refused by the server and still come only from real offers. */
import {useState} from 'react';
import {Async, Card, dateFa, errorOf, fa, useLoad} from './PanelKit';
import {DEFAULT_CONTENT, imageSrc, invalidateSiteContent, type CmsCard} from '../../lib/site-content';

type Json = Record<string, unknown>;
type Block = {key: string; label: string; draft: Json | null; published: Json | null; version: number; has_unpublished_changes: boolean; published_at: string | null};
type Media = {id: string; ref: string; filename: string; size_bytes: number; alt: string; created_at: string; in_use: boolean};
type Msg = {ok: boolean; text: string} | null;

type Field = {name: string; label: string; kind: 'text' | 'long' | 'image' | 'bool' | 'link' | 'cards' | 'list'; max?: number; min?: number; card?: ('title2' | 'meta')[]; hint?: string};
const SPEC: Record<string, Field[]> = {
  announcement: [{name: 'active', label: 'نمایش نوار', kind: 'bool'}, {name: 'text', label: 'متن', kind: 'long'}, {name: 'href', label: 'لینک (اختیاری)', kind: 'link'}],
  hero: [{name: 'title', label: 'تیتر — خط اول', kind: 'text'}, {name: 'title2', label: 'تیتر — خط دوم', kind: 'text'}, {name: 'subtitle', label: 'زیرتیتر — خط اول', kind: 'text'},
    {name: 'subtitle2', label: 'زیرتیتر — خط دوم', kind: 'text'}, {name: 'image', label: 'تصویر اصلی', kind: 'image'}, {name: 'image_alt', label: 'توضیح تصویر برای نابینایان', kind: 'text'},
    {name: 'minis', label: 'دو میان‌بر روی تصویر', kind: 'cards', max: 2, min: 0}],
  bento: [{name: 'title', label: 'تیتر — خط اول', kind: 'text'}, {name: 'title2', label: 'تیتر — خط دوم', kind: 'text'}, {name: 'tiles', label: 'چهار کاشی مقصد', kind: 'cards', min: 4, max: 4}],
  trips: [{name: 'title', label: 'تیتر بخش', kind: 'text'}, {name: 'items', label: 'کارت‌های سفر', kind: 'cards', min: 1, max: 6, card: ['title2', 'meta'], hint: 'مدت سفر مثل «۳ روز و ۲ شب»؛ قیمت ننویسید، روی کارت «استعلام قیمت» نمایش داده می‌شود.'}],
  assistant: [{name: 'title', label: 'تیتر', kind: 'text'}, {name: 'prompts', label: 'پیشنهادهای گفتگو', kind: 'list', min: 1, max: 6}],
  compare: [{name: 'title', label: 'تیتر', kind: 'text'}, {name: 'items', label: 'دو گزینه برای مقایسه', kind: 'cards', min: 2, max: 2}],
  organization: [{name: 'title', label: 'تیتر', kind: 'text'}, {name: 'items', label: 'ویژگی‌ها', kind: 'list', min: 1, max: 4}],
  footer: [{name: 'tagline', label: 'شعار پانویس', kind: 'long'}, {name: 'copyright', label: 'متن حق نشر', kind: 'text'}],
};
const CARD_FA = {title: 'عنوان', title2: 'خط دوم عنوان', meta: 'توضیح کوتاه', href: 'لینک', image: 'تصویر'};

function ImagePick({value, media, onChange, label}: {value: string; media: Media[]; onChange: (v: string) => void; label: string}) {
  const builtIn = !value.startsWith('media:');
  return <div className="cms-img">
    {/* eslint-disable-next-line @next/next/no-img-element */}
    {value && <img src={imageSrc(value)} alt=""/>}
    <select aria-label={label} value={value} onChange={e => onChange(e.target.value)}>
      {builtIn && <option value={value}>تصویر فعلی سایت</option>}
      {media.map(m => <option key={m.id} value={m.ref}>{m.alt || m.filename}</option>)}
    </select>
  </div>;
}

function CardsEditor({f, value, media, onChange}: {f: Field; value: CmsCard[]; media: Media[]; onChange: (v: CmsCard[]) => void}) {
  const set = (i: number, k: keyof CmsCard, v: string) => onChange(value.map((c, j) => (j === i ? {...c, [k]: v} : c)));
  const extra = f.card ?? [];
  return <fieldset className="cms-cards"><legend>{f.label}</legend>{f.hint && <p className="pn-muted">{f.hint}</p>}
    {value.map((c, i) => <div className="cms-card" key={i}>
      <b>{fa(i + 1)}</b>
      <label>{CARD_FA.title}<input value={c.title} maxLength={60} onChange={e => set(i, 'title', e.target.value)}/></label>
      {extra.map(k => <label key={k}>{CARD_FA[k]}<input value={c[k] ?? ''} maxLength={60} onChange={e => set(i, k, e.target.value)}/></label>)}
      <label>{CARD_FA.href}<input dir="ltr" value={c.href} placeholder="/destinations/shiraz" onChange={e => set(i, 'href', e.target.value)}/></label>
      <ImagePick label={`${CARD_FA.image} ${fa(i + 1)}`} value={c.image} media={media} onChange={v => set(i, 'image', v)}/>
      {(f.min ?? 0) < value.length && <button type="button" className="pn-btn ghost" onClick={() => onChange(value.filter((_, j) => j !== i))}>حذف</button>}
    </div>)}
    {value.length < (f.max ?? 6) && <button type="button" className="pn-btn ghost" onClick={() => onChange([...value, {title: '', href: '/', image: value[0]?.image ?? '/images/approved-figma/refTripNorth.jpg'}])}>افزودن کارت</button>}
  </fieldset>;
}

function BlockEditor({block, media, done}: {block: Block; media: Media[]; done: (m: Msg) => void}) {
  const {api} = useLoad<Json>(null);
  const start = (block.draft ?? block.published ?? DEFAULT_CONTENT[block.key as keyof typeof DEFAULT_CONTENT]) as Json;
  const [v, setV] = useState<Json>(start);
  const [revs, setRevs] = useState<{id: string; version: number; created_at: string}[] | null>(null);
  const put = (k: string, x: unknown) => setV({...v, [k]: x});
  async function run(fn: () => Promise<unknown>, ok: string, publish = false) {
    try {await fn(); if (publish) invalidateSiteContent(); done({ok: true, text: ok});} catch (x) {done({ok: false, text: errorOf(x).message});}
  }
  const save = () => run(() => api.put(`/cms/blocks/${block.key}`, v), 'پیش‌نویس ذخیره شد؛ تا انتشار، سایت تغییری نمی‌کند.');
  const publish = () => run(async () => {await api.put(`/cms/blocks/${block.key}`, v); await api.post(`/cms/blocks/${block.key}/publish`, {});}, 'روی سایت منتشر شد.', true);
  const unpublish = () => run(() => api.post(`/cms/blocks/${block.key}/unpublish`, {}), 'از سایت برداشته شد؛ سایت محتوای پیش‌فرض را نشان می‌دهد.', true);
  const history = async () => {try {setRevs((await api.get<{items: {id: string; version: number; created_at: string}[]}>(`/cms/blocks/${block.key}/revisions`)).items);} catch (x) {done({ok: false, text: errorOf(x).message});}};
  const restore = (id: string) => run(() => api.post(`/cms/blocks/${block.key}/revisions/${id}/restore`, {}), 'این نسخه در پیش‌نویس گذاشته شد؛ برای نمایش، «انتشار» را بزنید.');
  return <div className="cms-editor">
    <p className="cms-state">{block.published_at ? `منتشرشده، نسخه‌ی ${fa(block.version)} — ${dateFa(block.published_at)}` : 'هنوز منتشر نشده؛ سایت محتوای پیش‌فرض را نشان می‌دهد.'}{block.has_unpublished_changes && <span className="cms-dirty">تغییر منتشرنشده دارد</span>}</p>
    {SPEC[block.key].map(f => {
      const val = v[f.name];
      if (f.kind === 'bool') return <label className="cms-check" key={f.name}><input type="checkbox" checked={!!val} onChange={e => put(f.name, e.target.checked)}/>{f.label}</label>;
      if (f.kind === 'image') return <label key={f.name}>{f.label}<ImagePick label={f.label} value={String(val ?? '')} media={media} onChange={x => put(f.name, x)}/></label>;
      if (f.kind === 'cards') return <CardsEditor key={f.name} f={f} value={(val as CmsCard[]) ?? []} media={media} onChange={x => put(f.name, x)}/>;
      if (f.kind === 'list') {const list = (val as string[]) ?? []; return <fieldset key={f.name} className="cms-cards"><legend>{f.label}</legend>
        {list.map((p, i) => <div className="cms-row" key={i}><input aria-label={`${f.label} ${fa(i + 1)}`} value={p} maxLength={60} onChange={e => put(f.name, list.map((q, j) => (j === i ? e.target.value : q)))}/>
          {list.length > (f.min ?? 1) && <button type="button" className="pn-btn ghost" onClick={() => put(f.name, list.filter((_, j) => j !== i))}>حذف</button>}</div>)}
        {list.length < (f.max ?? 6) && <button type="button" className="pn-btn ghost" onClick={() => put(f.name, [...list, ''])}>افزودن</button>}</fieldset>;}
      return <label key={f.name}>{f.label}{f.kind === 'long' ? <textarea rows={2} value={String(val ?? '')} onChange={e => put(f.name, e.target.value)}/>
        : <input dir={f.kind === 'link' ? 'ltr' : undefined} value={String(val ?? '')} onChange={e => put(f.name, e.target.value)}/>}</label>;
    })}
    <div className="cms-actions">
      <button className="pn-btn ghost" type="button" onClick={() => void save()}>ذخیره‌ی پیش‌نویس</button>
      <button className="pn-btn" type="button" onClick={() => void publish()}>انتشار روی سایت</button>
      {block.published && <button className="pn-btn ghost" type="button" onClick={() => void unpublish()}>برداشتن از سایت</button>}
      <button className="pn-btn ghost" type="button" onClick={() => setV(DEFAULT_CONTENT[block.key as keyof typeof DEFAULT_CONTENT] as unknown as Json)}>بازگشت به پیش‌فرض</button>
      <button className="pn-btn ghost" type="button" onClick={() => void history()}>نسخه‌های قبلی</button>
      <a className="pn-btn ghost" href="/" target="_blank" rel="noreferrer">دیدن سایت</a>
    </div>
    {revs && (revs.length ? <ul className="cms-revs">{revs.map(r => <li key={r.id}>نسخه‌ی {fa(r.version)} — {dateFa(r.created_at)} <button className="pn-btn ghost" type="button" onClick={() => void restore(r.id)}>برگرداندن به پیش‌نویس</button></li>)}</ul> : <p className="pn-muted">نسخه‌ی منتشرشده‌ای وجود ندارد.</p>)}
  </div>;
}

function MediaLibrary({media, reload, done}: {media: Media[]; reload: () => void; done: (m: Msg) => void}) {
  const {api} = useLoad<Json>(null);
  const [busy, setBusy] = useState(false);
  async function upload(files: FileList | null) {
    if (!files?.length) return; setBusy(true);
    try {for (const file of Array.from(files)) {const form = new FormData(); form.append('file', file); form.append('alt', ''); const r = await api.postForm<{duplicate?: boolean}>('/cms/media', form); if (r.duplicate) done({ok: true, text: `«${file.name}» قبلاً در کتابخانه بود.`});}
      done({ok: true, text: 'تصویر به کتابخانه اضافه شد. برای دسترس‌پذیری، توضیح تصویر را بنویسید.'}); reload();}
    catch (x) {done({ok: false, text: errorOf(x).message});} finally {setBusy(false);}
  }
  const act = async (fn: () => Promise<unknown>, ok: string) => {try {await fn(); done({ok: true, text: ok}); reload();} catch (x) {done({ok: false, text: errorOf(x).message});}};
  return <div>
    <label className="cms-upload">افزودن تصویر (JPG، PNG یا WebP، حداکثر ۳ مگابایت)<input type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={busy} onChange={e => void upload(e.target.files)}/></label>
    {media.length === 0 ? <p className="pn-muted">هنوز تصویری بارگذاری نشده است.</p> : <div className="cms-media">{media.map(m => <figure key={m.id}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imageSrc(m.ref)} alt={m.alt}/>
      <figcaption><small dir="ltr">{m.filename} · {fa(Math.round(m.size_bytes / 1024))}KB</small>
        <input aria-label={`توضیح ${m.filename}`} defaultValue={m.alt} placeholder="توضیح تصویر" onBlur={e => e.target.value !== m.alt && void act(() => api.put(`/cms/media/${m.id}`, {alt: e.target.value}), 'توضیح تصویر ذخیره شد.')}/>
        {m.in_use ? <span className="cms-dirty">در سایت استفاده شده</span> : <button className="pn-btn ghost" type="button" onClick={() => void act(() => api.delete(`/cms/media/${m.id}`, {}), 'تصویر حذف شد.')}>حذف</button>}
      </figcaption></figure>)}</div>}
  </div>;
}

export function SiteContentManager() {
  const blocks = useLoad<{items: Block[]}>('/cms/blocks');
  const media = useLoad<{items: Media[]}>('/cms/media');
  const [tab, setTab] = useState<'blocks' | 'media'>('blocks'); const [key, setKey] = useState('hero'); const [msg, setMsg] = useState<Msg>(null);
  const done = (m: Msg) => {setMsg(m); blocks.reload(); media.reload();};
  const lib = media.state.kind === 'ready' ? media.state.data.items : [];
  return <>
    <div className="cms-tabs" role="tablist">
      <button role="tab" aria-selected={tab === 'blocks'} className={tab === 'blocks' ? 'on' : ''} onClick={() => setTab('blocks')}>بخش‌های صفحه</button>
      <button role="tab" aria-selected={tab === 'media'} className={tab === 'media' ? 'on' : ''} onClick={() => setTab('media')}>کتابخانه‌ی رسانه {lib.length ? `(${fa(lib.length)})` : ''}</button>
    </div>
    {msg && <p className={`pn-note${msg.ok ? '' : ' error'}`} role={msg.ok ? 'status' : 'alert'}>{msg.text}</p>}
    {tab === 'media' ? <Card title="کتابخانه‌ی رسانه"><MediaLibrary media={lib} reload={media.reload} done={setMsg}/></Card>
      : <Async state={blocks.state}>{d => {const b = d.items.find(x => x.key === key) ?? d.items[0]; return <div className="cms-grid">
        <nav className="cms-list" aria-label="بخش‌های سایت">{d.items.map(x => <button key={x.key} className={x.key === b.key ? 'on' : ''} onClick={() => {setKey(x.key); setMsg(null);}}>
          <span>{x.label}</span><small>{x.published ? (x.has_unpublished_changes ? 'تغییر منتشرنشده' : 'منتشرشده') : 'پیش‌فرض سایت'}</small></button>)}</nav>
        <Card title={b.label}><BlockEditor key={b.key} block={b} media={lib} done={done}/></Card></div>;}}</Async>}
  </>;
}
