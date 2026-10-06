// Server-side SEO lookup for catalogue pages. Falls back silently: metadata must never break a page.
export async function catalogSeo(path: string): Promise<{title: string; description: string} | null> {
  const base = process.env.NEXT_PUBLIC_API_URL; if (!base) return null;
  try {
    const res = await fetch(`${base}${path}`, {signal: AbortSignal.timeout(2500), next: {revalidate: 600}});
    if (!res.ok) return null;
    const seo = (await res.json()).seo; return seo && typeof seo.title === 'string' ? {title: seo.title, description: String(seo.description ?? '')} : null;
  } catch {return null;}
}
