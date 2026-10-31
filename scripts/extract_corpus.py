"""Extract Maple / FlexPDE code blocks from the course PDFs and lab .docx files.

Code in every source is set in Courier New, so blocks are found by font.
Writes corpus/raw/<source>/<nn>.{mpl,pde} plus corpus/raw/index.json.
Usage: python scripts/extract_corpus.py "D:/Maple/Course Content"
"""
import html, json, os, re, sys, zipfile
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'corpus', 'raw')

PDF_NAMES = {  # hashed filenames -> topic, from each PDF's first heading
    'bc6c5aa905f62d0877618b0324f235a3': 'notes1_kinematics',
    '3b4500f91479342ec85300a4c6d3b6b5': 'notes2_nonlinear',
    '3c8ee59aca1b42926048f9d1eafaf866': 'notes3_damped',
    '83cf0da792dec282396df1289846dcb5': 'notes4_rigidbody',
    '3e9fe007f0a8688b3d68361810605b44': 'notes5_energy_lagrange',
}


def is_pde(text):
    return bool(re.search(r'^\s*(VARIABLES|EQUATIONS|BOUNDARIES)\b', text, re.I | re.M))


def pdf_lines(path):
    """Yield (page, text, is_code) per visual line."""
    doc = pymupdf.open(path)
    for pno, page in enumerate(doc):
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                spans = [s for s in l['spans'] if s['text'].strip()]
                if not spans:
                    continue
                code = sum(len(s['text']) for s in spans if 'Courier' in s['font'])
                total = sum(len(s['text']) for s in spans)
                txt = ''.join(s['text'] for s in l['spans'])
                yield pno + 1, txt.rstrip(), code >= 0.6 * total


def docx_paras(path):
    """Yield (para_index, text, is_code, images) per paragraph."""
    z = zipfile.ZipFile(path)
    x = z.read('word/document.xml').decode('utf8')
    rels = z.read('word/_rels/document.xml.rels').decode()
    rmap = {}
    for m in re.finditer(r'<Relationship [^>]*>', rels):
        i = re.search(r'Id="([^"]+)"', m.group(0)); t = re.search(r'Target="([^"]+)"', m.group(0))
        if i and t:
            rmap[i.group(1)] = t.group(1)
    for idx, p in enumerate(re.findall(r'<w:p[ >].*?</w:p>', x, re.S)):
        txt, code, total, imgs = '', 0, 0, []
        for r in re.findall(r'<w:r[ >].*?</w:r>', p, re.S):
            courier = 'Courier' in r or 'Consolas' in r
            for m in re.finditer(r'<w:t[^>]*>([^<]*)</w:t>|<w:tab/>|<w:br/>|<v:imagedata r:id="(rId\d+)"|<a:blip r:embed="(rId\d+)"', r):
                if m.group(1) is not None:
                    s = html.unescape(m.group(1)); txt += s
                    total += len(s.strip()); code += len(s.strip()) if courier else 0
                elif m.group(2) or m.group(3):
                    imgs.append(rmap.get(m.group(2) or m.group(3)))
                elif 'tab' in m.group(0):
                    txt += '\t'
                else:
                    txt += '\n'
        yield idx, txt.rstrip(), total > 0 and code >= 0.6 * total, imgs


def heading_before(lines, i):
    for j in range(i - 1, max(-1, i - 40), -1):
        t = lines[j][1].strip()
        if t and not lines[j][2] and len(t) < 160:
            return t
    return ''


def extract(src_dir):
    os.makedirs(OUT, exist_ok=True)
    index = []
    sources = []
    for f in sorted(os.listdir(src_dir)):
        stem, ext = os.path.splitext(f)
        if ext == '.pdf':
            sources.append((PDF_NAMES.get(stem, stem), [(p, t, c, []) for p, t, c in pdf_lines(os.path.join(src_dir, f))], f))
        elif ext == '.docx':
            name = 'lab%s' % re.search(r'Lab(\d)', f).group(1)
            sources.append((name, list(docx_paras(os.path.join(src_dir, f))), f))
    for name, lines, fname in sources:
        d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
        i, n = 0, 0
        while i < len(lines):
            if not lines[i][2]:
                i += 1; continue
            start = i; block = []
            while i < len(lines) and (lines[i][2] or not lines[i][1].strip()) and not lines[i][3]:
                block.append(lines[i][1]); i += 1
            # images right after the block are Maple's rendered output
            outs = []
            while i < len(lines) and not lines[i][1].strip() and lines[i][3]:
                outs += lines[i][3]; i += 1
            text = '\n'.join(block).strip('\n')
            if len(text.strip()) < 3:
                continue
            n += 1
            kind = 'pde' if is_pde(text) else 'mpl'
            fn = '%02d.%s' % (n, kind)
            open(os.path.join(d, fn), 'w', encoding='utf8').write(text + '\n')
            index.append({'source': name, 'file': fname, 'id': '%s/%s' % (name, fn), 'kind': kind,
                          'loc': lines[start][0], 'context': heading_before(lines, start), 'output_images': outs})
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w'), indent=1)
    print('%d blocks' % len(index))


if __name__ == '__main__':
    extract(sys.argv[1] if len(sys.argv) > 1 else 'D:/Maple/Course Content')
