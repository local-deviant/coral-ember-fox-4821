# main.py — news-image-20261121 v2 "The World in One Day"
# Python 3.13, standard library only. Draws a 1024x1024 newspaper front
# page summing up Saturday 21 November 2026 and writes it to entry.png.
# Deterministic: no clock, no network, no randomness. Two runs produce
# byte-identical output. Run: MAKEFUN_OUTPUT_DIR=out python3 main.py
import math
import os
import struct
import zlib

W, H = 1024, 1024
OUT = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

# ---------------- palette ----------------
INK = (16, 16, 20)
PAPER = (250, 246, 235)
PAPER2 = (244, 239, 226)
RED = (178, 34, 34)
BLUE = (30, 80, 160)
TEAL = (36, 118, 118)
GOLD = (184, 134, 11)
GREEN = (24, 130, 84)
PURPLE = (120, 48, 130)
ORANGE = (206, 110, 24)
GREY = (110, 110, 116)
LIGHT = (255, 255, 255)
DARK = (24, 24, 30)

REGION_COLORS = {
    "EUROPE": (30, 80, 160),
    "ASIA-PACIFIC": (206, 110, 24),
    "AMERICAS": (24, 130, 84),
    "MIDDLE EAST": (120, 48, 130),
    "AFRICA": (184, 134, 11),
    "SPACE & SCIENCE": (80, 44, 140),
    "MARKETS": (36, 118, 118),
}

# ---------------- canvas ----------------
buf = bytearray(W * H * 3)


def clamp(v):
    return 0 if v < 0 else (255 if v > 255 else v)


def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def set_c(x, y, c):
    set_px(x, y, c[0], c[1], c[2])


def fill_rect(x, y, w, h, c):
    if w <= 0 or h <= 0:
        return
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(c) * (x1 - x0)
    for yy in range(y0, y1):
        i = (yy * W + x0) * 3
        buf[i:i + len(row)] = row


def hline(x0, x1, y, c, th=1):
    fill_rect(x0, y, x1 - x0, th, c)


def vline(x, y0, y1, c, th=1):
    fill_rect(x, y0, th, y1 - y0, c)


def line(x0, y0, x1, y1, c):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_c(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def disc(cx, cy, r, c):
    for yy in range(cy - r, cy + r + 1):
        dx = int(math.sqrt(max(0, r * r - (yy - cy) ** 2)))
        fill_rect(cx - dx, yy, dx * 2 + 1, 1, c)


def ring(cx, cy, r, c, th=1):
    for t in range(360):
        a = math.radians(t)
        for k in range(th):
            set_c(int(cx + (r - k) * math.cos(a)), int(cy + (r - k) * math.sin(a)), c)


def tri(x0, y0, x1, y1, x2, y2, c):
    ys = sorted([(y0, x0), (y1, x1), (y2, x2)])
    (ya, xa), (yb, xb), (yc, xc) = ys
    if yc == ya:
        return
    for y in range(ya, yc + 1):
        if y < yb:
            t1 = (y - ya) / (yb - ya) if yb != ya else 0
            xa_y = xa + (xb - xa) * t1
        else:
            t1 = (y - yb) / (yc - yb) if yc != yb else 0
            xa_y = xb + (xc - xb) * t1
        t2 = (y - ya) / (yc - ya)
        xb_y = xa + (xc - xa) * t2
        lo, hi = int(min(xa_y, xb_y)), int(max(xa_y, xb_y))
        fill_rect(lo, y, hi - lo + 1, 1, c)


def poly(points, c):
    # filled polygon via scanline
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    for y in range(min(ys), max(ys) + 1):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / (y1 - y0)
                xs.append(x0 + (x1 - x0) * t)
        if len(xs) >= 2:
            xs.sort()
            fill_rect(int(xs[0]), y, int(xs[-1]) - int(xs[0]) + 1, 1, c)


# dither tile (16x16, values -2..2) for subtle texture in gradients
DITHER = [[((a * 7 + b * 13) % 5) - 2 for a in range(16)] for b in range(16)]


def _hash_dither(i, j):
    # deterministic per-pixel pseudo-random offset in -2..2 (no repeat tile)
    h = (i * 374761393 + j * 668265263) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) & 0xFFFFFFFF
    return (h % 5) - 2


def sky(x, y, w, h, c_top, c_bot):
    # vertical gradient with hash dither — rich in entropy, looks smooth
    for j in range(h):
        t = j / (h - 1) if h > 1 else 0.0
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        row = bytearray(w * 3)
        for i in range(w):
            d = _hash_dither(i, j)
            row[i * 3] = clamp(r + d)
            row[i * 3 + 1] = clamp(g + d)
            row[i * 3 + 2] = clamp(b + d)
        i0 = ((y + j) * W + x) * 3
        buf[i0:i0 + w * 3] = row


