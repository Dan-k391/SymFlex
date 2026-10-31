import re,sys,zipfile,html
for path,out in zip(sys.argv[1::2],sys.argv[2::2]):
    z=zipfile.ZipFile(path); x=z.read('word/document.xml').decode('utf8')
    rels=z.read('word/_rels/document.xml.rels').decode()
    rmap=dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"',rels))
    rmap.update({a:b for b,a in re.findall(r'Target="([^"]+)"[^>]*Id="(rId\d+)"',rels)})
    res=[]
    for p in re.findall(r'<w:p[ >].*?</w:p>',x,re.S):
        t=''
        for m in re.finditer(r'<w:t[^>]*>([^<]*)</w:t>|<w:tab/>|<w:br/>|r:(?:embed|id)="(rId\d+)"',p):
            if m.group(1) is not None: t+=html.unescape(m.group(1))
            elif m.group(2): t+=' [%s] '%rmap.get(m.group(2),m.group(2))
            elif 'tab' in m.group(0): t+='\t'
            else: t+='\n'
        res.append(t)
    open(out,'w',encoding='utf8').write('\n'.join(res))
