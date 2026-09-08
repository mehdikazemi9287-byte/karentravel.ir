// No favicon is configured. Avoid a browser-generated 404 without inventing a brand asset.
export function GET() {
  return new Response(null, { status: 204 });
}
