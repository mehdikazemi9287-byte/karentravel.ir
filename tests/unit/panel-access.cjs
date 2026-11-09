// Role-filtered panel navigation and route guard (lib/panel-access.ts). Run: node tests/unit/panel-access.cjs
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const src=ts.transpileModule(fs.readFileSync('lib/panel-access.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
const scope={exports:{},require:p=>p.endsWith('.json')?JSON.parse(fs.readFileSync(path.join('lib',p),'utf8')):require(p)};scope.module={exports:scope.exports};
vm.runInNewContext(src,scope);const A=scope.exports;
const hrefs=(area,role)=>JSON.parse(JSON.stringify(A.navFor(area,role).map(i=>i.href)));
// admin area: 31 links for platform admin, far fewer for back office and finance, none of the other's tools
assert.equal(hrefs('admin','platform_admin').length,34);
const bo=hrefs('admin','backoffice_expert'),fin=hrefs('admin','finance_operator'),ta=hrefs('admin','tenant_admin');
assert.ok(bo.includes('/admin/ops')&&bo.includes('/backoffice')&&bo.includes('/admin/catalog'));
assert.ok(!bo.includes('/finance/ledger')&&!bo.includes('/finance')&&!bo.includes('/admin')&&!bo.includes('/admin/tenants'));
assert.ok(fin.includes('/finance')&&fin.includes('/finance/ledger')&&fin.includes('/admin/ops'));
assert.ok(!fin.includes('/admin/content')&&!fin.includes('/admin/sales-desk')&&!fin.includes('/backoffice'));
assert.ok(ta.includes('/admin')&&!ta.includes('/admin/tenants')&&!ta.includes('/admin/catalog'));
assert.ok(bo.length<20&&fin.length<20,`bo=${bo.length} fin=${fin.length}`);
// after-sales (Panels Phase 1): ops queue for back office only, refund queue and reconciliation for finance only
assert.ok(bo.includes('/backoffice/queues/service_requests')&&!bo.includes('/finance/refunds')&&!bo.includes('/finance/reconciliation'));
assert.ok(fin.includes('/finance/refunds')&&fin.includes('/finance/reconciliation')&&!fin.includes('/backoffice/queues/service_requests'));
assert.equal(A.canOpen('admin','/backoffice/requests/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','finance_operator'),false);
assert.equal(A.canOpen('admin','/backoffice/requests/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','backoffice_expert'),true);
assert.equal(A.canOpen('admin','/finance/refunds/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','backoffice_expert'),false);
assert.equal(A.canOpen('admin','/finance/refunds/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','finance_operator'),true);
assert.equal(A.canOpen('admin','/backoffice/queues/failed_issuance','finance_operator'),false);
assert.equal(A.canOpen('customer','/account/refunds/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','customer'),true);
// guard
assert.equal(A.canOpen('admin','/finance/ledger','backoffice_expert'),false);
assert.equal(A.canOpen('admin','/finance/ledger','finance_operator'),true);
assert.equal(A.canOpen('admin','/admin/tenants','tenant_admin'),false);
assert.equal(A.canOpen('admin','/admin/ops','customer'),false);
assert.equal(A.canOpen('admin','/backoffice/unknown-page','customer'),false);   // area fallback
assert.equal(A.canOpen('customer','/account/bookings','supplier'),true);
// agency: own tours in agency nav; supplier pages not for agency users, with a pointer to the agency page
assert.ok(hrefs('agency','agency_partner').includes('/agency/tours'));
assert.equal(A.canOpen('agency','/agency/tours','agency_partner'),true);
assert.equal(A.canOpen('agency','/agency/tours','supplier'),false);
assert.equal(A.canOpen('supplier','/supplier/tours','agency_partner'),false);
assert.equal(A.itemFor('supplier','/supplier/tours').moved.agency_partner,'/agency/tours');
assert.deepEqual(hrefs('supplier','agency_partner'),['/supplier/admission']);
assert.equal(A.canOpen('supplier','/supplier/offers/new','supplier'),true);
// organization: employees see their own desk and requests, not the admin pages
assert.deepEqual(hrefs('organization','employee'),['/employee','/organization/requests']);
assert.equal(A.canOpen('organization','/organization/members','employee'),false);
// account menu follows the same registry
const agencyMenu=A.roleLinks('agency_partner').map(x=>x[1]);
assert.ok(agencyMenu.includes('/agency/tours')&&!agencyMenu.includes('/supplier/tours')&&agencyMenu.includes('/agency'));
assert.ok(!A.roleLinks('backoffice_expert').map(x=>x[1]).includes('/finance/ledger'));
assert.ok(A.roleLinks('customer').map(x=>x[1]).includes('/quotes'));
// every registered page exists in the app router
for(const i of A.PANEL_ITEMS){const f=path.join('app',i.href,'page.tsx');assert.ok(fs.existsSync(f),`missing page for ${i.href}`);}
assert.equal(A.homeFor('agency_partner'),'/agency');assert.equal(A.homeFor('nobody'),'/account');
console.log('PASS panel nav is role-filtered, guard denies other roles, agency tours live in the agency panel');