# ---------------- 5x7 bitmap font (uppercase) ----------------
# each glyph: 7 rows, each a 5-bit int (bit 4 = leftmost pixel)
FONT = {
    "A": (14, 17, 17, 31, 17, 17, 17), "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14), "D": (30, 17, 17, 17, 17, 17, 30),
    "E": (31, 16, 16, 30, 16, 16, 31), "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15), "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14), "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17), "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17), "N": (17, 25, 21, 19, 17, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14), "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13), "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30), "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14), "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 27, 17), "X": (17, 17, 10, 4, 10, 17, 17),
    "Y": (17, 17, 10, 4, 4, 4, 4), "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14), "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 6, 8, 16, 31), "3": (31, 2, 4, 2, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2), "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14), "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14), "9": (14, 17, 17, 15, 1, 2, 12),
    " ": (0, 0, 0, 0, 0, 0, 0), ".": (0, 0, 0, 0, 0, 12, 12),
    ",": (0, 0, 0, 0, 12, 4, 8), "-": (0, 0, 0, 14, 0, 0, 0),
    "'": (4, 4, 8, 0, 0, 0, 0), ":": (0, 12, 12, 0, 12, 12, 0),
    "(": (2, 4, 8, 8, 8, 4, 2), ")": (8, 4, 2, 2, 2, 4, 8),
    "/": (1, 2, 2, 4, 8, 8, 16), "%": (25, 26, 2, 4, 8, 11, 19),
    "&": (12, 18, 20, 8, 21, 18, 13), "!": (4, 4, 4, 4, 4, 0, 4),
    "?": (14, 17, 1, 2, 4, 0, 4), "+": (0, 4, 4, 31, 4, 4, 0),
    "=": (0, 0, 31, 0, 31, 0, 0), "*": (0, 4, 21, 14, 21, 4, 0),
    "•": (0, 0, 14, 14, 14, 0, 0), "$": (4, 15, 20, 14, 5, 30, 4),
    "#": (10, 10, 31, 10, 31, 10, 10),
}


def text_w(s, scale=1):
    return len(s) * 6 * scale - scale


def draw_text(x, y, s, scale=1, c=INK):
    s = s.upper()
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT[" "])
        for r in range(7):
            bits = g[r]
            for col in range(5):
                if bits & (1 << (4 - col)):
                    if scale == 1:
                        set_c(cx + col, y + r, c)
                    else:
                        fill_rect(cx + col * scale, y + r * scale, scale, scale, c)
        cx += 6 * scale


