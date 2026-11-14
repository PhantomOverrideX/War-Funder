#!/usr/bin/env python3
"""Battle Front auto-updater.

Run by start.ps1 / start.bat / start.sh before the game launches. It downloads manifest.json from the
address in update.json, compares file hashes with the local copy and fetches only what changed.
It never blocks the game: offline, misconfigured or failed updates just start the installed version.
Usage:  python updater.py           (update if needed)
        python updater.py --check   (report only, change nothing)
"""
import hashlib, json, os, posixpath, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PROTECTED = {'update.json'}          # never overwritten by an update (it holds the friend's own source URL)


def log(*a):
    print('[update]', *a, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, timeout):
    req = urllib.request.Request(url, headers={'User-Agent': 'battlefront-updater', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def safe_target(rel):
    """Map a manifest path to a file inside ROOT, or None if it tries to escape."""
    if not isinstance(rel, str) or not rel or '\\' in rel or ':' in rel or rel.startswith('/'):
        return None
    norm = posixpath.normpath(rel)
    if norm.startswith('..') or norm == '.' or any(p in ('', '..') for p in norm.split('/')):
        return None
    target = os.path.realpath(os.path.join(ROOT, *norm.split('/')))
    return target if target.startswith(os.path.realpath(ROOT) + os.sep) else None


def allowed_url(u):
    return u.startswith('https://') or u.startswith('http://127.0.0.1') or u.startswith('http://localhost')


def main():
    check_only = '--check' in sys.argv
    try:
        cfg = json.load(open(os.path.join(ROOT, 'update.json'), encoding='utf8'))
    except Exception:
        log('no update.json - skipping'); return 0
    murl = (cfg.get('manifestUrl') or '').strip()
    if not murl or 'OWNER' in murl:
        log('updates not configured (edit update.json) - skipping'); return 0
    if not allowed_url(murl):
        log('manifestUrl must be https - skipping'); return 0
    base = (cfg.get('baseUrl') or murl.rsplit('/', 1)[0] + '/').strip()
    if not base.endswith('/'): base += '/'

    parts = []
    try:
        raw = fetch(murl + ('&' if '?' in murl else '?') + 't=' + str(int.from_bytes(os.urandom(3), 'big')), 8)
        man = json.loads(raw)
        files = man['files']; remote_v = str(man.get('version', '?'))
        try: local_v = str(json.load(open(os.path.join(ROOT, 'manifest.json'), encoding='utf8')).get('version', '?'))
        except Exception: local_v = 'none'

        todo = []
        for rel, info in files.items():
            if rel in PROTECTED or rel == 'manifest.json': continue
            tgt = safe_target(rel)
            if tgt is None: raise ValueError('unsafe path in manifest: %r' % rel)
            if not os.path.isfile(tgt) or sha256(tgt) != info['sha256']:
                todo.append((rel, tgt, info))
        if not todo:
            log('up to date (v%s)' % local_v)
            if local_v != remote_v and not check_only:
                open(os.path.join(ROOT, 'manifest.json'), 'wb').write(raw)
            return 0
        size = sum(i.get('size', 0) for _, _, i in todo)
        log('update available: v%s -> v%s  (%d files, %.1f MB)' % (local_v, remote_v, len(todo), size / 1e6))
        if check_only: return 0

        for n, (rel, tgt, info) in enumerate(todo, 1):          # download everything first ...
            log('  [%d/%d] %s' % (n, len(todo), rel))
            data = fetch(base + rel.replace(' ', '%20'), 60)
            if hashlib.sha256(data).hexdigest() != info['sha256']:
                raise ValueError('hash mismatch for ' + rel)
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            part = tgt + '.part'; parts.append((part, tgt))
            with open(part, 'wb') as f: f.write(data)
        for part, tgt in parts:                                  # ... then swap them in together
            os.replace(part, tgt)
        parts = []
        with open(os.path.join(ROOT, 'manifest.json'), 'wb') as f: f.write(raw)
        log('updated to v%s' % remote_v)
    except Exception as e:
        for part, _ in parts:
            try: os.remove(part)
            except OSError: pass
        log("couldn't update (%s: %s) - starting the installed version" % (type(e).__name__, e))
    return 0


if __name__ == '__main__':
    sys.exit(main())
