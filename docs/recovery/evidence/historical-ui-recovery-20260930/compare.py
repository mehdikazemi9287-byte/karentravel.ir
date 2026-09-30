from PIL import Image,ImageDraw
import json
from pathlib import Path
p=Path('/images');data=json.loads((p/'visual.json').read_text())
for w in [1366,1440,1536,1920,360,390,430]:
 col=500 if w>700 else w
 pieces=[]
 for n in ['76bea5c','d2ba674','candidate']:
  r=next(x for x in data if x['version']==n and x['width']==w);im=Image.open(p/f'{n}-{w}.png').convert('RGB');blocks=[]
  for label,box in [('TOP',(0,0,w,min(1450,im.height))),('DESTINATIONS',(0,max(0,int(r['mosaic']['y'])-100),w,min(im.height,int(r['mosaic']['y']+r['mosaic']['height'])+80))),('FOOTER',(0,max(0,int(r['footer']['y'])-60),w,im.height))]:
   if label=='DESTINATIONS':
    crop=Image.open(p/f'mosaic-{n}-{w}.jpg').convert('RGB')
   elif label=='FOOTER':
    section=p/f'footer-{n}-{w}.jpg'
    if section.exists():crop=Image.open(section).convert('RGB')
    else:
     crop=Image.new('RGB',(col,90),'white');ImageDraw.Draw(crop).text((12,30),'Footer hidden at this viewport',fill='black')
   else:crop=im.crop(box)
   crop=crop.resize((col,round(crop.height*col/crop.width)));blocks.append((label,crop))
  c=Image.new('RGB',(col,sum(z.height+26 for _,z in blocks)+32),'white');d=ImageDraw.Draw(c);d.text((10,8),f'{n} / {w}px',fill='black');y=32
  for label,img in blocks:d.text((8,y+3),label,fill='black');c.paste(img,(0,y+26));y+=img.height+26
  pieces.append(c)
 out=Image.new('RGB',(col*3,max(x.height for x in pieces)),'#dddddd')
 for i,img in enumerate(pieces):out.paste(img,(i*col,0))
 out.save(p/f'comparison-{w}.png')