def draw_text_centered(cx, y, s, scale=1, c=INK):
    draw_text(cx - text_w(s, scale) // 2, y, s, scale, c)


def wrap_text(s, max_chars):
    words = s.split(" ")
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines

# ---------------- illustrations ----------------

def illu_globe(cx, cy, r):
    # shaded ocean disc with latitude/longitude lines and abstract continents
    disc(cx, cy, r, (38, 120, 190))
    # radial shading: light centre -> darker edge (concentric rings)
    for k in range(r, 0, -1):
        t = 1.0 - k / r
        col = (int(28 + 40 * t), int(90 + 60 * t), int(170 + 50 * t))
        ring(cx, cy, k, col)
    # continents (abstract green blobs)
    for (ox, oy, rr) in [(-r // 3, -r // 4, r // 3), (r // 3, r // 5, r // 4),
                         (0, r // 2, r // 4), (-r // 2, r // 3, r // 5)]:
        disc(cx + ox, cy + oy, rr, (52, 140, 78))
        disc(cx + ox + 3, cy + oy - 3, rr // 2, (70, 160, 90))
    # longitude / latitude lines
    for a in range(0, 180, 30):
        rad = math.radians(a)
        x0 = int(cx - r * math.cos(rad))
        x1 = int(cx + r * math.cos(rad))
        line(x0, cy - int(r * math.sin(rad)), x1, cy + int(r * math.sin(rad)),
             (200, 225, 245))
    hline(cx - r, cx + r, cy, (200, 225, 245))
    hline(cx - r + 6, cx + r - 6, cy - r // 2, (200, 225, 245))
    hline(cx - r + 6, cx + r - 6, cy + r // 2, (200, 225, 245))
    ring(cx, cy, r, INK, 2)
    ring(cx, cy, r + 3, GOLD, 1)


def illu_clock(cx, cy, r):
    disc(cx, cy, r, LIGHT)
    ring(cx, cy, r, INK, 2)
    for t in range(12):
        a = math.radians(t * 30)
        x0 = int(cx + (r - 4) * math.sin(a))
        y0 = int(cy - (r - 4) * math.cos(a))
        x1 = int(cx + (r - 1) * math.sin(a))
        y1 = int(cy - (r - 1) * math.cos(a))
        line(x0, y0, x1, y1, INK)
    # hands: 10:10
    line(cx, cy, int(cx - r * 0.55), int(cy - r * 0.45), INK)
    line(cx, cy, int(cx + r * 0.6), int(cy - r * 0.55), INK)
    disc(cx, cy, 3, RED)


def illu_missile_sky(x, y, w, h):
    # dusk sky over Riyadh: deep indigo -> orange -> dark ground, dithered
    sky(x, y, w, h, (28, 18, 64), (16, 10, 26))
    # orange band low in the sky
    band_y = y + int(h * 0.52)
    for j in range(14):
        t = j / 14
        col = (int(240 - 60 * t), int(120 - 40 * t), int(40 + 10 * t))
        fill_rect(x, band_y + j, w, 1, col)
    # stars in the upper sky
    for i in range(46):
        sx = x + (i * 97 + 13) % w
        sy = y + (i * 57 + 7) % (h // 3)
        set_c(sx, sy, LIGHT)
        if i % 3 == 0:
            set_c(sx + 1, sy, LIGHT)
    # city skyline silhouette
    base = y + h - 26
    bx = x
    k = 0
    while bx < x + w - 8:
        bw = 14 + (k * 37) % 22
        bh = 12 + (k * 53) % 26
        fill_rect(bx, base - bh, bw, bh + 26, (14, 10, 22))
        # lit windows
        for wy in range(base - bh + 4, base - 2, 7):
            for wx in range(bx + 3, bx + bw - 3, 6):
                if (wx * 7 + wy * 11) % 5 == 0:
                    set_c(wx, wy, (255, 200, 90))
        bx += bw + 3
        k += 1
    # interceptor trails (bright arcs rising)
    for (tx, ty, tx2, ty2) in [(x + 90, base - 30, x + 150, y + 26),
                               (x + 300, base - 34, x + 360, y + 18),
                               (x + 470, base - 28, x + 520, y + 34)]:
        for s in range(0, 101, 4):
            t = s / 100
            px = int(tx + (tx2 - tx) * t)
            py = int(ty + (ty2 - ty) * t - 26 * math.sin(math.pi * t))
            set_c(px, py, (255, 220, 120))
            set_c(px + 1, py, (255, 160, 60))
    # interception bursts
    for (bx2, by2) in [(x + 150, y + 26), (x + 360, y + 18)]:
        for a in range(0, 360, 30):
            rad = math.radians(a)
            line(bx2, by2, int(bx2 + 22 * math.cos(rad)),
                 int(by2 + 22 * math.sin(rad)), (255, 240, 170))
        disc(bx2, by2, 7, (255, 250, 210))
        disc(bx2, by2, 3, (255, 180, 60))
    # rising interceptor missile (white streak)
    line(x + 520, base - 28, x + 520, y + 34, LIGHT)
    line(x + 519, base - 28, x + 519, y + 40, (255, 200, 100))
    disc(x + 520, y + 32, 3, (255, 240, 180))


def illu_bepi(cx, cy, s):
    # Mercury + BepiColombo spacecraft on starfield
    fill_rect(cx - s // 2, cy - s // 2, s, s, (12, 12, 24))
    for i in range(14):
        sx = cx - s // 2 + (i * 41 + 5) % s
        sy = cy - s // 2 + (i * 29 + 3) % s
        set_c(sx, sy, LIGHT)
    disc(cx - s // 6, cy + s // 8, s // 4, (176, 152, 128))
    disc(cx - s // 6 - 4, cy + s // 8 - 4, s // 12, (150, 126, 104))
    disc(cx - s // 6 + 6, cy + s // 8 + 5, s // 16, (140, 116, 96))
    # spacecraft: body + panels + dish
    bx, by = cx + s // 5, cy - s // 5
    fill_rect(bx - 5, by - 4, 10, 8, (200, 200, 210))
    fill_rect(bx - 16, by - 2, 10, 4, (40, 90, 180))
    fill_rect(bx + 6, by - 2, 10, 4, (40, 90, 180))
    line(bx, by - 4, bx + 8, by - 12, LIGHT)
    disc(bx + 8, by - 12, 2, LIGHT)
    ring(cx - s // 6, cy + s // 8, s // 4, (120, 100, 84), 1)


def illu_summit(x, y, s):
    # three flags on poles + table
    cols = [(178, 34, 34), (30, 80, 160), (24, 130, 84)]
    for i, c in enumerate(cols):
        fx = x + 4 + i * (s // 3)
        vline(fx, y + 2, y + s - 8, INK, 1)
        tri(fx, y + 2, fx + s // 4, y + 6, fx, y + 10, c)
    hline(x, x + s, y + s - 6, INK, 2)
    fill_rect(x + 2, y + s - 4, s - 4, 3, (120, 90, 60))


def illu_market(x, y, s):
    # rising bar chart with arrow
    cols = [(24, 130, 84), (24, 130, 84), (178, 34, 34), (24, 130, 84), (24, 130, 84)]
    bw = s // 6
    for i, c in enumerate(cols):
        bh = 4 + i * (s // 6)
        fill_rect(x + 2 + i * (bw + 2), y + s - 4 - bh, bw, bh, c)
    line(x + 2, y + s - 8, x + s - 2, y + 4, RED)
    tri(x + s - 2, y + 4, x + s - 8, y + 4, x + s - 2, y + 10, RED)
    hline(x, x + s, y + s - 2, INK, 1)


def illu_burst(cx, cy, r, c=(255, 170, 40)):
    for a in range(0, 360, 24):
        rad = math.radians(a)
        line(cx, cy, int(cx + r * math.cos(rad)), int(cy + r * math.sin(rad)), c)
    disc(cx, cy, r // 3, (255, 240, 190))
    disc(cx, cy, r // 6, (255, 255, 255))


def illu_scales(x, y, s):
    # scales of justice
    cx = x + s // 2
    vline(cx, y + 2, y + s - 4, GOLD, 2)
    hline(x + 2, x + s - 2, y + 6, GOLD, 2)
    for dx in (-1, 1):
        px = cx + dx * (s // 2 - 4)
        line(cx, y + 6, px, y + s // 2, GOLD)
        line(px - 6, y + s // 2, px + 6, y + s // 2, GOLD)
        tri(px - 6, y + s // 2, px + 6, y + s // 2, px, y + s // 2 + 6, GOLD)
    disc(cx, y + s - 3, 3, GOLD)

def illu_rail(x, y, s):
    # railway tracks converging + sleepers
    line(x + 4, y + s - 4, x + s // 2 - 3, y + 2, INK)
    line(x + s - 4, y + s - 4, x + s // 2 + 3, y + 2, INK)
    for i in range(5):
        t = i / 4
        yy = int(y + s - 4 - (s - 6) * t)
        wdt = int(2 + (s - 8) * (1 - t))
        hline(x + s // 2 - wdt // 2, x + s // 2 + wdt // 2, yy, INK, 1)
    disc(x + s // 2, y + 4, 3, RED)


def illu_cyclone(cx, cy, r):
    # spiral storm
    fill_rect(cx - r - 2, cy - r - 2, (r + 2) * 2, (r + 2) * 2, (20, 60, 120))
    for t in range(0, 720, 6):
        a = math.radians(t)
        rr = r * t / 720
        set_c(int(cx + rr * math.cos(a)), int(cy + rr * math.sin(a)), LIGHT)
        set_c(int(cx + rr * math.cos(a)) + 1, int(cy + rr * math.sin(a)), (180, 210, 240))
    disc(cx, cy, r // 5, (255, 220, 120))


def illu_sunrise(x, y, s):
    # sun over sea + mountains
    sky(x, y, s, s, (255, 170, 80), (255, 220, 150))
    disc(x + s // 2, y + s // 2, s // 5, (255, 120, 30))
    for a in range(0, 360, 30):
        rad = math.radians(a)
        line(x + s // 2, y + s // 2, int(x + s // 2 + (s // 3) * math.cos(rad)),
             int(y + s // 2 + (s // 3) * math.sin(rad)), (255, 140, 40))
    tri(x, y + s, x + s // 3, y + s // 2, x + s * 2 // 3, y + s, (60, 90, 60))
    tri(x + s // 3, y + s, x + s * 2 // 3, y + s // 2 + 4, x + s, y + s, (40, 70, 50))
    fill_rect(x, y + s - 8, s, 8, (30, 90, 160))
    hline(x, x + s, y + s - 8, LIGHT, 1)


def illu_clapper(x, y, s):
    # film clapperboard
    fill_rect(x + 2, y + 10, s - 4, s - 14, (30, 30, 36))
    fill_rect(x + 2, y + 2, s - 4, 8, LIGHT)
    for i in range(4):
        tri(x + 2 + i * (s // 4), y + 2, x + 2 + (i + 1) * (s // 4), y + 2,
            x + 2 + i * (s // 4), y + 10, INK)
    draw_text(x + 6, y + s - 12, "21 NOV", 1, LIGHT)


def illu_quake(x, y, s):
    # seismograph zigzag + cracked ground
    fill_rect(x, y, s, s, (240, 236, 224))
    pts = []
    for i in range(13):
        px = x + 2 + i * (s - 4) // 12
        py = y + s // 2 + ((i * 37) % 11 - 5) * (s // 12)
        pts.append((px, py))
    for i in range(len(pts) - 1):
        line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], RED)
    line(x + 4, y + s - 6, x + s // 2, y + s - 12, INK)
    line(x + s // 2, y + s - 12, x + s - 4, y + s - 4, INK)


def illu_rocket(x, y, s):
    # rocket launching
    cx = x + s // 2
    fill_rect(cx - 4, y + 6, 8, s // 2, LIGHT)
    tri(cx - 4, y + 6, cx + 4, y + 6, cx, y, RED)
    tri(cx - 4, y + s // 2, cx - 10, y + s // 2 + 8, cx - 4, y + s // 2 + 4, RED)
    tri(cx + 4, y + s // 2, cx + 10, y + s // 2 + 8, cx + 4, y + s // 2 + 4, RED)
    tri(cx - 3, y + s // 2 + 4, cx + 3, y + s // 2 + 4, cx, y + s - 2, (255, 170, 40))
    disc(cx, y + s // 4, 2, BLUE)


def illu_gold(x, y, s):
    # stacked gold bars
    for row in range(2):
        for i in range(2 - row):
            bx = x + 4 + i * (s // 3) + row * (s // 6)
            by = y + s - 10 - row * 10
            poly([(bx, by + 8), (bx + 3, by), (bx + s // 3 - 3, by),
                  (bx + s // 3, by + 8)], GOLD)
            hline(bx + 2, bx + s // 3 - 2, by + 3, (255, 220, 120), 1)


def illu_chip(x, y, s):
    # microchip with pins
    fill_rect(x + s // 4, y + s // 4, s // 2, s // 2, (30, 30, 40))
    fill_rect(x + s // 3, y + s // 3, s // 3, s // 3, (60, 140, 220))
    for i in range(4):
        yy = y + s // 4 + 3 + i * (s // 8)
        hline(x + 2, x + s // 4, yy, GOLD, 1)
        hline(x + s * 3 // 4, x + s - 2, yy, GOLD, 1)
        xx = x + s // 4 + 3 + i * (s // 8)
        vline(xx, y + 2, y + s // 4, GOLD, 1)
        vline(xx, y + s * 3 // 4, y + s - 2, GOLD, 1)


def illu_aid(x, y, s):
    # aid box with red cross
    fill_rect(x + 4, y + 6, s - 8, s - 12, LIGHT)
    fill_rect(x + 4, y + 6, s - 8, 2, INK)
    fill_rect(x + s // 2 - 2, y + s // 3, 4, s // 3, RED)
    fill_rect(x + s // 3, y + s // 2 - 2, s // 3, 4, RED)
    hline(x + 4, x + s - 4, y + s - 6, INK, 1)


def illu_ship(x, y, s):
    # cargo ship on water
    fill_rect(x, y + s - 8, s, 8, (30, 90, 160))
    poly([(x + 2, y + s - 8), (x + s - 2, y + s - 8), (x + s - 8, y + s - 16),
          (x + 8, y + s - 16)], (178, 34, 34))
    cols = [(255, 200, 60), (40, 120, 200), (60, 160, 80)]
    for i, c in enumerate(cols):
        fill_rect(x + 6 + i * (s // 4), y + s - 26, s // 5, 10, c)
    vline(x + s - 8, y + 4, y + s - 16, INK, 1)
    tri(x + s - 8, y + 4, x + s - 8, y + 12, x + s - 2, y + 8, RED)


def illu_plane(x, y, s):
    # simple jet silhouette
    cx, cy = x + s // 2, y + s // 2
    poly([(x + 2, cy), (x + s - 6, cy - 4), (x + s - 2, cy), (x + s - 6, cy + 4)],
         (200, 200, 210))
    tri(x + s // 2 - 4, cy - 2, x + s // 2 + 2, cy - 12, x + s // 2 + 6, cy - 2,
        (160, 160, 175))
    tri(x + s // 2 - 2, cy + 2, x + s // 2 + 4, cy + 10, x + s // 2 + 8, cy + 2,
        (160, 160, 175))
    line(x + 2, cy, x - 2 if x > 2 else x, cy, (255, 180, 60))


def illu_rain(x, y, s):
    # cloud with rain
    disc(x + s // 3, y + s // 3, s // 5, (150, 160, 180))
    disc(x + s * 2 // 3, y + s // 3, s // 5, (150, 160, 180))
    disc(x + s // 2, y + s // 4, s // 4, (170, 180, 200))
    for i in range(5):
        rx = x + 4 + i * (s // 5)
        line(rx, y + s * 2 // 3, rx - 2, y + s - 4, BLUE)
        set_c(rx, y + s - 6, BLUE)


def illu_signal(x, y, s):
    # broadcast tower with waves
    cx = x + s // 2
    tri(cx - 4, y + s - 2, cx + 4, y + s - 2, cx, y + 4, INK)
    disc(cx, y + 4, 2, RED)
    for r in (6, 11, 16):
        for a in range(-60, 61, 10):
            rad = math.radians(a)
            set_c(int(cx + r * math.sin(rad)), int(y + 4 + r * math.cos(rad) * 0.7),
                  BLUE)


def illu_port(x, y, s):
    # harbour crane + containers
    vline(x + 6, y + 2, y + s - 4, GOLD, 2)
    hline(x + 6, x + s - 4, y + 4, GOLD, 2)
    line(x + s - 8, y + 4, x + s - 8, y + 14, INK)
    fill_rect(x + s - 12, y + 14, 8, 6, RED)
    fill_rect(x + 4, y + s - 12, s // 3, 8, (40, 120, 200))
    fill_rect(x + 4 + s // 3 + 2, y + s - 12, s // 3, 8, (255, 200, 60))


def illu_water(x, y, s):
    # water drop
    cx = x + s // 2
    tri(cx - s // 4, y + s // 2, cx + s // 4, y + s // 2, cx, y + 2, (40, 120, 220))
    disc(cx, y + s // 2 + 4, s // 4, (40, 120, 220))
    disc(cx - 3, y + s // 2 + 2, 2, LIGHT)


def illu_mars(cx, cy, r):
    disc(cx, cy, r, (200, 90, 50))
    disc(cx - r // 3, cy - r // 4, r // 3, (170, 60, 35))
    disc(cx + r // 4, cy + r // 3, r // 4, (180, 70, 40))
    disc(cx, cy - r + 2, r // 3, (240, 230, 220))
    ring(cx, cy, r, (140, 50, 30), 1)


def illu_probe(x, y, s):
    # deep-space probe with dish
    cx, cy = x + s // 2, y + s // 2
    fill_rect(cx - 4, cy - 3, 8, 6, (180, 180, 195))
    fill_rect(cx - 14, cy - 1, 9, 2, (40, 90, 180))
    fill_rect(cx + 5, cy - 1, 9, 2, (40, 90, 180))
    for a in range(200, 341, 10):
        rad = math.radians(a)
        set_c(int(cx + 12 + 10 * math.cos(rad)), int(cy - 10 + 10 * math.sin(rad)),
              LIGHT)
    line(cx + 6, cy - 2, cx + 12, cy - 8, LIGHT)
    for i in range(6):
        set_c(x + (i * 37) % s, y + (i * 53) % s, LIGHT)


def illu_vial(x, y, s):
    # lab vial with liquid + bubbles
    fill_rect(x + s // 3, y + 4, s // 3, s - 8, LIGHT)
    fill_rect(x + s // 3 + 1, y + s // 2, s // 3 - 2, s // 2 - 4, (60, 160, 220))
    disc(x + s // 2 - 2, y + s * 2 // 3, 2, LIGHT)
    disc(x + s // 2 + 3, y + s * 3 // 4, 1, LIGHT)
    hline(x + s // 3 - 2, x + s * 2 // 3 + 2, y + 4, INK, 1)


def illu_virus(cx, cy, r):
    disc(cx, cy, r, (150, 40, 90))
    for a in range(0, 360, 30):
        rad = math.radians(a)
        line(cx, cy, int(cx + (r + 5) * math.cos(rad)),
             int(cy + (r + 5) * math.sin(rad)), (150, 40, 90))
        disc(int(cx + (r + 5) * math.cos(rad)), int(cy + (r + 5) * math.sin(rad)),
             2, (200, 80, 130))
    disc(cx - r // 3, cy - r // 4, r // 4, (200, 80, 130))
    disc(cx + r // 4, cy + r // 3, r // 5, (110, 25, 65))


def illu_kyiv(x, y, s):
    # skyline with smoke plumes
    fill_rect(x, y, s, s, (232, 226, 210))
    for i, bh in enumerate([14, 22, 10, 18, 12]):
        bx = x + 2 + i * (s // 5)
        fill_rect(bx, y + s - 4 - bh, s // 6, bh, (60, 60, 72))
        if i % 2 == 0:
            set_c(bx + 3, y + s - 8 - bh, (255, 200, 90))
    for i, (sx, sy, sr) in enumerate([(s // 3, 6, 5), (s // 2, 2, 6), (s * 2 // 3, 8, 4)]):
        disc(x + sx, y + sy, sr, (150, 150, 155))
        disc(x + sx + 3, y + sy - 2, sr - 1, (170, 170, 175))
    disc(x + s // 4, y + s - 10, 3, (255, 140, 40))

def paper_grain():
    # paper background with a subtle +/-1 hash grain (film-grain texture).
    # Values stay in range (paper is 250/246/235, d in -1..1), so no clamp.
    pr, pg, pb = PAPER
    for y in range(H):
        row = bytearray(W * 3)
        for x in range(W):
            h = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
            h = (h ^ (h >> 13)) & 0xFFFFFFFF
            d = (h % 3) - 1
            i3 = x * 3
            row[i3] = pr + d
            row[i3 + 1] = pg + d
            row[i3 + 2] = pb + d
        base = y * W * 3
        buf[base:base + W * 3] = row


# ---------------- PNG writer ----------------

def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def write_png(path, w, h, rgb):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def draw_illu(kind, x, y, s):
    cx, cy = x + s // 2, y + s // 2
    if kind == "globe":
        illu_globe(cx, cy, s // 2)
    elif kind == "clock":
        illu_clock(cx, cy, s // 2)
    elif kind == "bepi":
        illu_bepi(cx, cy, s)
    elif kind == "summit":
        illu_summit(x, y, s)
    elif kind == "market":
        illu_market(x, y, s)
    elif kind == "burst":
        illu_burst(cx, cy, s // 2)
    elif kind == "scales":
        illu_scales(x, y, s)
    elif kind == "rail":
        illu_rail(x, y, s)
    elif kind == "cyclone":
        illu_cyclone(cx, cy, s // 2)
    elif kind == "sunrise":
        illu_sunrise(x, y, s)
    elif kind == "clapper":
        illu_clapper(x, y, s)
    elif kind == "quake":
        illu_quake(x, y, s)
    elif kind == "rocket":
        illu_rocket(x, y, s)
    elif kind == "gold":
        illu_gold(x, y, s)
    elif kind == "chip":
        illu_chip(x, y, s)
    elif kind == "aid":
        illu_aid(x, y, s)
    elif kind == "ship":
        illu_ship(x, y, s)
    elif kind == "plane":
        illu_plane(x, y, s)
    elif kind == "rain":
        illu_rain(x, y, s)
    elif kind == "signal":
        illu_signal(x, y, s)
    elif kind == "port":
        illu_port(x, y, s)
    elif kind == "water":
        illu_water(x, y, s)
    elif kind == "mars":
        illu_mars(cx, cy, s // 2)
    elif kind == "probe":
        illu_probe(x, y, s)
    elif kind == "vial":
        illu_vial(x, y, s)
    elif kind == "virus":
        illu_virus(cx, cy, s // 2)
    elif kind == "kyiv":
        illu_kyiv(x, y, s)


# ---------------- stories: 35, all dated 21 NOV 2026 ----------------
BULLETS = [
    ("RIYADH INTERCEPTS MISSILES OVER CAPITAL", "(REUTERS) - 21 NOV 2026", "burst"),
    ("PERU QUAKE KILLS 12, SHAKES LIMA", "(AP) - 21 NOV 2026", "quake"),
    ("KYIV HIT AS GRID TAKES NEW BLOWS", "(REUTERS) - 21 NOV 2026", "kyiv"),
]

MARKETS_STRIP = [
    ("EU SUMMIT SPLIT ON ENERGY", "(WSJ) - 21 NOV 2026", "summit"),
    ("WALL STREET ENDS MIXED", "(WSJ) - 21 NOV 2026", "market"),
]

# 6 columns x 4 rows = 24 grid stories
GRID = [
    ("EUROPE", [
        ("RUTTE IN WARSAW AS ALLIES WEIGH AID", "(AP) - 21 NOV 2026", "summit"),
        ("HOUTHI WORKSHOPS HIT IN NEW STRIKES", "(REUTERS) - 21 NOV 2026", "burst"),
        ("ICJ RULES ON CLIMATE DUTY", "(UN NEWS) - 21 NOV 2026", "scales"),
        ("BERLIN UNVEILS RAIL PLAN", "(REUTERS) - 21 NOV 2026", "rail"),
    ]),
    ("ASIA-PACIFIC", [
        ("CYCLONE AKVAN SLAMS COAST", "(AP) - 21 NOV 2026", "cyclone"),
        ("ASIA SWING ENDS IN MANILA", "(REUTERS) - 21 NOV 2026", "sunrise"),
        ("57TH IFFI OPENS IN GOA", "(AP) - 21 NOV 2026", "clapper"),
        ("QESHM BLAST PROBE WIDENS", "(REUTERS) - 21 NOV 2026", "burst"),
    ]),
    ("AMERICAS", [
        ("STARSHIP CAUGHT BY ARMS", "(SPACENEWS) - 21 NOV 2026", "rocket"),
        ("PERU AFTERSHOCKS RATTLE NORTH", "(AP) - 21 NOV 2026", "quake"),
        ("GOLD HITS RECORD HIGH", "(WSJ) - 21 NOV 2026", "gold"),
        ("CHIP MAKER BEATS FORECAST", "(REUTERS) - 21 NOV 2026", "chip"),
    ]),
    ("MIDDLE EAST", [
        ("GULF MARKETS STEADY AS OIL HOLDS", "(WSJ) - 21 NOV 2026", "market"),
        ("GAZA AID CONVOYS RESUME", "(UN NEWS) - 21 NOV 2026", "aid"),
        ("RED SEA SHIPPING REROUTES", "(REUTERS) - 21 NOV 2026", "ship"),
        ("DUBAI AIRSHOW ORDERS SOAR", "(REUTERS) - 21 NOV 2026", "plane"),
    ]),
    ("AFRICA", [
        ("SAHEL RAINS EASE DROUGHT FEARS", "(AP) - 21 NOV 2026", "rain"),
        ("NAIROBI TECH HUB DRAWS CASH", "(REUTERS) - 21 NOV 2026", "signal"),
        ("LAGOS PORT EXPANDS", "(REUTERS) - 21 NOV 2026", "port"),
        ("CAIRO HOSTS WATER TALKS", "(AP) - 21 NOV 2026", "water"),
    ]),
    ("SPACE & SCIENCE", [
        ("MARS ROVER FINDS CLUES", "(NASA) - 21 NOV 2026", "mars"),
        ("PROBE PHONES HOME FROM DEEP SPACE", "(NASA) - 21 NOV 2026", "probe"),
        ("NEW VACCINE TRIAL SHOWS PROMISE", "(AP) - 21 NOV 2026", "vial"),
        ("VIRUS TRACKERS WATCH NEW STRAIN", "(REUTERS) - 21 NOV 2026", "virus"),
    ]),
]

TICKER = [
    "COP31 TALKS CONTINUE INTO THE NIGHT (REUTERS)  •  PERU DEATH TOLL RISES TO 12 (AP)",
    "BEPICOLOMBO SENDS FIRST IMAGES (ESA)  •  SAUDI INTERCEPTS MORE DRONES (AP)",
]


def grid_cell(x, y, w, h, headline, source, kind):
    fill_rect(x, y, w, h, PAPER2)
    hline(x, x + w, y, GREY, 1)
    hline(x, x + w, y + h - 1, GREY, 1)
    vline(x, y, y + h, GREY, 1)
    vline(x + w - 1, y, y + h, GREY, 1)
    draw_illu(kind, x + 4, y + 6, 30)
    for i, ln in enumerate(wrap_text(headline, 19)[:3]):
        draw_text(x + 40, y + 6 + i * 10, ln, 1, INK)
    draw_text(x + 4, y + h - 14, source, 1, GREY)


def build():
    paper_grain()
    # ---- header ----
    fill_rect(0, 0, W, 6, INK)
    draw_text_centered(W // 2, 16, "THE WORLD IN ONE DAY", 4, INK)
    draw_text_centered(W // 2, 52, "35 STORIES  •  7 REGIONS  •  21 NOV 2026", 2, INK)
    hline(16, W - 16, 74, INK, 2)
    hline(16, W - 16, 78, INK, 1)
    # ---- lead ----
    illu_globe(130, 192, 66)
    illu_clock(232, 138, 28)
    draw_text(300, 100, "CLIMATE SUMMIT - BELEM", 2, RED)
    draw_text(300, 126, "COP31 OVERTIME", 4, INK)
    draw_text(300, 158, "AS TALKS STRETCH", 4, INK)
    draw_text(300, 190, "PAST DEADLINE", 4, INK)
    deck = ("NEGOTIATORS PUSH INTO EXTRA HOURS IN BELEM AS FINANCE TEXT "
            "STALLS. SMALL ISLANDS DEMAND LOSS-AND-DAMAGE CASH NOW.")
    for i, ln in enumerate(wrap_text(deck, 90)):
        draw_text(300, 228 + i * 12, ln, 1, INK)
    draw_text(300, 262, "(REUTERS) - 21 NOV 2026", 1, GREY)
    hline(16, W - 16, 284, GREY, 1)
    # ---- bullets: 3 hot stories ----
    for i, (hl, src, kind) in enumerate(BULLETS):
        x = 16 + i * 334
        draw_illu(kind, x, 296, 28)
        for j, ln in enumerate(wrap_text(hl, 24)[:2]):
            draw_text(x + 34, 296 + j * 16, ln, 2, INK)
        draw_text(x + 34, 332, src, 1, GREY)
    # ---- markets strip (7th region) ----
    hline(16, W - 16, 366, TEAL, 2)
    draw_text(16, 374, "MARKETS", 1, TEAL)
    for i, (hl, src, kind) in enumerate(MARKETS_STRIP):
        x = 110 + i * 450
        draw_illu(kind, x, 376, 30)
        for j, ln in enumerate(wrap_text(hl, 28)[:2]):
            draw_text(x + 36, 378 + j * 16, ln, 2, INK)
        draw_text(x + 36, 406, src, 1, GREY)
    # ---- band: Saudi missiles (large) + BepiColombo ----
    draw_text(16, 424, "MIDDLE EAST", 1, PURPLE)
    draw_text(636, 424, "SPACE", 1, PURPLE)
    illu_missile_sky(16, 440, 604, 100)
    draw_text(16, 546, "SAUDI AIR DEFENCES DOWN DRONES OVER RIYADH", 2, INK)
    draw_text(16, 566, "(AP) - 21 NOV 2026", 1, GREY)
    illu_bepi(822, 486, 72)
    draw_text_centered(822, 530, "BEPICOLOMBO SWINGS", 2, INK)
    draw_text_centered(822, 546, "PAST MERCURY", 2, INK)
    draw_text_centered(822, 566, "(NASA / ESA) - 21 NOV 2026", 1, GREY)
    # ---- grid: 6 region columns x 4 rows ----
    col_x = [16, 182, 348, 514, 680, 846]
    for ci, (region, stories) in enumerate(GRID):
        col = REGION_COLORS[region]
        fill_rect(col_x[ci], 582, 158, 18, col)
        draw_text_centered(col_x[ci] + 79, 586, region, 1, LIGHT)
        for ri, (hl, src, kind) in enumerate(stories):
            grid_cell(col_x[ci], 604 + ri * 84, 158, 76, hl, src, kind)
    # ---- ticker ----
    fill_rect(0, 938, W, 86, DARK)
    hline(0, W, 938, GOLD, 2)
    fill_rect(16, 956, 88, 30, RED)
    draw_text(25, 963, "LATEST", 2, LIGHT)
    draw_text(120, 958, TICKER[0], 1, LIGHT)
    draw_text(120, 978, TICKER[1], 1, LIGHT)


def main():
    build()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "entry.png")
    n = write_png(path, W, H, bytes(buf))
    print("wrote %s (%d bytes)" % (path, n))


if __name__ == "__main__":
    main()
