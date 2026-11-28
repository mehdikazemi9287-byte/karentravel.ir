/* Blog data for the public pages. Server pages read the API directly (API_INTERNAL_URL inside the server network, or
   the public API URL); when that is not reachable the page falls back to loading in the browser. */
export type BlogSummary = {id: string; slug: string; title: string; excerpt: string; category: string; category_label: string; tags: string[];
  cover: string; cover_alt: string; published_at: string | null; updated_at: string | null; reading_minutes: number};
export type BlogPost = BlogSummary & {body: string; related: BlogSummary[]};
export type BlogList = {items: BlogSummary[]; total: number; page: number; pages: number; categories: {key: string; label: string}[]};

export const blogTenant = () => process.env.NEXT_PUBLIC_TENANT_SLUG || 'aftab-bank';
const publicBase = () => (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const serverBase = () => (process.env.API_INTERNAL_URL || publicBase()).replace(/\/$/, '');

export function blogPath(path: string, base = publicBase()): string {
  return `${base}/public/tenants/${encodeURIComponent(blogTenant())}${path}`;
}

/** `media:<id>` → public media URL; built-in site images are returned unchanged. */
export function blogImage(ref: string, base = publicBase()): string {
  return ref.startsWith('media:') ? blogPath(`/media/${ref.slice(6)}`, base) : ref;
}

/** Server-side read. `undefined` = API unreachable (render the browser fallback); `null` = not found. */
export async function serverBlog<T>(path: string): Promise<T | null | undefined> {
  try {
    const r = await fetch(blogPath(path, serverBase()), {signal: AbortSignal.timeout(5000), next: {revalidate: 60}});
    if (r.status === 404) return null;
    return r.ok ? ((await r.json()) as T) : undefined;
  } catch {return undefined;}
}

export type Block = {kind: 'p' | 'h' | 'ul'; text?: string; items?: string[]};
/** Plain-text body → paragraphs, "## " sub-headings and "- " bullet lists. No HTML is ever produced from the text. */
export function parseBody(body: string): Block[] {
  const out: Block[] = [];
  let para: string[] = [];
  let list: string[] | null = null;
  const flush = () => {
    if (para.length) {out.push({kind: 'p', text: para.join(' ')}); para = [];}
    if (list) {out.push({kind: 'ul', items: list}); list = null;}
  };
  for (const raw of body.split('\n')) {
    const line = raw.trim();
    if (!line) {flush(); continue;}
    if (line.startsWith('## ')) {flush(); out.push({kind: 'h', text: line.slice(3).trim()}); continue;}
    if (/^[-•]\s+/.test(line)) {if (para.length) {out.push({kind: 'p', text: para.join(' ')}); para = [];} (list ??= []).push(line.replace(/^[-•]\s+/, '')); continue;}
    if (list) {out.push({kind: 'ul', items: list}); list = null;}
    para.push(line);
  }
  flush();
  return out;
}

export type Inline = {text: string; href?: string};
/** Inline internal links «[متن](/path)» → text and site-path segments. Only same-site paths are linked
 *  (no scheme, no "//"); anything else stays plain text. Still no HTML is produced. */
export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  const re = /\[([^\]\n]{1,120})\]\((\/(?!\/)[A-Za-z0-9\-._~\/?=&#%]{0,200})\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({text: text.slice(last, m.index)});
    out.push({text: m[1], href: m[2]});
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({text: text.slice(last)});
  return out;
}

export const faDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('fa-IR', {timeZone: 'Asia/Tehran', year: 'numeric', month: 'long', day: 'numeric'}) : '');
