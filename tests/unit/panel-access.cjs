// Role-filtered panel navigation and route guard (lib/panel-access.ts). Run: node tests/unit/panel-access.cjs
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const src=ts.transpileModule(fs.readFileSync('lib/panel-access.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
const scope={exports:{},require:p=>p.endsWith('.json')?JSON.parse(fs.readFileSync(path.join('lib',p),'utf8')):require(p)};scope.module={exports:scope.exports};
vm.runInNewContext(src,scope);const A=scope.exports;
const hrefs=(area,role)=>JSON.parse(JSON.stringify(A.navFor(area,role).map(i=>i.href)));
// staff pages are split into three areas (ops / finance / admin); a role's staff menu is the union of the areas it can open
const staffHrefs=role=>[...new Set(['ops','finance','admin'].flatMap(a=>hrefs(a,role)))];
assert.equal(staffHrefs('platform_admin').length,48);
const bo=staffHrefs('backoffice_expert'),fin=staffHrefs('finance_operator'),ta=staffHrefs('tenant_admin');
assert.ok(bo.includes('/admin/ops')&&bo.includes('/backoffice')&&bo.includes('/admin/catalog'));
assert.ok(!bo.includes('/finance/ledger')&&!bo.includes('/finance')&&!bo.includes('/admin')&&!bo.includes('/admin/tenants'));
assert.ok(fin.includes('/finance')&&fin.includes('/finance/ledger')&&fin.includes('/admin/ops'));
assert.ok(!fin.includes('/admin/content')&&!fin.includes('/admin/sales-desk')&&!fin.includes('/backoffice'));
assert.ok(ta.includes('/admin')&&!ta.includes('/admin/tenants')&&!ta.includes('/admin/catalog'));
// Phase 1 rest: areas, «امروز», new pages, bottom nav
assert.equal(A.staffArea('/finance/refunds'),'finance');assert.equal(A.staffArea('/backoffice/agencies'),'ops');assert.equal(A.staffArea('/admin/ops'),'ops');assert.equal(A.staffArea('/admin/audit'),'admin');
assert.equal(A.areaFor('admin','/finance/refunds/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c'),'finance');assert.equal(A.areaFor('admin','/backoffice/requests/x'),'ops');assert.equal(A.areaFor('customer','/account'),'customer');
assert.ok(!hrefs('ops','finance_operator').includes('/backoffice/queues/service_requests')&&hrefs('finance','finance_operator')[0]==='/panel/today');
assert.deepEqual(JSON.parse(JSON.stringify(A.staffAreasFor('backoffice_expert').map(a=>a.area))).includes('finance'),bo.some(h=>A.staffArea(h)==='finance'));
assert.ok(fin.includes('/finance/failed-payments')&&fin.includes('/finance/settlement-import')&&fin.includes('/finance/bank-batches')&&fin.includes('/finance/approvals')&&fin.includes('/finance/tax-rates'));
assert.ok(bo.includes('/backoffice/price-changes')&&!bo.includes('/finance/bank-batches')&&!bo.includes('/admin/sla')&&ta.includes('/admin/sla'));
assert.equal(A.canOpen('customer','/panel/today','customer'),true);assert.equal(A.canOpen('admin','/finance/bank-batches','backoffice_expert'),false);
assert.equal(A.canOpen('customer','/account/price-changes','customer'),true);assert.equal(A.canOpen('organization','/organization/passengers','employee'),false);
assert.ok(hrefs('agency','agency_partner').includes('/agency/passengers')&&hrefs('organization','organization_admin').includes('/organization/passengers'));
for(const [area,role] of [['customer','customer'],['agency','agency_partner'],['ops','backoffice_expert'],['finance','finance_operator'],['admin','tenant_admin'],['organization','organization_admin'],['supplier','supplier']]){
  const t=A.mobileTabsFor(area,role);assert.ok(t.length>=2&&t.length<=4,`${area}:${t.length}`);for(const x of t)assert.ok(A.canOpen(area,x.href,role),`${area} tab ${x.href}`);}
assert.deepEqual(JSON.parse(JSON.stringify(A.mobileTabsFor('finance','finance_operator').map(t=>t.href))),['/panel/today','/finance/refunds','/finance/approvals','/finance/reconciliation']);
assert.ok(bo.length<25&&fin.length<28,`bo=${bo.length} fin=${fin.length}`);
// after-sales (Panels Phase 1): ops queue for back office only, refund queue and reconciliation for finance only
assert.ok(bo.includes('/backoffice/queues/service_requests')&&!bo.includes('/finance/refunds')&&!bo.includes('/finance/reconciliation'));
assert.ok(fin.includes('/finance/refunds')&&fin.includes('/finance/reconciliation')&&!fin.includes('/backoffice/queues/service_requests'));
assert.equal(A.canOpen('admin','/backoffice/requests/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','finance_operator'),false);
assert.equal(A.canOpen('admin','/backoffice/requests/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','backoffice_expert'),true);
assert.equal(A.canOpen('admin','/finance/refunds/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','backoffice_expert'),false);
assert.equal(A.canOpen('admin','/finance/refunds/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','finance_operator'),true);
assert.equal(A.canOpen('admin','/backoffice/queues/failed_issuance','finance_operator'),false);
assert.equal(A.canOpen('customer','/account/refunds/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','customer'),true);
// Panels Phase 2: agency sidebar groups and B2B/charter pages; staff review pages split between ops and finance
const ag=hrefs('agency','agency_partner');
for(const h of ['/agency/profile','/agency/credit','/agency/pricing','/agency/sell','/agency/invoices','/agency/users','/agency/inventory/flights'])assert.ok(ag.includes(h),h);
assert.ok(A.navFor('agency','agency_partner').filter(i=>i.group).length>=14);
assert.equal(A.canOpen('agency','/agency/inventory/flights/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','agency_partner'),true);
assert.equal(A.canOpen('agency','/agency/inventory/flights/new','supplier'),false);
assert.ok(bo.includes('/backoffice/agencies')&&bo.includes('/backoffice/charter-blocks')&&!bo.includes('/finance/agency-accounts'));
assert.ok(fin.includes('/finance/agency-accounts')&&fin.includes('/backoffice/agencies')&&!fin.includes('/backoffice/charter-blocks'));
assert.equal(A.canOpen('admin','/backoffice/agencies','agency_partner'),false);
assert.equal(A.canOpen('admin','/finance/agency-accounts','backoffice_expert'),false);
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
// Phase 2b: periodic agency settlement, disputes queue and charter notices
assert.ok(fin.includes('/finance/settlements/agencies')&&fin.includes('/finance/settlements/disputes')&&!bo.includes('/finance/settlements/agencies'));
assert.equal(A.canOpen('admin','/finance/settlements/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','backoffice_expert'),false);
assert.equal(A.canOpen('admin','/finance/settlements/0b5c1f4e-6a1d-4c3e-9f2a-1d2e3f4a5b6c','finance_operator'),true);
assert.equal(A.canOpen('admin','/finance/refunds/agency-credit/x','finance_operator'),true);assert.equal(A.canOpen('admin','/finance/refunds/agency-credit/x','backoffice_expert'),false);
assert.equal(A.canOpen('admin','/backoffice/charter-blocks/x','backoffice_expert'),true);
assert.ok(hrefs('agency','agency_partner').includes('/agency/settlements')&&hrefs('agency','agency_partner').includes('/agency/inventory/notices'));
assert.equal(A.canOpen('agency','/agency/settlements/x','agency_partner'),true);assert.equal(A.canOpen('agency','/agency/settlements','customer'),false);
console.log('panel-access: PASS');
