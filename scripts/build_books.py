#!/usr/bin/env python3
"""Build the public EPUB catalog. Python 3.12, standard library only."""
import argparse, hashlib, html, json, posixpath, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET

DC = '{http://purl.org/dc/elements/1.1/}'
OPF = '{http://www.idpf.org/2007/opf}'
MAX_XML = 2 * 1024**2
MAX_COVER = 10 * 1024**2
MAX_EPUB = 95 * 1024**2
STATUS = {'unread', 'reading', 'finished'}

def read_limited(z, name, limit):
    info = z.getinfo(name)
    if info.file_size > limit:
        raise ValueError(f'oversize member: {name}')
    return z.read(info)

def xml(z, name):
    raw = read_limited(z, name, MAX_XML)
    # Reject entity declarations even in UTF-16/32; no custom DTD processing.
    low = raw.replace(b'\x00', b'').upper()
    if b'<!ENTITY' in low or b'<!DOCTYPE' in low:
        raise ValueError('DTD/entity declarations are not supported')
    return ET.fromstring(raw)

def member(base, href):
    u = urlsplit(href)
    if u.scheme or u.netloc or u.path.startswith('/'):
        raise ValueError('external or absolute EPUB reference')
    p = posixpath.normpath(posixpath.join(base, unquote(u.path)))
    if p in ('.', '..') or p.startswith('../') or p.startswith('/') or '\\' in p:
        raise ValueError('unsafe EPUB reference')
    return p

def textval(el):
    return ' '.join(''.join(el.itertext()).split()) if el is not None else ''

def metadata(meta, key):
    return textval(meta.find(DC + key))

