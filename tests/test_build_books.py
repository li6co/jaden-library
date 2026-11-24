import base64, importlib.util, json, tempfile, unittest, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

spec=importlib.util.spec_from_file_location('builder',Path(__file__).resolve().parents[1]/'scripts/build_books.py')
builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jV1sAAAAASUVORK5CYII=')

def make_epub(path,title,author,lang,body,cover='epub3'):
    cover_item='' if not cover else '<item id="cov" href="images/cover.png" media-type="image/png"'+(' properties="cover-image"' if cover=='epub3' else '')+'/>'
    old='<meta name="cover" content="cov"/>' if cover=='epub2' else ''
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml','<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OEBPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        version='2.0' if cover=='epub2' else '3.0'
        nav_item='<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>' if version=='2.0' else '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        toc=' toc="ncx"' if version=='2.0' else ''
        z.writestr('OEBPS/book.opf',f'<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" version="{version}" unique-identifier="uid"><metadata><dc:identifier id="uid">urn:test:{escape(title)}</dc:identifier><dc:title>{escape(title)}</dc:title><dc:creator>{escape(author)}</dc:creator><dc:language>{lang}</dc:language><dc:date>1925</dc:date>{old}'+ ('<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>' if version=='3.0' else '') +f'</metadata><manifest><item id="c" href="chapter.xhtml" media-type="application/xhtml+xml"/>{cover_item}{nav_item}</manifest><spine{toc}><itemref idref="c"/></spine></package>')
        z.writestr('OEBPS/chapter.xhtml',f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}"><head><title>{escape(title)}</title></head><body><h1>{escape(title)}</h1><p>{escape(body)}</p></body></html>')
        if version=='2.0': z.writestr('OEBPS/toc.ncx',f'<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="urn:test:{escape(title)}"/></head><docTitle><text>{escape(title)}</text></docTitle><navMap><navPoint id="p1" playOrder="1"><navLabel><text>{escape(title)}</text></navLabel><content src="chapter.xhtml"/></navPoint></navMap></ncx>')
        else: z.writestr('OEBPS/nav.xhtml',f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body><nav epub:type="toc"><ol><li><a href="chapter.xhtml">{escape(title)}</a></li></ol></nav></body></html>')
        if cover: z.writestr('OEBPS/images/cover.png',PNG)

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name); (self.root/'books').mkdir(); self.out=self.root/'site'
    def tearDown(self): self.temp.cleanup()
    def put(self,name='진달래꽃.epub',cover='epub3'):
        path=self.root/'books'/name; make_epub(path,'진달래꽃','김소월','ko','나 보기가 역겨워 가실 때에는',cover); return path
    def test_three_public_domain_excerpt_fixtures(self):
        p=self.put(); make_epub(self.root/'books'/'Pride & Prejudice.epub','Pride and Prejudice','Jane Austen','en','It is a truth universally acknowledged.','epub2'); make_epub(self.root/'books'/'Alice.epub','Alice’s Adventures in Wonderland','Lewis Carroll','en','Alice was beginning to get very tired.',None)
        (self.root/'books-overrides.json').write_text(json.dumps({p.name:{'category':'시','status':'reading','note':'공개 메모'}},ensure_ascii=False),encoding='utf-8')
        rows=builder.build(self.root,self.out); self.assertEqual(len(rows),3); by={r['title']:r for r in rows}; ko=by['진달래꽃']; self.assertEqual((ko['author'],ko['language'],ko['published'],ko['status']),('김소월','ko','1925','reading')); self.assertIn('%',ko['file']); self.assertEqual((self.out/ko['cover']).read_bytes(),PNG); self.assertFalse(by['Pride and Prejudice']['coverFallback']); self.assertTrue(by['Alice’s Adventures in Wonderland']['coverFallback']); self.assertIn('Alice', (self.out/by['Alice’s Adventures in Wonderland']['cover']).read_text()); self.assertEqual(rows,builder.build(self.root,self.out)); p.unlink(); self.assertEqual(len(builder.build(self.root,self.out)),2); self.assertFalse((self.out/ko['cover']).exists())
    def test_invalid_zip(self):
        (self.root/'books'/'broken.epub').write_text('error'); self.assertRaises(ValueError,builder.build,self.root,self.out); self.assertFalse((self.out/'books.json').exists())
    def test_drm(self):
        p=self.put();
        with zipfile.ZipFile(p,'a') as z: z.writestr('META-INF/rights.xml','<rights/>')
        self.assertRaisesRegex(ValueError,'rights-managed',builder.build,self.root,self.out)
    def test_duplicate(self):
        p=self.put(); (p.parent/'copy.epub').write_bytes(p.read_bytes()); self.assertRaisesRegex(ValueError,'duplicate',builder.build,self.root,self.out)
    def test_unsafe_path(self): self.assertRaises(ValueError,builder.member,'OEBPS','../../outside.png')
    def test_100_plus(self):
        for i in range(110): make_epub(self.root/'books'/f'{i}.epub',f'테스트 {i}','테스트','ko','테스트',None)
        self.assertEqual(len(builder.build(self.root,self.out)),110)
    def test_empty(self): self.assertEqual(builder.build(self.root,self.out),[])

if __name__=='__main__': unittest.main()
