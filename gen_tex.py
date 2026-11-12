"""Procedural, tileable texture generator for Battle Front.
Outputs colour (.jpg) + tangent-space normal (.jpg) for every material and a manifest.json.
Run:  python3 gen_tex.py <out_dir>
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ helpers
def fbm(n, beta=2.0, seed=0, lo=1.0, hi=None, ax=1.0, ay=1.0):
    """Tileable band-limited noise in 0..1 (FFT based). ax/ay stretch the frequency axes."""
    r = np.random.default_rng(seed)
    w = r.standard_normal((n, n))
    F = np.fft.fft2(w)
    k = np.fft.fftfreq(n) * n
    KX, KY = np.meshgrid(k * ax, k * ay)
    f = np.sqrt(KX ** 2 + KY ** 2)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta / 2.0)
    amp[f < lo] = 0
    if hi is not None:
        amp[f > hi] = 0
    amp[0, 0] = 0
    out = np.real(np.fft.ifft2(F * amp))
    out = (out - out.mean()) / (out.std() + 1e-9)
    return np.clip(out * 0.22 + 0.5, 0, 1)

def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) == 2 else t
    return a + (b - a) * t

def col(r, g, b, n):
    return np.ones((n, n, 3)) * np.array([r, g, b])

def smooth(x, a, b):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)

def wrap_draw(img, fn):
    """call fn(draw, dx, dy) at 9 wrap offsets so shapes tile seamlessly"""
    n = img.size[0]
    d = ImageDraw.Draw(img)
    for dx in (-n, 0, n):
        for dy in (-n, 0, n):
            fn(d, dx, dy)

def layer_to_arr(img):
    return np.asarray(img, dtype=np.float32) / 255.0

def voronoi_edges(n, pts, seed, width=0.02):
    r = np.random.default_rng(seed)
    P = r.random((pts, 2))
    y, x = np.mgrid[0:n, 0:n] / n
    d = []
    for px, py in P:
        dx = np.abs(x - px); dx = np.minimum(dx, 1 - dx)
        dy = np.abs(y - py); dy = np.minimum(dy, 1 - dy)
        d.append(np.sqrt(dx * dx + dy * dy))
    d = np.sort(np.stack(d, 0), axis=0)
    edge = d[1] - d[0]
    return np.clip(1 - edge / width, 0, 1), d[0]

def normal_from_height(h, strength=2.0):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nx, ny, nz = -gx * strength * 8, gy * strength * 8, np.ones_like(h)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / L, ny / L, nz / L], -1) * 0.5 + 0.5

def save(name, color, height, nstrength=2.0, nsize=512, q=90):
    n = color.shape[0]
    Image.fromarray((np.clip(color, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, name + '.jpg'), quality=q, subsampling=0)
    nm = normal_from_height(height, nstrength)
    im = Image.fromarray((np.clip(nm, 0, 1) * 255).astype(np.uint8))
    if n != nsize:
        im = im.resize((nsize, nsize), Image.LANCZOS)
    im.save(os.path.join(OUT, name + '_normal.jpg'), quality=94, subsampling=0)
    print('wrote', name)

def speckle(n, density, seed, size=1):
    r = np.random.default_rng(seed)
    m = (r.random((n, n)) < density).astype(np.float32)
    if size > 1:
        m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(size if size % 2 else size + 1)), dtype=np.float32) / 255
    return m

# ------------------------------------------------------------------ ground
def grass(n=1024):
    low = fbm(n, 2.4, 1, 1, 24)
    mid = fbm(n, 1.6, 2, 8, 90)
    blades = fbm(n, 0.6, 3, 60, 380, ax=0.35, ay=1.0)       # vertical streaks = blades
    fine = fbm(n, 0.3, 4, 150, 500)
    dark, light = col(0.17, 0.30, 0.08, n), col(0.38, 0.52, 0.16, n)
    c = mix(dark, light, smooth(low * 0.6 + mid * 0.4, 0.3, 0.7))
    dry = smooth(fbm(n, 3.0, 5, 2, 10), 0.62, 0.85)
    c = mix(c, col(0.50, 0.48, 0.24, n), dry[..., None] * 0.35)
    c *= (0.72 + 0.5 * blades)[..., None] * (0.9 + 0.2 * fine)[..., None]
    # clover / tiny flowers
    fl = speckle(n, 0.0009, 9, 3)
    c = mix(c, col(0.9, 0.88, 0.7, n), fl[..., None] * 0.8)
    fl2 = speckle(n, 0.0005, 10, 3)
    c = mix(c, col(0.85, 0.75, 0.2, n), fl2[..., None] * 0.8)
    h = blades * 0.6 + mid * 0.3 + fine * 0.2
    save('grass', c, h, 1.6)

def sand(n=1024):
    warp = fbm(n, 2.5, 11, 1, 6)
    y = np.mgrid[0:n, 0:n][0] / n
    x = np.mgrid[0:n, 0:n][1] / n
    rip = np.sin(2 * np.pi * (y * 22 + warp * 0.9 + 0.25 * np.sin(2 * np.pi * x * 2)))
    rip = rip * 0.5 + 0.5
    grain = fbm(n, 0.4, 12, 120, 500)
    low = fbm(n, 2.2, 13, 1, 14)
    c = mix(col(0.72, 0.58, 0.38, n), col(0.88, 0.76, 0.54, n), smooth(low * 0.55 + rip * 0.45, 0.25, 0.8))
    c *= (0.9 + 0.2 * grain)[..., None]
    peb = speckle(n, 0.0006, 14, 3)
    c = mix(c, col(0.40, 0.34, 0.27, n), peb[..., None] * 0.7)
    h = rip * 0.5 + grain * 0.25 + peb * 0.4
    save('sand', c, h, 1.8)

def snow(n=1024):
    low = fbm(n, 2.6, 21, 1, 12)
    streak = fbm(n, 1.4, 22, 4, 60, ax=0.12, ay=1.0)
    sp = fbm(n, 0.3, 23, 200, 500)
    c = mix(col(0.80, 0.86, 0.96, n), col(0.97, 0.98, 1.0, n), smooth(low * 0.5 + streak * 0.5, 0.3, 0.75))
    # patches of frozen soil / dead grass
    soil = smooth(fbm(n, 3.2, 24, 2, 9), 0.70, 0.86)
    c = mix(c, col(0.55, 0.52, 0.46, n), soil[..., None] * 0.35)
    c = mix(c, col(0.55, 0.55, 0.40, n), (soil * smooth(sp, 0.55, 0.7))[..., None] * 0.5)
    glit = speckle(n, 0.0015, 25, 1)
    c = np.clip(c + glit[..., None] * 0.12, 0, 1)
    h = streak * 0.55 + low * 0.3 + sp * 0.15
    save('snow', c, h, 1.2)

def forest(n=1024):
    low = fbm(n, 2.4, 31, 1, 16)
    c = mix(col(0.23, 0.17, 0.09, n), col(0.34, 0.28, 0.12, n), low)
    moss = smooth(fbm(n, 3.0, 32, 2, 10), 0.58, 0.78)
    c = mix(c, col(0.16, 0.28, 0.09, n), moss[..., None] * 0.8)
    img = Image.fromarray((c * 255).astype(np.uint8))
    rr = np.random.default_rng(33)
    pal = [(178, 96, 28), (196, 140, 36), (140, 70, 24), (110, 82, 30), (160, 50, 24), (86, 92, 34)]
    h_img = Image.new('L', (n, n), 128)
    def leaves(d, dx, dy):
        pass
    for _ in range(7000):
        x, y = rr.integers(0, n, 2)
        L = rr.integers(8, 20); W = max(3, int(L * rr.uniform(0.35, 0.55)))
        ang = rr.uniform(0, np.pi)
        cx, cy = np.cos(ang) * L / 2, np.sin(ang) * L / 2
        colr = pal[rr.integers(0, len(pal))]
        sh = rr.uniform(0.65, 1.1)
        colr = tuple(int(min(255, v * sh)) for v in colr)
        for dx in (-n, 0, n):
            for dy in (-n, 0, n):
                if -30 < x + dx < n + 30 and -30 < y + dy < n + 30:
                    pts = [(x + dx - cx, y + dy - cy), (x + dx + cx, y + dy + cy)]
                    ImageDraw.Draw(img).line(pts, fill=colr, width=W)
                    ImageDraw.Draw(h_img).line(pts, fill=int(150 + rr.integers(-8, 12)), width=W)
    for _ in range(500):   # twigs
        x, y = rr.integers(0, n, 2); L = rr.integers(25, 70); ang = rr.uniform(0, np.pi)
        for dx in (-n, 0, n):
            for dy in (-n, 0, n):
                pts = [(x + dx, y + dy), (x + dx + np.cos(ang) * L, y + dy + np.sin(ang) * L)]
                ImageDraw.Draw(img).line(pts, fill=(54, 38, 22), width=2)
                ImageDraw.Draw(h_img).line(pts, fill=165, width=2)
    arr = np.asarray(img, dtype=np.float32) / 255
    fine = fbm(n, 0.5, 34, 100, 400)
    arr *= (0.85 + 0.3 * fine)[..., None]
    h = np.asarray(h_img, dtype=np.float32) / 255 * 0.8 + fine * 0.2
    save('forest', arr, h, 2.4)

def rock(n=1024):
    warp = fbm(n, 2.6, 41, 1, 5)
    y = np.mgrid[0:n, 0:n][0] / n
    layers = np.sin(2 * np.pi * (y * 9 + warp * 2.2)) * 0.5 + 0.5
    crack, cell = voronoi_edges(n, 70, 42, 0.012)
    mid = fbm(n, 2.0, 43, 3, 60)
    fine = fbm(n, 0.8, 44, 60, 400)
    c = mix(col(0.34, 0.31, 0.28, n), col(0.58, 0.54, 0.48, n), smooth(mid * 0.6 + layers * 0.4, 0.25, 0.8))
    c *= (0.85 + 0.3 * fine)[..., None]
    c *= (1 - 0.6 * crack)[..., None]
    lich = speckle(n, 0.0012, 45, 5)
    c = mix(c, col(0.62, 0.64, 0.30, n), lich[..., None] * 0.5)
    h = mid * 0.5 + layers * 0.2 + fine * 0.15 - crack * 0.6 + 0.3
    save('rock', c, h, 2.6)

def urban(n=1024):
    low = fbm(n, 2.4, 51, 1, 18)
    fine = fbm(n, 0.7, 52, 80, 400)
    c = mix(col(0.30, 0.30, 0.29, n), col(0.50, 0.49, 0.46, n), low)
    crack, _ = voronoi_edges(n, 40, 53, 0.007)
    stain = smooth(fbm(n, 3.0, 54, 2, 12), 0.6, 0.8)
    c = mix(c, col(0.10, 0.09, 0.08, n), stain[..., None] * 0.6)
    c *= (0.85 + 0.3 * fine)[..., None]
    c *= (1 - 0.55 * crack)[..., None]
    deb = speckle(n, 0.0012, 55, 3)
    c = mix(c, col(0.55, 0.30, 0.22, n), deb[..., None] * 0.6)       # brick bits
    deb2 = speckle(n, 0.0010, 56, 2)
    c = mix(c, col(0.70, 0.70, 0.66, n), deb2[..., None] * 0.6)
    h = low * 0.3 + fine * 0.3 - crack * 0.5 + deb * 0.3 + 0.2
    save('urban', c, h, 2.0)

def runway(n=1024):
    """One tile = 60 m wide (u) x 100 m long (v). Use repeat [1, 9] on a 60x900 plane."""
    base = fbm(n, 0.5, 61, 80, 500) * 0.5 + fbm(n, 2.0, 62, 2, 40) * 0.5
    c = col(0.17, 0.17, 0.18, n) * (0.7 + 0.6 * base)[..., None]
    y, x = np.mgrid[0:n, 0:n] / n
    # wheel tracks (rubber) + oil
    for u0 in (0.30, 0.70, 0.42, 0.58):
        c *= (1 - 0.16 * np.exp(-((x - u0) / 0.035) ** 2) * (0.6 + 0.4 * fbm(n, 2, 63, 1, 8, ax=0.1)))[..., None]
    # patches
    pr = np.random.default_rng(64)
    for _ in range(9):
        px, py, pw, ph = pr.random(), pr.random(), pr.uniform(0.04, 0.14), pr.uniform(0.03, 0.10)
        m = ((np.abs(((x - px + .5) % 1) - .5) < pw) & (np.abs(((y - py + .5) % 1) - .5) < ph))
        c[m] *= pr.uniform(0.82, 1.18)
    # cracks
    img = Image.fromarray((np.clip(c, 0, 1) * 255).astype(np.uint8))
    for _ in range(26):
        sx, sy = pr.integers(0, n, 2); pts = [(sx, sy)]; ang = pr.uniform(0, 6.28)
        for _s in range(14):
            ang += pr.uniform(-0.6, 0.6); sx += np.cos(ang) * 24; sy += np.sin(ang) * 24; pts.append((sx, sy))
        for dx in (-n, 0, n):
            for dy in (-n, 0, n):
                ImageDraw.Draw(img).line([(a + dx, b + dy) for a, b in pts], fill=(18, 18, 19), width=2)
    c = np.asarray(img, dtype=np.float32) / 255
    # markings (paint, worn)
    wear = smooth(fbm(n, 2.4, 65, 2, 12), 0.2, 0.5) * 0.3 + 0.7
    paint = np.zeros((n, n), np.float32)
    paint[(x > 0.030) & (x < 0.046)] = 1
    paint[(x > 0.954) & (x < 0.970)] = 1
    dash = ((y % 0.5) < 0.30)
    paint[(x > 0.488) & (x < 0.512) & dash] = 1
    # aiming-point style side bars every tile
    paint[(x > 0.14) & (x < 0.24) & (y > 0.40) & (y < 0.46)] = 1
    paint[(x > 0.76) & (x < 0.86) & (y > 0.40) & (y < 0.46)] = 1
    paint *= wear
    c = mix(c, col(0.86, 0.86, 0.82, n), (paint * 0.95)[..., None])
    h = base * 0.3 + (1 - paint) * 0.05
    save('runway', c, h, 1.0)

# ------------------------------------------------------------------ buildings
def windows_layer(n, cols, rows, ww, wh, seed, lit=0.0):
    """returns (glassmask, framemask, glasscolor) for a grid of windows"""
    r = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n] / n
    gm = np.zeros((n, n), np.float32); fm = np.zeros((n, n), np.float32)
    gc = np.zeros((n, n, 3), np.float32)
    for i in range(cols):
        for j in range(rows):
            cx = (i + 0.5) / cols; cy = (j + 0.5) / rows
            hw, hh = ww / 2 / cols, wh / 2 / rows
            fr = 0.012
            f = (np.abs(x - cx) < hw + fr) & (np.abs(y - cy) < hh + fr)
            g = (np.abs(x - cx) < hw) & (np.abs(y - cy) < hh)
            fm[f] = 1; gm[g] = 1
            b = r.uniform(0.7, 1.2)
            top = np.array([0.30, 0.38, 0.46]) * b; bot = np.array([0.08, 0.10, 0.13]) * b
            t = np.clip((y - (cy - hh)) / (2 * hh + 1e-9), 0, 1)[..., None]
            gcell = top * (1 - t) + bot * t
            if r.random() < 0.25:   # curtains / interior glow
                gcell = gcell * 0.5 + np.array([0.35, 0.27, 0.14]) * r.uniform(0.3, 0.9)
            if r.random() < lit:
                gcell = np.array([0.9, 0.78, 0.45])
            gc[g] = gcell[g]
    return gm, fm, gc

def facade(name, base_lo, base_hi, cols, rows, ww, wh, seed, n=512, brick=False, planks=False, frame=(0.82, 0.82, 0.80), stains=0.4, ns=2.0):
    low = fbm(n, 2.2, seed, 1, 14)
    fine = fbm(n, 0.6, seed + 1, 60, 250)
    y, x = np.mgrid[0:n, 0:n]
    c = mix(col(*base_lo, n), col(*base_hi, n), low)
    h = low * 0.2 + fine * 0.1
    if brick:
        bh, bw = 12, 30
        row = y // bh
        off = (row % 2) * (bw // 2)
        bx = (x + off) % bw; by = y % bh
        mortar = (bx < 2) | (by < 2)
        r = np.random.default_rng(seed + 5)
        tint = r.uniform(0.75, 1.2, size=(n // bh + 2, n // bw + 3))
        t = tint[row, ((x + off) // bw) % tint.shape[1]]
        c = c * t[..., None]
        c[mortar] = np.array([0.62, 0.60, 0.56]) * (0.85 + 0.3 * fine[mortar][:, None])
        h = np.where(mortar, 0.1, 0.5) + fine * 0.1
    if planks:
        ph = 32
        pl = y // ph
        r = np.random.default_rng(seed + 6)
        ptint = r.uniform(0.7, 1.15, n // ph + 1)
        grain = fbm(n, 1.2, seed + 7, 8, 120, ax=0.08, ay=1.0)
        c = c * (ptint[pl] * (0.8 + 0.4 * grain))[..., None]
        seam = (y % ph) < 2
        c[seam] *= 0.35
        h = np.where(seam, 0.1, 0.5) + grain * 0.2
    st = smooth(fbm(n, 2.6, seed + 2, 2, 24, ax=0.15, ay=1.0), 0.55, 0.9) * stains * 0.4
    c *= (1 - st * 0.55)[..., None]
    if cols:
        gm, fm, gc = windows_layer(n, cols, rows, ww, wh, seed + 3, lit=0.0)
        c = np.where(fm[..., None] > 0, np.array(frame) * (0.9 + 0.2 * fine[..., None]), c)
        c = np.where(gm[..., None] > 0, gc, c)
        h = np.where(fm > 0, 0.62, h); h = np.where(gm > 0, 0.05, h)
        # sill
    # horizontal floor seams for concrete
    if not brick and not planks and rows:
        for j in range(rows):
            yy = int(j / rows * n)
            c[yy:yy + 2] *= 0.7; h[yy:yy + 2] = 0.25
    save(name, c, h, ns, nsize=512)

def roof(n=512):
    r = np.random.default_rng(71)
    y, x = np.mgrid[0:n, 0:n]
    th, tw = 32, 24
    row = y // th; off = (row % 2) * (tw // 2)
    tx = ((x + off) % tw) / tw; ty = (y % th) / th
    shade = 0.5 + 0.5 * np.sin(tx * np.pi)           # curved clay tile
    shade *= 0.55 + 0.45 * ty                          # overlapping lower edge brighter
    tint = r.uniform(0.75, 1.15, size=(n // th + 2, n // tw + 3))[row, ((x + off) // tw) % (n // tw + 3)]
    fine = fbm(n, 0.7, 72, 30, 250)
    moss = smooth(fbm(n, 3.0, 73, 2, 12), 0.62, 0.8)
    c = (0.52 + 0.45 * shade) * tint * (0.85 + 0.3 * fine)
    c = np.stack([c, c, c], -1)
    c = mix(c, col(0.35, 0.45, 0.25, n) * 0.9, moss[..., None] * 0.4)
    gap = (ty < 0.07)
    c[gap] *= 0.35
    h = shade * 0.6 + (1 - gap) * 0.1
    save('roof', c, h, 2.5)

# ------------------------------------------------------------------ vehicles
def metal(n=512):
    """Aircraft skin: panel lines, rivets, oil streaks. Light grey so colour tint shows through."""
    r = np.random.default_rng(81)
    base = fbm(n, 2.2, 81, 1, 20)
    fine = fbm(n, 0.7, 82, 50, 250)
    c = col(0.80, 0.80, 0.80, n) * (0.88 + 0.2 * base)[..., None] * (0.95 + 0.1 * fine)[..., None]
    h = np.full((n, n), 0.5, np.float32)
    img = Image.fromarray((np.clip(c, 0, 1) * 255).astype(np.uint8)); himg = Image.fromarray((h * 255).astype(np.uint8))
    d = ImageDraw.Draw(img); hd = ImageDraw.Draw(himg)
    xs = np.sort(r.integers(0, n, 7)); ys = np.sort(r.integers(0, n, 9))
    xs = [0] + list(xs); ys = [0] + list(ys)
    for xv in xs:
        d.line([(xv, 0), (xv, n)], fill=(60, 62, 66), width=1); hd.line([(xv, 0), (xv, n)], fill=70, width=2)
        for yv in range(4, n, 14):
            d.ellipse([xv + 3 - 1, yv - 1, xv + 3 + 1, yv + 1], fill=(120, 122, 126)); hd.ellipse([xv + 2, yv - 2, xv + 5, yv + 1], fill=200)
    for yv in ys:
        d.line([(0, yv), (n, yv)], fill=(60, 62, 66), width=1); hd.line([(0, yv), (n, yv)], fill=70, width=2)
        for xv in range(4, n, 14):
            d.ellipse([xv - 1, yv + 3 - 1, xv + 1, yv + 3 + 1], fill=(120, 122, 126)); hd.ellipse([xv - 2, yv + 2, xv + 1, yv + 5], fill=200)
    for _ in range(150):   # scratches
        x0, y0 = r.integers(0, n, 2); L = r.integers(6, 40); a = r.uniform(0, 6.28)
        d.line([(x0, y0), (x0 + np.cos(a) * L, y0 + np.sin(a) * L)], fill=(205, 206, 208), width=1)
    arr = np.asarray(img, dtype=np.float32) / 255
    streak = fbm(n, 1.8, 83, 3, 60, ax=0.1, ay=1.0)
    arr *= (1 - 0.12 * smooth(streak, 0.55, 0.85))[..., None]
    h = np.asarray(himg, dtype=np.float32) / 255 * 0.9 + fine * 0.1
    save('metal', arr, h, 2.2)

def armor(n=512):
    """Rolled / cast steel for tanks with weld seams, bolts, pitting and dust."""
    r = np.random.default_rng(91)
    low = fbm(n, 2.4, 91, 1, 14)
    pit = fbm(n, 0.4, 92, 80, 250)
    c = col(0.74, 0.74, 0.72, n) * (0.82 + 0.3 * low)[..., None] * (0.9 + 0.2 * pit)[..., None]
    h = pit * 0.25 + low * 0.1 + 0.4
    img = Image.fromarray((np.clip(c, 0, 1) * 255).astype(np.uint8)); himg = Image.fromarray((np.clip(h, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img); hd = ImageDraw.Draw(himg)
    # plates with weld seams
    for v in (0, 170, 340):
        for ln in range(-3, 4):
            yy = v + ln * 0
        for xx in range(0, n, 14):
            yy = v + int(3 * np.sin(xx * 0.5))
            d.ellipse([xx, yy, xx + 9, yy + 5], outline=(90, 90, 88)); hd.ellipse([xx, yy, xx + 9, yy + 5], fill=190)
    for u in (60, 280, 450):
        for yy in range(0, n, 14):
            xx = u + int(3 * np.sin(yy * 0.5))
            d.ellipse([xx, yy, xx + 5, yy + 9], outline=(90, 90, 88)); hd.ellipse([xx, yy, xx + 5, yy + 9], fill=190)
    for _ in range(60):   # bolts
        bx, by = r.integers(8, n - 8, 2)
        d.ellipse([bx - 4, by - 4, bx + 4, by + 4], fill=(96, 96, 94), outline=(46, 46, 44)); hd.ellipse([bx - 4, by - 4, bx + 4, by + 4], fill=215)
    for _ in range(120):  # edge wear / scratches
        x0, y0 = r.integers(0, n, 2); L = r.integers(5, 30); a = r.uniform(0, 6.28)
        d.line([(x0, y0), (x0 + np.cos(a) * L, y0 + np.sin(a) * L)], fill=(190, 188, 180), width=1)
    arr = np.asarray(img, dtype=np.float32) / 255
    dust = smooth(fbm(n, 2.4, 93, 2, 30, ax=0.5, ay=1.0), 0.45, 0.85)
    arr = mix(arr, np.array([0.60, 0.52, 0.40]) * arr.mean(-1, keepdims=True) * 1.3, (dust * 0.18)[..., None])
    h = np.asarray(himg, dtype=np.float32) / 255
    save('armor', np.clip(arr, 0, 1), h, 2.4)

def fabric(n=512):
    r = np.random.default_rng(101)
    y, x = np.mgrid[0:n, 0:n]
    weave = (np.sin(x * 2 * np.pi / 3.0) * np.sin(y * 2 * np.pi / 3.0)) * 0.5 + 0.5
    low = fbm(n, 2.4, 101, 1, 18)
    c = col(0.86, 0.80, 0.64, n) * (0.88 + 0.2 * low)[..., None] * (0.92 + 0.12 * weave)[..., None]
    # doped rib stitching rows
    for u in range(0, n, 64):
        c[:, u:u + 2] *= 0.70
        for yy in range(0, n, 8):
            c[yy:yy + 2, u + 3:u + 6] *= 0.55
    sag = smooth(fbm(n, 2.0, 102, 3, 30), 0.55, 0.8)
    c *= (1 - 0.10 * sag)[..., None]
    h = weave * 0.3 + low * 0.2 + 0.3
    save('fabric', c, h, 1.6)

def tracks(n=512):
    r = np.random.default_rng(111)
    y, x = np.mgrid[0:n, 0:n]
    lh = 32   # one link per 32 px (16 links)
    ly = y % lh
    c = np.ones((n, n, 3), np.float32) * np.array([0.16, 0.15, 0.14])
    link = fbm(n, 1.0, 111, 20, 200)
    c *= (0.7 + 0.7 * link)[..., None]
    h = np.full((n, n), 0.5, np.float32)
    for k in range(0, n, lh):
        c[k:k + 3] *= 0.3; h[k:k + 3] = 0.1
    # end connectors / grousers
    for xx in (0, n // 2):
        c[:, xx:xx + 70] *= 1.25
    guide = (np.abs(x - n // 2) < 22) & (ly > 6) & (ly < 26)
    h[guide] = 0.9; c[guide] *= 1.35
    for kx in (40, n - 40):
        for ky in range(0, n, lh):
            c[ky + 14:ky + 20, kx - 4:kx + 4] = 0.40
            h[ky + 14:ky + 20, kx - 4:kx + 4] = 0.8
    dirt = smooth(fbm(n, 2.5, 112, 2, 30), 0.5, 0.8)
    c = mix(c, col(0.30, 0.23, 0.16, n), (dirt * 0.5)[..., None])
    rust = smooth(fbm(n, 2.8, 113, 2, 20), 0.6, 0.85)
    c = mix(c, col(0.38, 0.20, 0.10, n), (rust * 0.4)[..., None])
    save('tracks', c, h, 2.6)

def camo(n=512):
    a = fbm(n, 2.6, 121, 1, 7); b = fbm(n, 2.6, 122, 1, 9); cc = fbm(n, 2.6, 123, 1, 11)
    base = col(0.32, 0.36, 0.20, n)
    c = base
    c = mix(c, col(0.42, 0.33, 0.18, n), smooth(a, 0.52, 0.56)[..., None])
    c = mix(c, col(0.18, 0.22, 0.13, n), smooth(b, 0.54, 0.58)[..., None])
    c = mix(c, col(0.08, 0.08, 0.07, n), smooth(cc, 0.62, 0.65)[..., None])
    fine = fbm(n, 0.6, 124, 60, 250)
    c *= (0.85 + 0.3 * fine)[..., None]
    save('camo', c, fine, 1.2)

# ------------------------------------------------------------------ run
if __name__ == '__main__':
    grass(); sand(); snow(); forest(); rock(); urban(); runway(); roof()
    facade('building', (0.54, 0.54, 0.52), (0.70, 0.70, 0.67), 4, 3, 0.55, 0.50, 201)
    facade('brick', (0.60, 0.28, 0.20), (0.74, 0.40, 0.28), 2, 2, 0.34, 0.45, 211, brick=True, frame=(0.88, 0.88, 0.84), stains=0.3, ns=2.2)
    facade('plaster', (0.78, 0.72, 0.60), (0.90, 0.85, 0.72), 2, 2, 0.26, 0.34, 221, frame=(0.45, 0.32, 0.20), stains=0.5)
    facade('wood', (0.42, 0.28, 0.16), (0.56, 0.38, 0.22), 2, 2, 0.22, 0.30, 231, planks=True, frame=(0.85, 0.82, 0.75), stains=0.3)
    metal(); armor(); fabric(); tracks(); camo()
    T = {}
    def entry(name, rep): T[name] = {"map": name + ".jpg", "normalMap": name + "_normal.jpg", "repeat": rep}
    entry('grass', [260, 260]); entry('sand', [260, 260]); entry('snow', [220, 220])
    entry('forest', [260, 260]); entry('rock', [200, 200]); entry('urban', [240, 240])
    entry('runway', [1, 9]); entry('building', [1, 1]); entry('brick', [1, 1]); entry('plaster', [1, 1])
    entry('wood', [1, 1]); entry('roof', [4, 4]); entry('metal', [1, 1]); entry('armor', [1, 1])
    entry('fabric', [1, 1]); entry('tracks', [1, 1]); entry('camo', [1, 1])
    json.dump({"version": 2, "heightConvention": "normal maps are tangent-space; colour maps are tintable (vehicle/roof maps are light grey on purpose)",
               "slots": {"ground": "grass", "vehicleBody": "metal", "vehicleTracks": "tracks"},
               "textures": T}, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=2)
    print('done')