def image_ext(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if raw.startswith(b'\xff\xd8\xff'): return 'jpg'
    if raw.startswith((b'GIF87a', b'GIF89a')): return 'gif'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP': return 'webp'
    return None

def fallback(title, author):
    def lines(s, n=14, maxlines=5):
        parts = [s[i:i+n] for i in range(0, len(s), n)] or ['']
        if len(parts)>maxlines: parts=parts[:maxlines]; parts[-1]=parts[-1][:-1]+'…'
        return parts
    t=''.join(f'<text x="200" y="{150+i*42}" font-size="27">{html.escape(l)}</text>' for i,l in enumerate(lines(title)))
    a=''.join(f'<text x="200" y="{420+i*29}" font-size="19">{html.escape(l)}</text>' for i,l in enumerate(lines(author,18,3)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600"><rect width="400" height="600" fill="#e9e0cf"/><rect x="18" y="18" width="364" height="564" fill="none" stroke="#8d7860" stroke-width="2"/><g text-anchor="middle" fill="#302a25" font-family="serif">{t}{a}<text x="200" y="550" font-size="14">JADEN LIBRARY</text></g></svg>').encode()

def extract(path):
    if path.stat().st_size > MAX_EPUB: raise ValueError('EPUB exceeds 95 MiB')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)): raise ValueError('duplicate ZIP members')
        if read_limited(z,'mimetype',100).strip()!=b'application/epub+zip': raise ValueError('not an EPUB')
        if 'META-INF/rights.xml' in names: raise ValueError('rights-managed EPUB not supported')
        if 'META-INF/encryption.xml' in names:
            enc=xml(z,'META-INF/encryption.xml')
            # Allow only standard font obfuscation, not encrypted book content.
            algs=[e.get('Algorithm','') for e in enc.iter() if e.tag.rsplit('}',1)[-1]=='EncryptionMethod']
            if not algs or any(a not in {'http://www.idpf.org/2008/embedding','http://ns.adobe.com/pdf/enc#RC'} for a in algs):
                raise ValueError('encrypted/DRM EPUB not supported')
        container=xml(z,'META-INF/container.xml')
        rootfile=next((e for e in container.iter() if e.tag.rsplit('}',1)[-1]=='rootfile'),None)
        if rootfile is None: raise ValueError('missing OPF rootfile')
        opfpath=member('',rootfile.attrib['full-path'])
        opf=xml(z,opfpath); meta=opf.find(OPF+'metadata'); manifest=opf.find(OPF+'manifest'); spine=opf.find(OPF+'spine')
        if meta is None or manifest is None or spine is None or len(spine)==0: raise ValueError('missing EPUB metadata/manifest/spine')
        items={i.get('id'):i for i in manifest.findall(OPF+'item')}
        for ref in spine.findall(OPF+'itemref'):
            item=items.get(ref.get('idref'))
            if item is None or member(posixpath.dirname(opfpath),item.get('href','')) not in names: raise ValueError('missing spine content')
        title=metadata(meta,'title') or path.stem
        authors=[textval(e) for e in meta.findall(DC+'creator') if textval(e)]
        author=', '.join(authors) or '저자 미상'
        cover_items=[i for i in items.values() if 'cover-image' in i.get('properties','').split()]
        for m in meta.findall(OPF+'meta'):
            if m.get('name','').lower()=='cover' and m.get('content') in items: cover_items.append(items[m.get('content')])
        cover_items += [i for i in items.values() if i.get('media-type','').startswith('image/') and 'cover' in (i.get('id','')+' '+i.get('href','')).lower()]
        cover=None; ext=None
        for item in cover_items:
            try:
                raw=read_limited(z,member(posixpath.dirname(opfpath),item.get('href','')),MAX_COVER)
                kind=image_ext(raw)
                if kind: cover,ext=raw,kind; break
            except (KeyError,ValueError,RuntimeError,zipfile.BadZipFile): continue
        return dict(id='epub-'+digest, title=title, author=author, authors=authors, language=metadata(meta,'language') or 'und', published=metadata(meta,'date') or None, coverFallback=cover is None), cover if cover is not None else fallback(title,author), ext or 'svg'

def added(root,path):
    try:
        dates=subprocess.check_output(['git','-C',str(root),'log','--follow','--diff-filter=A','--format=%aI','--',path.relative_to(root).as_posix()],stderr=subprocess.DEVNULL,text=True).splitlines()
        if dates: return datetime.fromisoformat(dates[-1]).astimezone(timezone.utc).isoformat()
    except (OSError,subprocess.SubprocessError,ValueError): pass
    return datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()

def build(root,output):
    root=root.resolve(); output=output.resolve()
    books=root/'books'; overrides=json.loads((root/'books-overrides.json').read_text(encoding='utf-8')) if (root/'books-overrides.json').exists() else {}
    if not isinstance(overrides,dict): raise ValueError('overrides must be an object')
    records=[]; covers={}; seen=set(); used=set()
    for path in sorted(books.glob('*')):
        if path.suffix.lower()!='.epub': continue
        if path.is_symlink() or not path.is_file(): raise ValueError(f'not a regular file: {path.name}')
        try:
            book,cover,ext=extract(path)
            if book['id'] in seen: raise ValueError('duplicate EPUB content')
            seen.add(book['id'])
            key=path.name if path.name in overrides else book['id']
            override=overrides.get(key,{})
            if key in overrides: used.add(key)
            if not isinstance(override,dict): raise ValueError('invalid override')
            if any(k not in {'category','status','note'} for k in override): raise ValueError('unknown override field')
            category=override.get('category','미분류'); status=override.get('status','unread'); note=override.get('note','')
            if not all(isinstance(v,str) for v in (category,status,note)) or status not in STATUS: raise ValueError('invalid category/status/note')
            name=book['id']+'.'+ext
            book.update(file='books/'+quote(path.name,safe=''), cover='covers/'+name, addedAt=added(root,path), category=category,status=status,note=note)
            records.append(book); covers[name]=cover
        except Exception as e: raise ValueError(f'{path.name}: {e}') from e
    for key in sorted(set(overrides)-used): print(f'warning: unused override {key}',file=sys.stderr)
    records.sort(key=lambda b:(b['addedAt'],b['id']),reverse=True)
    output.mkdir(parents=True,exist_ok=True); target=output/'covers'; target.mkdir(exist_ok=True)
    for name,data in covers.items(): (target/name).write_bytes(data)
    for old in target.glob('epub-*'):
        if old.is_file() and old.name not in covers: old.unlink()
    tmp=output/'books.json.tmp'; tmp.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(output/'books.json')
    print(f'Catalog: {len(records)} books, {len(covers)} covers')
    return records

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); parser.add_argument('--output',type=Path); args=parser.parse_args()
    try: build(args.root,args.output or args.root)
    except Exception as e: print(f'ERROR: {e}',file=sys.stderr); sys.exit(1)
