// Personal vs organization panel by membership (lib/panel-context.ts). Run: node tests/unit/panel-context.cjs
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const src=ts.transpileModule(fs.readFileSync('lib/panel-context.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const scope={exports:{},require};scope.module={exports:scope.exports};vm.runInNewContext(src,scope);const C=scope.exports;
const plain=JSON.parse.bind(JSON),j=x=>plain(JSON.stringify(x));
const employee=[{id:'o1',name:'شرکت الف',permissions:[]}];
const manager=[{id:'o1',name:'شرکت الف',permissions:['requests.read_all']}];
const hr=[{id:'o2',name:'شرکت ب',permissions:['benefits.manage']}];
// no membership: nothing opens by membership, no switcher for a plain customer
assert.equal(C.orgAllows('/employee',[]),false);assert.deepEqual(j(C.panelContextsFor(null,[])),[]);
// plain member: employee desk, own requests and policy; never org-wide records or members
for(const p of ['/employee','/organization/requests','/organization/policy'])assert.equal(C.orgAllows(p,employee),true,p);
for(const p of ['/organization','/organization/reports','/organization/billing','/organization/credit','/organization/audit','/organization/bookings','/organization/members'])assert.equal(C.orgAllows(p,employee),false,p);
// role-only pages never open by membership
for(const p of ['/organization/structure','/organization/passengers','/organization/financial-context'])assert.equal(C.orgAllows(p,manager),false,p);
// records permission opens the overview and records; members needs its own permissions
assert.equal(C.orgAllows('/organization/billing',manager),true);assert.equal(C.orgAllows('/organization/members',manager),false);
assert.equal(C.orgAllows('/organization/members',hr),true);assert.equal(C.orgAllows('/organization/audit',hr),false);
// detail pages follow their parent; trailing slash ignored
assert.equal(C.orgAllows('/organization/requests/abc',employee),true);assert.equal(C.orgAllows('/organization/billing/',manager),true);
// homes and switcher
assert.equal(C.orgHomeFor(employee),'/employee');assert.equal(C.orgHomeFor(manager),'/organization');assert.equal(C.orgHomeFor([]),null);
assert.deepEqual(j(C.panelContextsFor(null,employee)).map(c=>[c.kind,c.href]),[['personal','/account'],['organization','/employee']]);
assert.equal(j(C.panelContextsFor(null,employee))[1].label,'پنل سازمان: شرکت الف');
assert.equal(j(C.panelContextsFor(null,[...employee,...hr]))[1].label,'پنل سازمان');
// global organization role without a membership row still gets the switcher to its role home
assert.deepEqual(j(C.panelContextsFor('/organization',[])).map(c=>c.href),['/account','/organization']);
assert.deepEqual(j(C.orgPagesFor(employee)),['/employee','/organization/requests','/organization/policy']);
console.log('panel-context: PASS');
