import re,sys
M={'surface':'#1A0D1F','background':'#1A0D1F','surface-bright':'#2A1530','surface-dim':'#140A18','surface-container-lowest':'#140A18','surface-container-low':'#21122A','surface-container':'#2A1530','surface-container-high':'#32193A','surface-container-highest':'#3A2142','surface-variant':'#3A2142','on-surface':'#F5EEE4','on-background':'#F5EEE4','on-surface-variant':'#C7B6C1','outline':'#9C8796','outline-variant':'#4A3052','inverse-surface':'#F5EEE4','inverse-on-surface':'#2A1530','primary':'#F26A4D','primary-container':'#EF5B3D','secondary':'#DCBCE0','tertiary':'#EFB448','tertiary-container':'#EFB448','on-tertiary-container':'#2A1530'}
for f in sys.argv[1:]:
    s=open(f,encoding='utf-8').read();n=0
    for k,v in M.items():
        s,c=re.subn(r'("%s"\s*:\s*")#[0-9a-fA-F]{6}(")'%re.escape(k),r'\g<1>%s\g<2>'%v,s);n+=c
    s=s.replace('<html dir="rtl"','<html class="dark" dir="rtl"',1).replace('bg-white','bg-surface-container-lowest')
    open(f,'w',encoding='utf-8').write(s);print(f,n)
