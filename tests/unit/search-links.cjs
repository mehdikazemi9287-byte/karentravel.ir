// QA 2026-11-28 items 4-6 (and 3): login returns to the page, the assistant opens the results page, multi-city is
// disabled without moving the visitor, results run one search per submit, /admin/commerce reads /enterprise/organizations.
// Run: node tests/unit/search-links.cjs
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const out=ts.transpileModule(fs.readFileSync('lib/search-links.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const scope={exports:{},URLSearchParams,Date};vm.runInNewContext(out,scope);const L=scope.exports;
// 5: login link
assert.equal(L.loginHref('/account/bookings/abc'),'/login?redirect=%2Faccount%2Fbookings%2Fabc');
assert.equal(L.loginHref('/account/bookings/abc','?tab=docs'),'/login?redirect='+encodeURIComponent('/account/bookings/abc?tab=docs'));
assert.equal(L.loginHref('',''),'/login?redirect=%2F');
// 6: smart assistant -> results page, never the homepage
const q=href=>Object.fromEntries(new URLSearchParams(href.split('?')[1]));
const hotel=L.nlSearchHref({raw:'',vertical:'hotel',destination:'شیراز',depart:'2026-12-10',nights:3,adults:2,budgetMax:50000000,missing:[]},{depart:'',adults:1});
assert.ok(hotel.startsWith('/search/results?'));assert.equal(q(hotel).return,'2026-12-13');assert.equal(q(hotel).max_price,'50000000');assert.equal(q(hotel).adults,'2');
assert.ok(!('filters_max_price' in q(hotel))&&!('trip_type' in q(hotel)));
const flight=L.nlSearchHref({raw:'',vertical:'flight',origin:'تهران',destination:'مشهد',missing:[]},{depart:'2026-12-01',adults:1});
assert.ok(flight.startsWith('/search/results?'));assert.equal(q(flight).trip_type,'one_way');assert.equal(q(flight).depart,'2026-12-01');assert.ok(!('return' in q(flight)));
assert.ok(L.nlSearchHref({raw:'',vertical:'train',destination:'مشهد',missing:[]},{depart:'2026-12-01',adults:1}).startsWith('/trains/request?'));
// 6: multi-city is disabled with «به‌زودی» and no longer navigates or resets the form
const home=fs.readFileSync('components/search/HomeSearchExperience.tsx','utf8');
assert.ok(!home.includes("trip_type=multi_city&edit=1"),'multi-city must not navigate');
assert.ok(home.includes("option!=='multi_city'")&&home.includes('(به‌زودی)'));
assert.ok(!/router\.push\(`\/\?\$\{params/.test(home),'assistant must not go to the homepage');
const usv=fs.readFileSync('components/operational/UnifiedSearchView.tsx','utf8');
assert.ok(usv.includes('<option value="multi_city" disabled>'));
// 4: the search effect depends on the URL criteria only, and execute() never on the editable form state
assert.ok(/useEffect\(\(\)=>\{if\(!ready\)return;[^\n]*execute\(initial\)[^\n]*\[execute,initial,ready\]\)/.test(usv));
assert.ok(usv.includes('},[api,session]);'),'execute must not depend on form fields');
assert.ok(/function submit\([^\n]*commit\(current\(\)\)\}/.test(usv)&&!/function submit\([^\n]*void execute/.test(usv));
// 3: commerce panel uses the real endpoint
const cp=fs.readFileSync('components/panel/CommercePanel.tsx','utf8');
assert.ok(cp.includes("useLoad<Row[]>('/enterprise/organizations')")&&!cp.includes("useLoad<Row[]>('/organizations')"));
console.log('PASS search-links: login redirect, assistant to results, multi-city disabled, submit-only search, commerce orgs endpoint');
