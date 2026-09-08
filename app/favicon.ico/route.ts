// Keep the unconfigured browser icon transparent; no brand asset is introduced.
export function GET() {
  return new Response('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>', {
    headers: { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=86400' },
  });
}
