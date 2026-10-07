import sys
lines=[l.split() for l in open(sys.argv[1]) if l.startswith('PANEL')]
screens=[]; cur=''; t0=None
for _,t,h in lines:
    b=int(h,16)
    if b==0x66:
        if cur: screens.append((t0,cur))
        cur=''; t0=t; continue
    if t0 is None: t0=t
    cur+= chr(b) if 0x20<=b<0x60 else f'<{b:02x}>'
screens.append((t0,cur))
prev=None; n=0
for t,s in screens:
    if s!=prev:
        print(f'{float(t):7.2f}s  {s!r}'); n+=1
        if n>40: break
    prev=s
