/* schema.org JSON-LD data block (not executed, so the CSP nonce is not needed). Server component: in the HTML without JS. */
export function JsonLd({data}: {data: object | object[]}) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(data).replace(/</g, '\\u003c')}}/>;
}
