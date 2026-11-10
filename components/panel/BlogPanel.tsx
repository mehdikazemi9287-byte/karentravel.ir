'use client';
/* Blog editor: write posts as drafts, publish or take them down. Body is plain text: blank line = new paragraph,
   "## " = sub-heading, "- " = bullet. Prices and discounts are refused by the server. */
import {useState} from 'react';
import {Async, Card, dateFa, errorOf, fa, useLoad} from './PanelKit';
import {blogImage} from '../../lib/blog';

type Post = {id: string; slug: string; title: string; excerpt: string; category: string; category_label: string; tags: string[]; cover: string; cover_alt: string;
  status: string; published_at: string | null; updated_at: string | null; body?: string};
type Media = {id: string; ref: string; filename: string; alt: string};
type Msg = {ok: boolean; text: string} | null;
const CATS = [['guide', 'راهنمای مقصد'], ['tips', 'نکته‌های سفر'], ['visa', 'ویزا و مدارک'], ['news', 'اخبار کارن تراول']];
const blank = {slug: '', title: '', excerpt: '', body: '', category: 'guide', tags: '', cover: '', cover_alt: ''};

function Editor({post, media, done, close}: {post: Post | null; media: Media[]; done: (m: Msg) => void; close: () => void}) {
  const {api} = useLoad<unknown>(null);
  const [v, setV] = useState(post ? {...blank, ...post, body: post.body ?? '', tags: post.tags.join('، ')} : blank);
  const [id, setId] = useState(post?.id ?? null);
  const [status, setStatus] = useState(post?.status ?? 'draft');
  const set = (k: keyof typeof blank) => (e: {target: {value: string}}) => setV({...v, [k]: e.target.value});
  const payload = () => ({slug: v.slug.trim().toLowerCase(), title: v.title, excerpt: v.excerpt, body: v.body, category: v.category,
    tags: v.tags.split(/[,،]/).map(t => t.trim()).filter(Boolean), cover: v.cover, cover_alt: v.cover_alt});
  async function save(): Promise<string | null> {
    try {const r = await (id ? api.put<Post>(`/blog/posts/${id}`, payload()) : api.post<Post>('/blog/posts', payload())); setId(r.id); setStatus(r.status); return r.id;}
    catch (x) {done({ok: false, text: errorOf(x).message}); return null;}
  }
  async function act(kind: 'save' | 'publish' | 'unpublish') {
    const pid = await save(); if (!pid) return;
    try {
      if (kind === 'publish') {await api.post(`/blog/posts/${pid}/publish`, {}); setStatus('published'); done({ok: true, text: 'مطلب روی سایت منتشر شد.'});}
      else if (kind === 'unpublish') {await api.post(`/blog/posts/${pid}/unpublish`, {}); setStatus('draft'); done({ok: true, text: 'مطلب از سایت برداشته شد و پیش‌نویس ماند.'});}
      else done({ok: true, text: status === 'published' ? 'تغییرات ذخیره شد و روی سایت است.' : 'پیش‌نویس ذخیره شد؛ تا انتشار روی سایت نمی‌آید.'});
    } catch (x) {done({ok: false, text: errorOf(x).message});}
  }
  return <div className="cms-editor blog-editor">
    <p className="cms-state">{status === 'published' ? 'منتشرشده' : 'پیش‌نویس'}</p>
    <label>عنوان<input value={v.title} maxLength={160} onChange={set('title')}/></label>
    <label>نامک (آدرس صفحه، لاتین)<input dir="ltr" value={v.slug} maxLength={120} placeholder="shiraz-travel-guide" onChange={set('slug')}/></label>
    <label>دسته<select value={v.category} onChange={set('category')}>{CATS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
    <label>خلاصه (برای کارت و گوگل)<textarea rows={2} value={v.excerpt} maxLength={300} onChange={set('excerpt')}/></label>
    <label>متن مطلب<textarea rows={16} value={v.body} onChange={set('body')}/></label>
    <p className="pn-muted">بین پاراگراف‌ها یک خط خالی بگذارید. «## » در اول خط = زیرعنوان، «- » = فهرست. قیمت و درصد تخفیف ننویسید.</p>
    <label>برچسب‌ها (با ویرگول جدا کنید)<input value={v.tags} onChange={set('tags')}/></label>
    <label>تصویر شاخص<select value={v.cover} onChange={set('cover')}><option value="">بدون تصویر</option>
      {v.cover && !v.cover.startsWith('media:') && <option value={v.cover}>تصویر فعلی</option>}
      {media.map(m => <option key={m.id} value={m.ref}>{m.alt || m.filename}</option>)}</select></label>
    {/* eslint-disable-next-line @next/next/no-img-element */}
    {v.cover && <img className="blog-editor-cover" src={blogImage(v.cover)} alt=""/>}
    <label>توضیح تصویر<input value={v.cover_alt} maxLength={160} onChange={set('cover_alt')}/></label>
    <p className="pn-muted">تصویر را اول در «محتوای سایت ← کتابخانه‌ی رسانه» بارگذاری کنید.</p>
    <div className="cms-actions">
      <button className="pn-btn ghost" type="button" onClick={() => void act('save')}>ذخیره</button>
      {status !== 'published' && <button className="pn-btn" type="button" onClick={() => void act('publish')}>انتشار روی سایت</button>}
      {status === 'published' && <button className="pn-btn ghost" type="button" onClick={() => void act('unpublish')}>برداشتن از سایت</button>}
      {status === 'published' && v.slug && <a className="pn-btn ghost" href={`/blog/${v.slug}`} target="_blank" rel="noreferrer">دیدن مطلب</a>}
      <button className="pn-btn ghost" type="button" onClick={close}>بازگشت به فهرست</button>
    </div>
  </div>;
}

export function BlogManager() {
  const posts = useLoad<{items: Post[]}>('/blog/posts');
  const media = useLoad<{items: Media[]}>('/cms/media');
  const {api} = useLoad<unknown>(null);
  const [open, setOpen] = useState<Post | null | 'new'>(null);
  const [msg, setMsg] = useState<Msg>(null);
  const lib = media.state.kind === 'ready' ? media.state.data.items : [];
  const done = (m: Msg) => {setMsg(m); posts.reload();};
  async function edit(p: Post) {try {setOpen(await api.get<Post>(`/blog/posts/${p.id}`)); setMsg(null);} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <>
    {msg && <p className={`pn-note${msg.ok ? '' : ' error'}`} role={msg.ok ? 'status' : 'alert'}>{msg.text}</p>}
    {open ? <Card title={open === 'new' ? 'مطلب تازه' : open.title}><Editor key={open === 'new' ? 'new' : open.id} post={open === 'new' ? null : open} media={lib} done={done} close={() => setOpen(null)}/></Card>
      : <Card title="مطالب وبلاگ">
        <div className="cms-actions"><button className="pn-btn" type="button" onClick={() => {setOpen('new'); setMsg(null);}}>نوشتن مطلب تازه</button>
          <a className="pn-btn ghost" href="/blog" target="_blank" rel="noreferrer">دیدن وبلاگ</a></div>
        <Async state={posts.state}>{d => d.items.length === 0 ? <p className="pn-muted">هنوز مطلبی نوشته نشده است.</p>
          : <ul className="blog-admin-list">{d.items.map(p => <li key={p.id}><button type="button" onClick={() => void edit(p)}>
            <b>{p.title}</b><small>{p.category_label} · {p.status === 'published' ? `منتشرشده ${p.published_at ? dateFa(p.published_at) : ''}` : 'پیش‌نویس'}</small></button></li>)}</ul>}</Async>
        {posts.state.kind === 'ready' && <p className="pn-muted">{fa(posts.state.data.items.filter(p => p.status === 'published').length)} مطلب منتشرشده</p>}
      </Card>}
  </>;
}
