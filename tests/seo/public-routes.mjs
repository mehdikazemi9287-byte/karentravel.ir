// Public, indexable pages of karentravel.ir that render without a database row.
// `sitemap: false` = public but intentionally not listed (none today). Detail pages (/tours/<id>, /blog/<slug>,
// /destinations/<slug>, /hotels/<slug>, …) come from the API and are checked through the sitemap when it lists them.
export const PUBLIC_ROUTES = [
  '/', '/flights', '/trains', '/hotels', '/tours', '/tours/last-minute', '/tours/nowruz', '/tours/installment', '/tours/special',
  '/destinations', '/experiences', '/blog', '/travel-guides', '/visa', '/car-rental', '/villas',
  '/restaurants', '/attractions', '/events-venues', '/pools-sports', '/handicrafts', '/souvenirs', '/tourist-transport', '/festival',
  '/services', '/solutions', '/faq', '/contact', '/about', '/support', '/privacy', '/terms', '/refund-policy', '/itineraries', '/white-label', '/integrations',
].map(path => ({path}));
