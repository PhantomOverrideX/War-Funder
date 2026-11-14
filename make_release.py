#!/usr/bin/env python3
"""Publish helper (for the game's author): run this after changing the game, then upload/push the folder.

    python make_release.py                 -> new version like 2026.11.14-1
    python make_release.py --version 2.0   -> your own version label

It rewrites manifest.json (version + SHA-256 of every game file). Friends' launchers compare against it.
"""
import datetime, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_NAMES = {'manifest.json', 'update.json', 'make_release.py', 'gen_tex.py', 'start.ps1', 'start.py', 'README_UPDATES.txt', '.DS_Store'}
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.github'}
SKIP_EXT = {'.zip', '.part', '.pyc'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()


def main():
    files = {}
    for d, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for n in sorted(names):
            if n in SKIP_NAMES and d == ROOT: continue
            if os.path.splitext(n)[1].lower() in SKIP_EXT: continue
            p = os.path.join(d, n); rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
            files[rel] = {'sha256': sha(p), 'size': os.path.getsize(p)}
    old = {}
    try: old = json.load(open(os.path.join(ROOT, 'manifest.json'), encoding='utf8'))
    except Exception: pass
    if old.get('files') == files and '--version' not in sys.argv:
        print('Nothing changed - keeping version', old.get('version')); return
    if '--version' in sys.argv:
        ver = sys.argv[sys.argv.index('--version') + 1]
    else:
        today = datetime.date.today().strftime('%Y.%m.%d'); n = 1
        ov = str(old.get('version', ''))
        if ov.startswith(today + '-'):
            try: n = int(ov.split('-')[1]) + 1
            except ValueError: pass
        ver = '%s-%d' % (today, n)
    with open(os.path.join(ROOT, 'manifest.json'), 'w', encoding='utf8') as f:
        json.dump({'version': ver, 'files': files}, f, indent=1, sort_keys=True)
    print('Release %s: %d files' % (ver, len(files)))
    print('Now upload/push the folder (including manifest.json) to your host.')


if __name__ == '__main__':
    main()
