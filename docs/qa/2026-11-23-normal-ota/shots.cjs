// QA-only screenshot harness. Catalog responses are Mock fixtures (local DB has no catalog import).
const {chromium}=require('playwright');
const fs=require('fs');
const phase=process.argv[2]||'before'; const only=process.argv[3]; const out=`${process.env.OUT_DIR||'/tmp/nota/shots'}/${phase}`; fs.mkdirSync(out,{recursive:true});
const W=process.env.WEB_URL||'http://127.0.0.1:3150';
const day=new Date(Date.now()+2*86400000).toISOString().slice(0,10);
const city=(id,name,img)=>({id,kind:'city',parent_id:null,country_code:'IR',name,name_fa:name,name_en:null,latitude:null,longitude:null,population:null,description:null,image_url:img,image_credit:null,hotel_count:3});
const places={items:[city('c1','مشهد','/images/approved-figma/refTripNorth.jpg'),city('c2','کیش','/images/approved-figma/refTripQeshm.jpg'),city('c3','تبریز','/images/approved-figma/imgTileMasuleh.jpg'),city('c4','قشم','/images/approved-figma/imgTileQeshm.jpg'),city('c5','رشت','/images/approved-figma/imgTileMasuleh.jpg'),city('c6','اهواز','/images/approved-figma/imgImage.jpg'),city('c7','کرمان','/images/approved-figma/imgImage1.jpg')]};
const al=(iata,name_fa,name_en)=>({id:'Q'+iata,iata,icao:null,name:name_fa||name_en,name_fa,name_en,country_code:'IR',airline_type:'airline',website:null,logo_url:null,logo_credit:null});
const airlines={items:[al('HH',null,'Taban Air'),al('RV','هواپیمایی کاسپین','Caspian Airlines'),al('PR',null,'Pars Air'),al('VR',null,'Varesh Airlines'),al('IS',null,'Sepehran Airlines'),al('2F',null,'Mock airline 2F'),al('W5','ماهان','Mahan Air'),al('Y9',null,'Kish Air')]};
const hotel=(i,name,img)=>({id:'h'+i,slug:'mock-'+i,name,name_fa:name,name_en:null,name_local:null,hotel_type:'hotel',hotel_type_fa:'هتل',stars:4,country_code:'IR',city:{id:'c1',name:'مشهد'},region:{id:'r1',name:'خراسان رضوی'},address:null,latitude:null,longitude:null,amenities:[{key:'wifi',label:'اینترنت'},{key:'parking',label:'پارکینگ'}],image_url:img,image_credit:'Mock Author, CC BY-SA 4.0, via Wikimedia Commons',price_note:'قیمت پس از انتخاب تاریخ و استعلام'});
const hotels={total:3,offset:0,limit:24,items:[hotel(1,'هتل نمونهٔ Mock یک','/images/approved-figma/imgThumb.jpg'),hotel(2,'هتل نمونهٔ Mock دو','/images/approved-figma/imgThumb1.jpg'),hotel(3,'هتل نمونهٔ Mock سه','/images/approved-figma/imgThumb2.jpg')],price_note:'قیمت پس از انتخاب تاریخ و استعلام'};
const facets={countries:[{code:'IR',name:'ایران',count:3}],cities:[{id:'c1',name:'مشهد',count:3}],stars:[{value:4,count:3}],types:[{key:'hotel',label:'هتل',count:3}],amenities:[]};
const tour=(i,title,dest,img)=>({id:'t'+i,slug:'t'+i,href:'/tours/t'+i,categories:[],title,destination:{id:'d'+i,name:dest},duration_nights:3,duration_days:4,transport_fa:'هوایی',image_url:img,image_credit:null});
const tours={total:3,items:[tour(1,'تور مشهد (Mock)','مشهد','/mock-img/mashhad.jpg'),tour(2,'تور تبریز (Mock)','تبریز','/mock-img/tabriz.jpg'),tour(3,'تور کیش (Mock)','کیش','/mock-img/kish.jpg')],destinations:[],categories:[],years:[]};
async function mock(page){
  await page.route('**/mock-img/*',r=>r.fulfill({path:(process.env.FX_DIR||'/tmp/nota/fx')+'/'+r.request().url().split('/').pop(),contentType:'image/jpeg'}));
  await page.route(/127\.0\.0\.1:\d+\/catalog\//,r=>{const u=new URL(r.request().url());const p=u.pathname;
    if(p==='/catalog/places')return r.fulfill({json:places});
    if(p==='/catalog/airlines')return r.fulfill({json:airlines});
    if(p==='/catalog/hotels/facets')return r.fulfill({json:facets});
    if(p==='/catalog/hotels')return r.fulfill({json:hotels});
    if(p==='/catalog/tours')return r.fulfill({json:tours});
    return r.continue();});
}
const pages=[['home','/'],['flights','/flights'],['flight-results',`/search/results?vertical=flight&origin=${encodeURIComponent('تهران')}&destination=${encodeURIComponent('شیراز')}&depart=${day}&adults=1&trip_type=one_way&sort=recommended`],['hotels','/hotels'],['trains','/trains'],['tours','/tours'],['login','/login'],['support','/support']];
(async()=>{const b=await chromium.launch({channel:'chrome',args:['--no-sandbox']});
  for(const [w,h,tag] of [[1440,900,'1440'],[390,844,'390']]){
    const ctx=await b.newContext({viewport:{width:w,height:h},locale:'fa-IR'});const page=await ctx.newPage();await mock(page);
    for(const [name,url] of pages){ if(only&&!only.split(',').includes(name))continue;
      try{await page.goto(W+url,{waitUntil:'networkidle',timeout:60000});}catch(e){console.log('nav',name,e.message.split('\n')[0])}
      await page.waitForTimeout(1500);
      await page.screenshot({path:`${out}/${name}-${tag}.png`,fullPage:true});
      if(name==='home'||name==='flights'){
        const btn=page.getByRole('button',{name:/^(پیدا کن|جست‌وجو)$/}).first();
        if(await btn.count()){await btn.click();await page.waitForTimeout(1500);await page.screenshot({path:`${out}/${name}-submit-${tag}.png`});
          await page.goto(W+url,{waitUntil:'networkidle'});await page.waitForTimeout(1000);}
        const o=page.getByRole('combobox',{name:/مبدا|مبدأ/}).first();
        if(await o.count()){await o.click();await o.fill('تهران');await page.waitForTimeout(1500);await page.screenshot({path:`${out}/${name}-origin-dropdown-${tag}.png`});}
      }
    }
    await ctx.close();}
  await b.close();})();
