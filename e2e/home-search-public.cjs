const {chromium,expect}=require('@playwright/test');
const fs=require('fs');const path=require('path');const assert=require('node:assert/strict');
const base=process.argv[2];const out=process.argv[3];const stage=process.argv[4]||'verification';
if(!base||!out)throw new Error('Usage: node e2e/home-search-public.cjs URL EVIDENCE_DIR STAGE');
const day=(offset)=>{const d=new Date();d.setDate(d.getDate()+offset);return d.toISOString().slice(0,10)};
async function visibleAndClickable(locator){
 await locator.scrollIntoViewIfNeeded();
 return locator.evaluate(el=>{const b=el.getBoundingClientRect();const hit=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return {visible:b.x>=0&&b.y>=0&&b.right<=innerWidth+1&&b.bottom<=innerHeight+1,clickable:hit===el||el.contains(hit),x:b.x,y:b.y,width:b.width,height:b.height}});
}
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{
  for(const width of [1440,768,430,390]){
   const context=await browser.newContext({viewport:{width,height:900},locale:'fa-IR'});
   const page=await context.newPage();page.setDefaultTimeout(10000);
   const errors=[],failed=[],searches=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
   page.on('requestfailed',r=>{if(r.failure()?.errorText!=='net::ERR_ABORTED')failed.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText})});
   page.on('response',r=>{if(r.status()>=400)failed.push({path:new URL(r.url()).pathname,status:r.status()})});
   page.on('request',r=>{if(new URL(r.url()).pathname==='/search/v2/public')searches.push(r.postDataJSON())});
   await page.goto(base+'/',{waitUntil:'networkidle'});
   await expect(page.getByRole('tab',{name:'پرواز',exact:true})).toHaveAttribute('aria-selected','true');
   await page.locator('#search').scrollIntoViewIfNeeded();
   await page.screenshot({path:path.join(out,stage+'-home-'+width+'.png')});
   const tabNames=['هتل','ویلا','تور','قطار','خودرو','کروز','ویزا','پرواز'];
   for(const name of tabNames){
    await page.getByRole('tab',{name,exact:true}).click();
    await expect(page.getByRole('tab',{name,exact:true})).toHaveAttribute('aria-selected','true');
    await expect(page.getByRole('tabpanel')).toHaveAttribute('aria-label','فرم جست‌وجوی '+name);
   }
   const origin=page.getByRole('combobox',{name:'مبدأ',exact:true});
   const destination=page.getByRole('combobox',{name:'مقصد',exact:true});
   await origin.click();await origin.fill('تهران');
   await page.getByRole('option').filter({has:page.locator('b').filter({hasText:/^تهران$/})}).first().click();
   await expect(origin).toHaveValue('تهران');
   // Regression: a single click must move from an open origin picker to destination.
   await origin.click();await destination.click();
   await expect(destination).toHaveAttribute('aria-expanded','true');
   await destination.fill('شیراز');
   await page.getByRole('option').filter({has:page.locator('b').filter({hasText:/^شیراز$/})}).first().click();
   await expect(destination).toHaveValue('شیراز');
   await expect(page.locator('.fs-scrim')).toHaveCount(0);
   if(width===1440){
    await page.locator('.fs-go').click();
    await expect(page.getByRole('alert')).toContainText('تاریخ');
    assert.equal(searches.length,0,'invalid dates must not request the API');
   }else await page.getByRole('button',{name:'تاریخ سفر',exact:true}).click();
   const depart=day(7),back=day(10);
   await page.getByLabel('تاریخ رفت',{exact:true}).fill(depart);
   await page.getByLabel('تاریخ برگشت',{exact:true}).fill(back);
   const dateDone=page.getByRole('button',{name:'تأیید تاریخ',exact:true});
   const dateGeometry=await visibleAndClickable(dateDone);
   assert.ok(dateGeometry.visible&&dateGeometry.clickable,'date confirmation must be visible and unobstructed');
   const panelBox=await page.locator('.fs-pop--date').boundingBox();
   assert.ok(panelBox.x>=0&&panelBox.x+panelBox.width<=width+1,'date picker must fit viewport');
   await page.screenshot({path:path.join(out,stage+'-date-'+width+'.png')});
   await dateDone.click();
   await page.locator('.fs-field--pax > button').click();
   await page.getByRole('button',{name:'افزایش بزرگسال',exact:true}).click();
   await page.getByRole('button',{name:'افزایش کودک',exact:true}).click();
   await page.getByRole('button',{name:'افزایش نوزاد',exact:true}).click();
   const paxDone=page.getByRole('button',{name:'تأیید مسافران',exact:true});
   const paxGeometry=await visibleAndClickable(paxDone);assert.ok(paxGeometry.visible&&paxGeometry.clickable);
   await paxDone.click();
   await expect(page.locator('.fs-field--pax > button')).toContainText('۵ مسافر');
   const responsePromise=page.waitForResponse(r=>new URL(r.url()).pathname==='/search/v2/public');
   await page.locator('.fs-go').click();
   const response=await responsePromise;assert.equal(response.status(),200);
   const data=await response.json();
   await expect(page).toHaveURL(/\/search\/results\?/);
   await expect(page.locator('h1')).toContainText('تهران');
   await expect(page.locator('h1')).toContainText('شیراز');
   await expect(page.locator('.zero-results,.search-results-list:not(:has(.result-skeleton))').first()).toBeVisible();
   await page.waitForLoadState('networkidle');
   assert.equal(searches.length,1,'one submission must make one Search request');
   const payload=searches[0];
   assert.deepEqual(payload.verticals,['flight']);assert.equal(payload.origin,'تهران');assert.equal(payload.destination,'شیراز');
   assert.equal(payload.travellers,5);assert.equal(payload.filters.depart,depart);assert.equal(payload.filters.return,back);
   assert.equal(payload.filters.adults,3);assert.equal(payload.filters.children,1);assert.equal(payload.filters.infants,1);
   assert.equal(data.structured_query.destination,'شیراز');assert.equal(data.structured_query.travellers,5);
   const params=new URL(page.url()).searchParams;
   assert.equal(params.get('depart'),depart);assert.equal(params.get('return'),back);assert.equal(params.get('children'),'1');
   await page.screenshot({path:path.join(out,stage+'-results-'+width+'.png')});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'results must not overflow horizontally');
   assert.deepEqual(errors,[],'console errors');assert.deepEqual(failed,[],'failed network requests');
   results.push({width,tabs:8,origin:'تهران',destination:'شیراز',dateGeometry,paxGeometry,request:payload,route:new URL(page.url()).pathname,http:response.status(),count:data.pagination.total,providers:data.provider_diagnostics,consoleErrors:errors,networkErrors:failed});
   await context.close();
  }
  fs.writeFileSync(path.join(out,stage+'-browser.json'),JSON.stringify(results,null,2));
  console.log(JSON.stringify({stage,verifiedWidths:results.map(x=>x.width),results:results.map(x=>({width:x.width,http:x.http,count:x.count,requests:1,route:x.route,consoleErrors:x.consoleErrors,networkErrors:x.networkErrors}))}));
 }catch(e){fs.writeFileSync(path.join(out,stage+'-failure.txt'),e.stack);throw e}
 finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
