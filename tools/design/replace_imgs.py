import re,glob,collections,html,sys
rules=[(r'یزد|yazd','hero-yazd.png'),(r'قشم|کیش|هرمز|qeshm|kish|hormuz','trip-qeshm.jpeg'),(r'گیلان|شمال|هیرکانی|gilan|north|mazandaran','trip-north.jpeg')]
stats=collections.Counter()
def pick(alt):
    a=alt.lower()
    if re.search(r'^profile$|avatar|user photo|portrait|پروفایل|کاربر|مسافر',a): return 'assets/avatar.svg','avatar'
    if not re.search(r'hotel|هتل|room|اتاق|lobby|لابی|suite|spa|pool|استخر|restaurant|رستوران|breakfast|صبحانه|radisson|istanbul|استانبول|bosphorus|بسفر|taxi|تاکسی|lounge|غذا|meal',a):
        for pat,img in rules:
            if re.search(pat,a): return 'assets/'+img,'owned'
        if re.search(r'شیراز پایتخت شعر|eram|حافظیه',a): return 'assets/trip-shiraz.jpeg','owned'
    return 'assets/placeholder.svg','placeholder'
for f in sys.argv[1:]:
    pre='../' if '/' in f else ''
    s=open(f,encoding='utf-8').read()
    def rep(m):
        tag=m.group(0)
        if 'googleusercontent' not in tag: return tag
        alt=html.unescape((re.search(r'(?:data-alt|alt)="([^"]*)"',tag) or [None,''])[1])
        src,k=pick(alt);stats[k]+=1
        return re.sub(r'src="https://lh3[^"]*"','src="'+pre+src+'"',tag)
    s=re.sub(r'<img[^>]*>',rep,s)
    s,n=re.subn(r"url\((['\"]?)https://lh3[^)'\"]+\1\)","url('"+pre+"assets/placeholder.svg')",s);stats['bg']+=n
    open(f,'w',encoding='utf-8').write(s)
print(stats)
