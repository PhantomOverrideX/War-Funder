#!/usr/bin/env python3
"""Battle Front launcher: checks for updates, starts a local server and opens the game.
Run with:  python start.py     (Windows: py start.py)      Stop with Ctrl+C.
"""
import functools, http.server, os, socketserver, subprocess, sys, threading, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8000


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    os.chdir(ROOT)
    upd = os.path.join(ROOT, 'updater.py')
    if os.path.isfile(upd):
        try:
            subprocess.run([sys.executable, upd], cwd=ROOT, timeout=300)
        except Exception as e:
            print('[update] skipped (%s)' % e)
        print()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = None
    for port in range(PORT, PORT + 20):
        try:
            srv = socketserver.ThreadingTCPServer(('127.0.0.1', port), functools.partial(Quiet, directory=ROOT))
            break
        except OSError:
            continue
    if srv is None:
        print('Could not find a free port.'); return 1
    url = 'http://localhost:%d/' % srv.server_address[1]
    print('Serving %s on %s' % (ROOT, url))
    print('Press Ctrl+C to stop the server.')
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        srv.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
