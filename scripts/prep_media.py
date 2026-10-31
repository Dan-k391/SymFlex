"""Prep visual references for corpus cleaning: docx media -> corpus/media/<lab>/ (WMF->PNG), PDF pages -> corpus/pages/."""
import os, subprocess, sys, zipfile, pymupdf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from extract_corpus import PDF_NAMES
src = sys.argv[1] if len(sys.argv) > 1 else 'D:/Maple/Course Content'
PS = r'''Add-Type -AssemblyName System.Drawing
Get-ChildItem -Path "%s" -Filter *.wmf | ForEach-Object {
  $img = [System.Drawing.Image]::FromFile($_.FullName)
  $bmp = New-Object System.Drawing.Bitmap $img.Width, $img.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.Clear([System.Drawing.Color]::White); $g.DrawImage($img, 0, 0, $img.Width, $img.Height)
  $bmp.Save(($_.FullName -replace '\.wmf$', '.png'), [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose(); $img.Dispose()
  Remove-Item $_.FullName }'''
for f in sorted(os.listdir(src)):
    stem, ext = os.path.splitext(f)
    if ext == '.docx':
        lab = 'lab' + f.split('Lab')[1][0]
        d = os.path.join(ROOT, 'corpus', 'media', lab)
        os.makedirs(d, exist_ok=True)
        z = zipfile.ZipFile(os.path.join(src, f))
        for n in z.namelist():
            if n.startswith('word/media/'):
                open(os.path.join(d, os.path.basename(n)), 'wb').write(z.read(n))
        subprocess.run(['powershell', '-NoProfile', '-Command', PS % d], check=True)
    elif ext == '.pdf':
        d = os.path.join(ROOT, 'corpus', 'pages', PDF_NAMES.get(stem, stem)); os.makedirs(d, exist_ok=True)
        for i, p in enumerate(pymupdf.open(os.path.join(src, f))):
            p.get_pixmap(dpi=110).save(os.path.join(d, 'p%02d.png' % (i + 1)))
print('done')
