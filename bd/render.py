"""Build Different post renderer.

Renders a post spec (see content/SCHEMA.md) into 1080x1350 JPEG slides.
Everything is drawn at 2x and downsampled, so lines and shapes are smooth.
"""
import math
import os
import random
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- canvas ----
S = 2                      # supersampling factor
W1, H1 = 1080, 1350        # final size
W, H = W1 * S, H1 * S
M = 96                     # side margin (1x units)


def p(v):
    """1x units -> canvas pixels."""
    return int(round(v * S))


# ---------------------------------------------------------------- brand -----
BG_TOP = (9, 12, 17)
BG_BOT = (16, 22, 31)
PANEL = (20, 26, 36)
PANEL_HI = (34, 30, 22)       # amber-tinted panel for emphasis
AMBER = (242, 181, 68)
INK = (243, 241, 234)
INK2 = (206, 210, 218)        # secondary text
MUTED = (138, 147, 160)
FAINT = (58, 66, 78)
GRID = (36, 44, 56)
GRAY1 = (124, 135, 150)       # de-emphasised series
GRAY2 = (82, 92, 106)         # second de-emphasised series

FONT_DIRS = [
    "/usr/share/fonts/truetype/google-fonts",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts"),
]
_FONT_FILES = {
    "bold": "Poppins-Bold.ttf",
    "medium": "Poppins-Medium.ttf",
    "regular": "Poppins-Regular.ttf",
    "light": "Poppins-Light.ttf",
}
_font_cache = {}


def font(weight, size):
    """Poppins at `size` (1x units)."""
    key = (weight, size)
    if key not in _font_cache:
        fname = _FONT_FILES[weight]
        for d in FONT_DIRS:
            path = os.path.join(d, fname)
            if os.path.exists(path):
                _font_cache[key] = ImageFont.truetype(path, p(size))
                break
        else:
            raise FileNotFoundError(f"Font {fname} not found in {FONT_DIRS}")
    return _font_cache[key]


# ------------------------------------------------------------ background ----
_bg_cache = {}


def background(glow=True, curve_seed=None):
    key = (glow, curve_seed)
    if key in _bg_cache:
        return _bg_cache[key].copy()
    t = np.linspace(0, 1, H)[:, None]
    top, bot = np.array(BG_TOP, float), np.array(BG_BOT, float)
    grad = (top + (bot - top) * t[..., None]).astype(np.uint8)
    grad = np.repeat(grad, W, axis=1)
    img = Image.fromarray(grad, "RGB").convert("RGBA")

    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    step = p(90)
    for x in range(0, W + 1, step):
        g.line([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=S)
    for y in range(0, H + 1, step):
        g.line([(0, y), (W, y)], fill=(255, 255, 255, 8), width=S)
    img = Image.alpha_composite(img, grid)

    if glow:
        gl = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        cx, cy, r = (W1 - 80) * S / 4, 120 * S / 4, 260 * S / 4
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=AMBER + (34,))
        gl = gl.filter(ImageFilter.GaussianBlur(r * 0.6)).resize((W, H), Image.BILINEAR)
        img = Image.alpha_composite(img, gl)

    if curve_seed is not None:
        img = _decor_curve(img, curve_seed)
    _bg_cache[key] = img
    return img.copy()


def _decor_curve(img, seed, y_base=None, amp=280, alpha=60):
    """Faint rising line along the bottom. Decorative, not data."""
    rnd = random.Random(seed)
    n, v, vals = 60, 0.0, []
    for _ in range(n + 1):
        v += rnd.uniform(-0.9, 1.25)
        vals.append(v)
    lo, hi = min(vals), max(vals)
    y_base = y_base if y_base is not None else H1 - 170
    pts = [(p(-20 + (W1 + 40) * i / n), p(y_base - (val - lo) / (hi - lo + 1e-9) * amp))
           for i, val in enumerate(vals)]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon(pts + [(W + p(20), H), (-p(20), H)], fill=AMBER + (int(alpha * 0.2),))
    d.line(pts, fill=AMBER + (alpha,), width=p(3), joint="curve")
    return Image.alpha_composite(img, layer)


# ------------------------------------------------------------------ text ----
def tracked(d, xy, text, fnt, fill, tracking):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + p(tracking)
    return x


def tracked_width(d, text, fnt, tracking):
    if not text:
        return 0
    return sum(d.textlength(ch, font=fnt) + p(tracking) for ch in text) - p(tracking)


_HL = re.compile(r"\*\*(.+?)\*\*")


def rich_tokens(text):
    """Split into words; each word is a list of (segment, highlighted) so that punctuation
    touching a **highlight** stays attached: '**50%**.' -> [[('50%',True),('.',False)]]"""
    segs, pos = [], 0
    for m in _HL.finditer(text):
        if m.start() > pos:
            segs.append((text[pos:m.start()], False))
        segs.append((m.group(1), True))
        pos = m.end()
    if pos < len(text):
        segs.append((text[pos:], False))
    words, cur = [], []
    for s, hl in segs:
        for part in re.split(r"(\s+)", s):
            if not part:
                continue
            if part.isspace():
                if cur:
                    words.append(cur)
                    cur = []
            else:
                cur.append((part, hl))
    if cur:
        words.append(cur)
    return words


def word_width(d, word, fnt):
    return sum(d.textlength(s, font=fnt) for s, _ in word)


def wrap_tokens(d, words, fnt, max_w):
    space = d.textlength(" ", font=fnt)
    lines, cur, cur_w = [], [], 0.0
    for w in words:
        ww = word_width(d, w, fnt)
        add = ww if not cur else space + ww
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [w], ww
        else:
            cur.append(w)
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


def line_width(d, line, fnt):
    space = d.textlength(" ", font=fnt)
    return sum(word_width(d, w, fnt) for w in line) + space * max(0, len(line) - 1)


def draw_lines(d, x, y, lines, fnt, lh, color=INK, hl_color=AMBER, align="left", box_w=None):
    space = d.textlength(" ", font=fnt)
    for line in lines:
        lx = x
        if align == "center" and box_w:
            lx = x + (box_w - line_width(d, line, fnt)) / 2
        for w in line:
            for s, hl in w:
                d.text((lx, y), s, font=fnt, fill=hl_color if hl else color)
                lx += d.textlength(s, font=fnt)
            lx += space
        y += lh
    return y


def fit_text(d, text, weight, sizes, max_w, max_h, lh_mult=1.18):
    """Largest size from `sizes` whose wrapped text fits the box."""
    tokens = rich_tokens(text)
    for s in sizes:
        f = font(weight, s)
        lines = wrap_tokens(d, tokens, f, p(max_w))
        lh = p(s * lh_mult)
        if lh * len(lines) <= p(max_h):
            return f, lines, lh
    f = font(weight, sizes[-1])
    return f, wrap_tokens(d, tokens, f, p(max_w)), p(sizes[-1] * lh_mult)


def paragraphs(d, x, y, text, size, max_w, color=INK2, weight="regular", lh_mult=1.45, gap=18,
               bullet_color=AMBER):
    """Draw paragraphs separated by '\\n'. Lines starting with '- ' become bullets."""
    f = font(weight, size)
    lh = p(size * lh_mult)
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("- "):
            r = p(5)
            cy = y + lh / 2 - p(size * 0.05)
            d.ellipse([x + p(4), cy - r, x + p(4) + 2 * r, cy + r], fill=bullet_color)
            lines = wrap_tokens(d, rich_tokens(para[2:]), f, p(max_w - 34))
            y = draw_lines(d, x + p(34), y, lines, f, lh, color=color)
        else:
            lines = wrap_tokens(d, rich_tokens(para), f, p(max_w))
            y = draw_lines(d, x, y, lines, f, lh, color=color)
        y += p(gap)
    return y


def measure_paragraphs(d, text, size, max_w, lh_mult=1.45, gap=18, weight="regular"):
    f = font(weight, size)
    lh = p(size * lh_mult)
    h = 0
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        w = max_w - 34 if para.startswith("- ") else max_w
        t = para[2:] if para.startswith("- ") else para
        h += lh * len(wrap_tokens(d, rich_tokens(t), f, p(w))) + p(gap)
    return h


# ------------------------------------------------------------- chrome -------
def header(d, label):
    f = font("medium", 26)
    d.rectangle([p(M), p(118), p(M + 44), p(124)], fill=AMBER)
    tracked(d, (p(M + 62), p(102)), "BUILD DIFFERENT", f, INK, 6)
    if label:
        fl = font("medium", 22)
        lw = tracked_width(d, label.upper(), fl, 4)
        tracked(d, (p(W1 - M) - lw, p(106)), label.upper(), fl, MUTED, 4)


def footer(d, idx, total, note="Education, not advice"):
    fy = H1 - 118
    d.line([(p(M), p(fy - 32)), (p(W1 - M), p(fy - 32))], fill=(46, 54, 66), width=p(2))
    d.text((p(M), p(fy - 6)), "@builddifferent.trading", font=font("medium", 28), fill=INK)
    right = f"{note}   {idx}/{total}" if note else f"{idx}/{total}"
    fr = font("regular", 23)
    rw = d.textlength(right, font=fr)
    d.text((p(W1 - M) - rw, p(fy - 2)), right, font=fr, fill=MUTED)


def kicker(d, x, y, text):
    f = font("medium", 24)
    return tracked(d, (p(x), p(y)), text.upper(), f, AMBER, 5)


# ------------------------------------------------------------ slides --------
def slide_cover(spec, ctx):
    img = background(glow=True, curve_seed=ctx["seed"])
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    top = 250
    if spec.get("kicker"):
        kicker(d, M, top, spec["kicker"])
        top += 70
    f, lines, lh = fit_text(d, spec["title"], "bold", [96, 90, 84, 78, 72, 66, 60], W1 - 2 * M, 560)
    y = draw_lines(d, p(M), p(top), lines, f, lh)
    if spec.get("sub"):
        y += p(34)
        fs = font("regular", 36)
        sub_lines = wrap_tokens(d, rich_tokens(spec["sub"]), fs, p(W1 - 2 * M))
        draw_lines(d, p(M), y, sub_lines, fs, p(52), color=INK2)
    # swipe cue
    cue = spec.get("cue", "Swipe")
    fc = font("medium", 28)
    cw = d.textlength(cue, font=fc)
    cx = p(W1 - M) - cw - p(56)
    cy = p(H1 - 262)
    d.text((cx, cy), cue, font=fc, fill=AMBER)
    ax = cx + cw + p(16)
    ay = cy + p(22)
    d.line([(ax, ay), (ax + p(36), ay)], fill=AMBER, width=p(4))
    d.polygon([(ax + p(40), ay), (ax + p(26), ay - p(10)), (ax + p(26), ay + p(10))], fill=AMBER)
    footer(d, ctx["idx"], ctx["total"])
    return img


def _title_block(d, spec, top=200, size_range=(58, 54, 50, 46, 42), max_h=150):
    y = p(top)
    if spec.get("kicker"):
        kicker(d, M, top, spec["kicker"])
        y = p(top + 56)
    f, lines, lh = fit_text(d, spec["title"], "bold", list(size_range), W1 - 2 * M, max_h)
    return draw_lines(d, p(M), y, lines, f, lh)


def slide_text(spec, ctx):
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, max_h=230)
    y += p(36)
    body = spec.get("body", "")
    size = 38
    call_h = _callout_height(d, spec["callout"]) + p(56) if spec.get("callout") else 0
    avail = (H1 - 196) * S - y - call_h
    while size > 28 and measure_paragraphs(d, body, size, W1 - 2 * M) > avail:
        size -= 2
    y = paragraphs(d, p(M), y, body, size, W1 - 2 * M)
    if spec.get("callout"):
        _callout(d, spec["callout"], y_top=y + p(30))
    footer(d, ctx["idx"], ctx["total"])
    return img


def _callout_lines(d, text):
    f = font("medium", 34)
    return f, wrap_tokens(d, rich_tokens(text), f, p(W1 - 2 * M - 70)), p(48)


def _callout_height(d, text):
    _, lines, lh = _callout_lines(d, text)
    return lh * len(lines) + p(56)


def _callout(d, text, y_top):
    f, lines, lh = _callout_lines(d, text)
    h = lh * len(lines) + p(56)
    y0 = min(y_top, p(H1 - 196) - h)
    d.rounded_rectangle([p(M), y0, p(W1 - M), y0 + h], radius=p(18), fill=PANEL_HI)
    d.rounded_rectangle([p(M), y0, p(M + 8), y0 + h], radius=p(4), fill=AMBER)
    draw_lines(d, p(M + 44), y0 + p(26), lines, f, lh, color=INK)


def slide_checklist(spec, ctx):
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, max_h=230)
    y += p(44)
    items = spec["items"]
    size = 40 if len(items) <= 4 else 36
    text_w = W1 - 2 * M - 92

    def total_h(sz):
        f = font("regular", sz)
        return sum(max(p(64), p(sz * 1.4) * len(wrap_tokens(d, rich_tokens(it), f, p(text_w)))) + p(30)
                   for it in items)

    avail = (H1 - 200) * S - y
    while size > 26 and total_h(size) > avail:
        size -= 2
    f = font("regular", size)
    lh = p(size * 1.4)
    fn = font("bold", 28)
    for i, it in enumerate(items, 1):
        r = p(28)
        cx, cy = p(M) + r, y + r
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=AMBER)
        num = str(i)
        nb = d.textbbox((0, 0), num, font=fn)
        d.text((cx - (nb[2] - nb[0]) / 2 - nb[0], cy - (nb[3] - nb[1]) / 2 - nb[1]), num, font=fn,
               fill=BG_TOP)
        lines = wrap_tokens(d, rich_tokens(it), f, p(text_w))
        ty = y + (p(64) - lh) / 2 if len(lines) == 1 else y
        end = draw_lines(d, p(M + 92), ty, lines, f, lh, color=INK)
        y = max(end, y + p(64)) + p(30)
    footer(d, ctx["idx"], ctx["total"])
    return img


def slide_stat(spec, ctx):
    img = background(glow=True)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = p(230)
    if spec.get("kicker"):
        kicker(d, M, 230, spec["kicker"])
        y = p(300)
    fv = font("bold", 210)
    d.text((p(M) - p(8), y), spec["value"], font=fv, fill=INK)
    vb = d.textbbox((p(M) - p(8), y), spec["value"], font=fv)
    y = vb[3] + p(30)
    d.rectangle([p(M), y, p(M + 120), y + p(10)], fill=AMBER)
    y += p(56)
    f, lines, lh = fit_text(d, spec["label"], "bold", [52, 48, 44, 40], W1 - 2 * M, 200)
    y = draw_lines(d, p(M), y, lines, f, lh)
    if spec.get("body"):
        y += p(30)
        paragraphs(d, p(M), y, spec["body"], 34, W1 - 2 * M)
    footer(d, ctx["idx"], ctx["total"])
    return img


def slide_formula(spec, ctx):
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, max_h=150)
    y += p(40)
    # formula card: each '\n'-separated line must fit on one row
    raw_lines = [ln.strip() for ln in spec["formula"].split("\n") if ln.strip()]
    inner_w = W1 - 2 * M - 96
    for size in (50, 46, 42, 38, 34, 31, 28):
        ff = font("bold", size)
        if all(line_width(d, w, ff) <= p(inner_w) for w in (rich_tokens(ln) for ln in raw_lines)):
            break
    flh = p(size * 1.3)
    flines = [rich_tokens(ln) for ln in raw_lines]
    card_h = flh * len(flines) + p(92)
    d.rounded_rectangle([p(M), y, p(W1 - M), y + card_h], radius=p(22), fill=PANEL_HI)
    draw_lines(d, p(M + 48), y + p(46), flines, ff, flh, color=INK, align="center", box_w=p(inner_w))
    y += card_h + p(48)
    if spec.get("body"):
        paragraphs(d, p(M), y, spec["body"], 34, W1 - 2 * M)
    footer(d, ctx["idx"], ctx["total"])
    return img


def slide_compare(spec, ctx):
    """Two side-by-side cards: {'cards': [{'name','rows':[[k,v],...],'result','result_label','good':bool}]}"""
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, max_h=150)
    y += p(44)
    gap = 28
    cw = (W1 - 2 * M - gap) / 2
    card_top = y
    card_h = p(700)
    for i, card in enumerate(spec["cards"]):
        x0 = M + i * (cw + gap)
        good = card.get("good", False)
        d.rounded_rectangle([p(x0), card_top, p(x0 + cw), card_top + card_h], radius=p(22),
                            fill=PANEL_HI if good else PANEL)
        cy = card_top + p(40)
        d.text((p(x0 + 36), cy), card["name"], font=font("bold", 38), fill=INK)
        cy += p(76)
        fk, fv = font("regular", 27), font("medium", 32)
        for k, v in card["rows"]:
            d.text((p(x0 + 36), cy), k, font=fk, fill=MUTED)
            d.text((p(x0 + 36), cy + p(36)), v, font=fv, fill=INK)
            cy += p(96)
        cy += p(6)
        d.line([(p(x0 + 36), cy), (p(x0 + cw - 36), cy)], fill=FAINT, width=p(2))
        cy += p(26)
        d.text((p(x0 + 36), cy), card.get("result_label", "Expected per trade"), font=fk, fill=MUTED)
        d.text((p(x0 + 36), cy + p(36)), card["result"], font=font("bold", 52), fill=INK)
        # status pill with icon + label (never colour alone)
        pill = card.get("pill")
        if pill:
            fp = font("medium", 22)
            neutral = card.get("neutral", False)
            text_x = p(x0 + 56) if neutral else p(x0 + 84)
            pw = d.textlength(pill, font=fp) + (p(40) if neutral else p(64))
            py = card_top + card_h - p(70)
            d.rounded_rectangle([p(x0 + 36), py, p(x0 + 36) + pw, py + p(44)], radius=p(22),
                                fill=AMBER if good else GRAY2)
            if not neutral:
                mx, my = p(x0 + 58), py + p(22)
                col = BG_TOP if good else INK
                if good:   # tick
                    d.line([(mx - p(9), my), (mx - p(3), my + p(7)), (mx + p(10), my - p(8))], fill=col,
                           width=p(4), joint="curve")
                else:      # cross
                    d.line([(mx - p(7), my - p(7)), (mx + p(7), my + p(7))], fill=col, width=p(4))
                    d.line([(mx - p(7), my + p(7)), (mx + p(7), my - p(7))], fill=col, width=p(4))
            d.text((text_x, py + p(9)), pill, font=fp, fill=BG_TOP if good else INK)
    y = card_top + card_h + p(44)
    if spec.get("body"):
        paragraphs(d, p(M), y, spec["body"], 32, W1 - 2 * M)
    footer(d, ctx["idx"], ctx["total"])
    return img


def slide_matrix(spec, ctx):
    """2x2 grid. spec: x_axis [left,right], y_axis [top,bottom], cells [[tl,tr],[bl,br]] each {'title','sub'},
    highlight: [row,col] (optional)."""
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, max_h=150)
    y += p(70)
    axis_w = 70
    gx0 = M + axis_w
    gw = W1 - M - gx0
    cell_gap = 18
    cw = (gw - cell_gap) / 2
    ch = 300
    fa = font("medium", 24)
    # column headers
    for j, lab in enumerate(spec["x_axis"]):
        tw = tracked_width(d, lab.upper(), fa, 3)
        tracked(d, (p(gx0 + j * (cw + cell_gap) + cw / 2) - tw / 2, y - p(46)), lab.upper(), fa, MUTED, 3)
    hl = tuple(spec.get("highlight", (-1, -1)))
    for i in range(2):
        for j in range(2):
            x0 = gx0 + j * (cw + cell_gap)
            y0 = y + p(i * (ch + cell_gap))
            cell = spec["cells"][i][j]
            fill = PANEL_HI if (i, j) == hl else PANEL
            d.rounded_rectangle([p(x0), y0, p(x0 + cw), y0 + p(ch)], radius=p(20), fill=fill)
            ft, lines, lh = fit_text(d, cell["title"], "bold", [40, 36, 32], cw - 60, 110)
            ty = draw_lines(d, p(x0 + 30), y0 + p(34), lines, ft, lh, color=INK)
            fs = font("regular", 27)
            sl = wrap_tokens(d, rich_tokens(cell.get("sub", "")), fs, p(cw - 60))
            draw_lines(d, p(x0 + 30), ty + p(12), sl, fs, p(38), color=INK2)
    # row labels (rotated)
    for i, lab in enumerate(spec["y_axis"]):
        tw = int(tracked_width(d, lab.upper(), fa, 3)) + p(8)
        th = p(40)
        tmp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        tracked(td, (0, 0), lab.upper(), fa, MUTED, 3)
        rot = tmp.rotate(90, expand=True)
        cy = y + p(i * (ch + cell_gap) + ch / 2)
        img.alpha_composite(rot, (p(M + 8), int(cy - rot.height / 2)))
    y_after = y + p(2 * ch + cell_gap) + p(50)
    if spec.get("body"):
        paragraphs(d, p(M), y_after, spec["body"], 32, W1 - 2 * M)
    footer(d, ctx["idx"], ctx["total"])
    return img


def _arrow(d, a, b, color, width, head=16):
    d.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    hl = p(head)
    left = (b[0] - hl * math.cos(ang - 0.45), b[1] - hl * math.sin(ang - 0.45))
    right = (b[0] - hl * math.cos(ang + 0.45), b[1] - hl * math.sin(ang + 0.45))
    d.polygon([b, left, right], fill=color)


def slide_cycle(spec, ctx):
    """Loop of 3-5 steps around a circle. spec: steps [str], center str."""
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, max_h=150)
    steps = spec["steps"]
    n = len(steps)
    cx, cy = W1 / 2, (y / S) + 420
    R = 300
    node_w, node_h = 330, 130
    centers = []
    for k in range(n):
        a = -math.pi / 2 + 2 * math.pi * k / n
        centers.append((cx + R * math.cos(a), cy + R * math.sin(a)))
    # arrows along the circle between nodes
    for k in range(n):
        a0 = -math.pi / 2 + 2 * math.pi * k / n
        a1 = -math.pi / 2 + 2 * math.pi * (k + 1) / n
        span = a1 - a0
        s0, s1 = a0 + span * 0.30, a1 - span * 0.30
        pts = [(p(cx + R * math.cos(s0 + (s1 - s0) * t / 20)), p(cy + R * math.sin(s0 + (s1 - s0) * t / 20)))
               for t in range(21)]
        d.line(pts[:-1], fill=FAINT, width=p(5), joint="curve")
        _arrow(d, pts[-3], pts[-1], FAINT, p(5), head=18)
    fs = font("medium", 29)
    for k, (x, yy) in enumerate(centers):
        fill = PANEL_HI if k == spec.get("highlight", -1) else PANEL
        d.rounded_rectangle([p(x - node_w / 2), p(yy - node_h / 2), p(x + node_w / 2), p(yy + node_h / 2)],
                            radius=p(22), fill=fill)
        d.text((p(x - node_w / 2 + 22), p(yy - node_h / 2 + 14)), str(k + 1), font=font("bold", 24), fill=AMBER)
        lines = wrap_tokens(d, rich_tokens(steps[k]), fs, p(node_w - 60))
        lh = p(38)
        ty = p(yy) - lh * len(lines) / 2 + p(8)
        draw_lines(d, p(x - node_w / 2 + 30), ty, lines, fs, lh, color=INK, align="center",
                   box_w=p(node_w - 60))
    if spec.get("center"):
        fc = font("bold", 34)
        lines = wrap_tokens(d, rich_tokens(spec["center"]), fc, p(250))
        lh = p(44)
        draw_lines(d, p(cx - 125), p(cy) - lh * len(lines) / 2, lines, fc, lh, color=AMBER, align="center",
                   box_w=p(250))
    if spec.get("body"):
        paragraphs(d, p(M), p(cy + R + node_h / 2 + 50), spec["body"], 32, W1 - 2 * M)
    footer(d, ctx["idx"], ctx["total"])
    return img


def slide_windows(spec, ctx):
    """Walk-forward style timeline. spec: total (int), rows [[train_start, train_end, test_end], ...],
    labels {'train','test'}, axis_label"""
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, max_h=150)
    y += p(60)
    total = spec["total"]
    rows = spec["rows"]
    left = M + 130
    right = W1 - M
    span = right - left
    bar_h = 54
    gap = 26
    fl = font("medium", 24)
    # legend
    lx = p(M)
    for lab, col in ((spec.get("labels", {}).get("train", "Build (in-sample)"), GRAY2),
                     (spec.get("labels", {}).get("test", "Test (out-of-sample)"), AMBER)):
        d.rounded_rectangle([lx, y, lx + p(40), y + p(22)], radius=p(4), fill=col)
        d.text((lx + p(54), y - p(6)), lab, font=fl, fill=INK2)
        lx += p(54) + d.textlength(lab, font=fl) + p(48)
    y += p(70)
    for i, (a, b, c) in enumerate(rows):
        yy = y + p(i * (bar_h + gap))
        d.text((p(M), yy + p(12)), f"Round {i + 1}", font=fl, fill=MUTED)
        xa = left + span * a / total
        xb = left + span * b / total
        xc = left + span * c / total
        d.rounded_rectangle([p(xa), yy, p(xb) - p(2), yy + p(bar_h)], radius=p(8), fill=GRAY2)
        d.rounded_rectangle([p(xb) + p(2), yy, p(xc), yy + p(bar_h)], radius=p(8), fill=AMBER)
    yy = y + p(len(rows) * (bar_h + gap)) + p(4)
    d.line([(p(left), yy), (p(right), yy)], fill=FAINT, width=p(2))
    if spec.get("axis_label"):
        fa = font("regular", 24)
        aw = d.textlength(spec["axis_label"], font=fa)
        d.text((p(right) - aw, yy + p(14)), spec["axis_label"], font=fa, fill=MUTED)
    if spec.get("body"):
        paragraphs(d, p(M), yy + p(80), spec["body"], 32, W1 - 2 * M)
    footer(d, ctx["idx"], ctx["total"])
    return img


def slide_cta(spec, ctx):
    img = background(glow=True, curve_seed=ctx["seed"] + 1)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    title = spec.get("title", "Found this useful?")
    f, lines, lh = fit_text(d, title, "bold", [80, 72, 64], W1 - 2 * M, 200)
    y = draw_lines(d, p(M), p(250), lines, f, lh)
    y += p(56)
    actions = spec.get("actions") or [
        ["Save", "Keep it for your next trading session"],
        ["Share", "Send it to a trader who needs it"],
        ["Follow", "@builddifferent.trading for a new lesson every day"],
    ]
    for k, (a, b) in enumerate(actions):
        d.rounded_rectangle([p(M), y, p(W1 - M), y + p(128)], radius=p(20), fill=PANEL)
        d.rounded_rectangle([p(M + 28), y + p(40), p(M + 76), y + p(88)], radius=p(10), fill=AMBER)
        fn = font("bold", 26)
        num = str(k + 1)
        nb = d.textbbox((0, 0), num, font=fn)
        d.text((p(M + 52) - (nb[2] - nb[0]) / 2 - nb[0], y + p(64) - (nb[3] - nb[1]) / 2 - nb[1]), num,
               font=fn, fill=BG_TOP)
        d.text((p(M + 104), y + p(22)), a, font=font("bold", 36), fill=INK)
        d.text((p(M + 104), y + p(72)), b, font=font("regular", 27), fill=INK2)
        y += p(150)
    y += p(20)
    disc = spec.get("disclaimer", "Educational content only. Not investment advice or a recommendation to "
                                  "buy or sell any security. Not SEBI-registered. Markets carry risk; "
                                  "do your own research.")
    fd = font("regular", 23)
    dl = wrap_tokens(d, rich_tokens(disc), fd, p(W1 - 2 * M))
    draw_lines(d, p(M), y, dl, fd, p(34), color=MUTED)
    footer(d, ctx["idx"], ctx["total"], note=None)
    return img


# ------------------------------------------------------------ charts --------
def nice_ticks(lo, hi, n=5):
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / max(1, n)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 10))
        v += step
    return ticks


def fmt(v, pattern):
    """Format a number; negatives get a true minus sign in front of any prefix (−₹50k, not ₹-50k)."""
    try:
        if isinstance(v, (int, float)) and v < 0:
            s = pattern.format(abs(v))
            return "−" + (s[1:] if s.startswith("+") else s)
        return pattern.format(v)
    except (ValueError, KeyError, IndexError):
        return str(v)


def chart_line(d, img, spec, box):
    """box = (x0,y0,x1,y1) in canvas px."""
    x0, y0, x1, y1 = box
    series = spec["series"]
    xs = spec["x"]
    y_all = [v for s in series for v in s["values"] if v is not None]
    y_lo = spec.get("y_min", min(y_all))
    y_hi = spec.get("y_max", max(y_all))
    yt = spec["y_ticks"] if spec.get("y_ticks") else nice_ticks(y_lo, y_hi, spec.get("y_tick_count", 5))
    y_lo, y_hi = min(yt[0], y_lo), max(yt[-1], y_hi)
    xt = spec["x_ticks"] if "x_ticks" in spec else nice_ticks(min(xs), max(xs), spec.get("x_tick_count", 5))
    xt = [t for t in xt if min(xs) <= t <= max(xs)]
    x_lo, x_hi = min(xs), max(xs)
    ft = font("regular", 24)
    yfmt = spec.get("y_format", "{:g}")
    xfmt = spec.get("x_format", "{:g}")
    ylab_w = max(d.textlength(fmt(t, yfmt), font=ft) for t in yt)
    multi = len(series) > 1
    legend_h = p(60) if multi else 0
    pl = x0 + ylab_w + p(22)
    fe = font("medium", 24)
    end_w = max((d.textlength(s["end_label"], font=fe) for s in series if s.get("end_label")), default=0)
    pr = x1 - (end_w + p(44) if end_w else p(spec.get("right_pad", 20)))
    pt = y0 + legend_h + p(16)
    pb = y1 - p(40) - (p(40) if spec.get("x_label") else 0)

    rev = spec.get("x_reverse", False)

    def X(v):
        f = (v - x_lo) / (x_hi - x_lo)
        return pl + ((1 - f) if rev else f) * (pr - pl)

    def Y(v):
        return pb - (v - y_lo) / (y_hi - y_lo) * (pb - pt)

    # shaded regions
    for r in spec.get("regions", []):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rectangle([X(r["x0"]), pt, X(r["x1"]), pb], fill=(255, 255, 255, 10))
        img.alpha_composite(layer)
        if r.get("label"):
            fr = font("medium", 22)
            lw = tracked_width(d, r["label"].upper(), fr, 3)
            ly = pb - p(38) if r.get("label_pos") == "bottom" else pt + p(10)
            tracked(d, ((X(r["x0"]) + X(r["x1"])) / 2 - lw / 2, ly), r["label"].upper(), fr, MUTED, 3)
    # grid + y ticks
    for t in yt:
        yy = Y(t)
        d.line([(pl, yy), (pr, yy)], fill=GRID, width=p(2))
        lab = fmt(t, yfmt)
        lw = d.textlength(lab, font=ft)
        d.text((pl - p(14) - lw, yy - p(16)), lab, font=ft, fill=MUTED)
    if spec.get("zero_line") and y_lo < 0 < y_hi:
        d.line([(pl, Y(0)), (pr, Y(0))], fill=(96, 106, 120), width=p(3))
    # x ticks
    for t in xt:
        lab = fmt(t, xfmt)
        lw = d.textlength(lab, font=ft)
        d.text((X(t) - lw / 2, pb + p(12)), lab, font=ft, fill=MUTED)
    if spec.get("x_label"):
        fx = font("regular", 24)
        lw = d.textlength(spec["x_label"], font=fx)
        d.text(((pl + pr) / 2 - lw / 2, pb + p(50)), spec["x_label"], font=fx, fill=MUTED)
    # vertical reference lines
    for v in spec.get("vlines", []):
        xx = X(v["x"])
        d.line([(xx, pt), (xx, pb)], fill=(96, 106, 120), width=p(3))
        if v.get("label"):
            fv = font("medium", 22)
            lw = d.textlength(v["label"], font=fv)
            lx = xx + p(10) if v.get("side", "right") == "right" else xx - p(10) - lw
            ly = pb - p(38) if v.get("label_pos") == "bottom" else pt + p(8)
            d.text((lx, ly), v["label"], font=fv, fill=INK2)
    # series: de-emphasised first, focus on top
    grays = [GRAY1, GRAY2, (70, 78, 92)]
    colors = []
    gi = 0
    for s in series:
        if s.get("focus"):
            colors.append(AMBER)
        else:
            colors.append(grays[gi % len(grays)])
            gi += 1
    order = sorted(range(len(series)), key=lambda k: 1 if series[k].get("focus") else 0)
    for k in order:
        s = series[k]
        pts = [(X(x), Y(v)) for x, v in zip(xs, s["values"]) if v is not None]
        if s.get("focus") and spec.get("area", True):
            base = Y(max(y_lo, min(y_hi, spec.get("area_base", y_lo))))
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.polygon(pts + [(pts[-1][0], base), (pts[0][0], base)], fill=AMBER + (26,))
            img.alpha_composite(layer)
        d.line(pts, fill=colors[k], width=p(6 if s.get("focus") else 5), joint="curve")
        r = p(9)
        ex, ey = pts[-1]
        if spec.get("end_dots", True):
            ring = p(4)
            d.ellipse([ex - r - ring, ey - r - ring, ex + r + ring, ey + r + ring], fill=PANEL)
            d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=colors[k])
        if s.get("end_label"):
            # direct label in a text colour (never the series colour), right of the end point
            d.text((ex + p(22), ey - p(17)), s["end_label"], font=fe, fill=INK if s.get("focus") else INK2)
    # point annotations
    for a in spec.get("points", []):
        s = series[a.get("series", 0)]
        xi = xs.index(a["x"]) if a["x"] in xs else min(range(len(xs)), key=lambda i: abs(xs[i] - a["x"]))
        px_, py_ = X(xs[xi]), Y(s["values"][xi])
        r, ring = p(10), p(4)
        col = colors[a.get("series", 0)]
        d.ellipse([px_ - r - ring, py_ - r - ring, px_ + r + ring, py_ + r + ring], fill=PANEL)
        d.ellipse([px_ - r, py_ - r, px_ + r, py_ + r], fill=col)
        if a.get("label"):
            fa = font("medium", 24)
            lw = d.textlength(a["label"], font=fa)
            dx, dy = a.get("dx", 18), a.get("dy", -52)
            lx = px_ + p(dx) if dx >= 0 else px_ + p(dx) - lw
            lx = max(pl, min(lx, pr - lw))
            ly = py_ + p(dy)
            d.rounded_rectangle([lx - p(12), ly - p(6), lx + lw + p(12), ly + p(38)], radius=p(8), fill=PANEL)
            d.text((lx, ly), a["label"], font=fa, fill=INK)
    # legend (>=2 series)
    if multi:
        fl = font("medium", 24)
        lx = pl
        for k, s in enumerate(series):
            d.line([(lx, y0 + p(20)), (lx + p(36), y0 + p(20))], fill=colors[k], width=p(6))
            d.text((lx + p(48), y0 + p(4)), s["name"], font=fl, fill=INK2)
            lx += p(48) + d.textlength(s["name"], font=fl) + p(40)


def chart_bar(d, img, spec, box):
    x0, y0, x1, y1 = box
    cats, vals = spec["categories"], spec["values"]
    n = len(cats)
    hl = set(spec.get("highlight", []))
    if "highlight_range" in spec:
        a, b = spec["highlight_range"]
        hl |= set(range(a, b + 1))
    vmax = spec.get("y_max", max(0, max(vals)))
    vmin = spec.get("y_min", min(0, min(vals)))
    label_all = spec.get("label_all", n <= 8)
    show_axis = spec.get("show_y_axis", not label_all)
    ft = font("regular", 24)
    yfmt = spec.get("y_format", spec.get("value_format", "{:g}"))
    yt = nice_ticks(vmin, vmax, 4) if show_axis else []
    if yt:
        vmin, vmax = min(vmin, yt[0]), max(vmax, yt[-1])
    ylab_w = max((d.textlength(fmt(t, yfmt), font=ft) for t in yt), default=0)
    pl = x0 + (ylab_w + p(22) if show_axis else p(4))
    pr = x1 - p(4)
    pt = y0 + p(64)
    pb = y1 - p(52) - (p(40) if spec.get("x_label") else 0)

    def Y(v):
        return pb - (v - vmin) / (vmax - vmin) * (pb - pt)

    for t in yt:
        yy = Y(t)
        d.line([(pl, yy), (pr, yy)], fill=GRID, width=p(2))
        lab = fmt(t, yfmt)
        d.text((pl - p(14) - d.textlength(lab, font=ft), yy - p(16)), lab, font=ft, fill=MUTED)
    slot = (pr - pl) / n
    bw = min(slot * spec.get("bar_ratio", 0.56), p(96))
    base = Y(0)
    fv = font("bold", 28 if n <= 8 else 22)
    every = spec.get("label_every", 1)
    for i, (c, v) in enumerate(zip(cats, vals)):
        cx = pl + slot * (i + 0.5)
        col = AMBER if (i in hl or not hl) else GRAY2
        top = Y(v)
        rad = min(p(10), int(bw / 2))
        if v >= 0:
            d.rounded_rectangle([cx - bw / 2, top, cx + bw / 2, base], radius=rad, fill=col,
                                corners=(True, True, False, False))
        else:
            d.rounded_rectangle([cx - bw / 2, base, cx + bw / 2, top], radius=rad, fill=col,
                                corners=(False, False, True, True))
        if label_all or i in hl:
            lab = fmt(v, spec.get("value_format", "{:g}"))
            lw = d.textlength(lab, font=fv)
            ly = top - p(44) if v >= 0 else top + p(10)
            d.text((cx - lw / 2, ly), lab, font=fv, fill=INK if (i in hl or not hl) else INK2)
        if i % every == 0 or i in hl and spec.get("label_highlight_cats", False):
            cw_ = d.textlength(str(c), font=ft)
            d.text((cx - cw_ / 2, max(base, Y(vmin)) + p(12)), str(c), font=ft, fill=MUTED)
    d.line([(pl, base), (pr, base)], fill=(96, 106, 120), width=p(3))
    if spec.get("x_label"):
        fx = font("regular", 24)
        lw = d.textlength(spec["x_label"], font=fx)
        d.text(((pl + pr) / 2 - lw / 2, pb + p(54)), spec["x_label"], font=fx, fill=MUTED)


def chart_candles(d, img, spec, box):
    """Synthetic candles for illustration only. spec: seed, n, levels [{'y':value,'label':str,'focus':bool}]"""
    x0, y0, x1, y1 = box
    if spec.get("ohlc"):
        ohlc = [tuple(c) for c in spec["ohlc"]]
    else:
        rnd = random.Random(spec.get("seed", 7))
        ohlc, prev = [], spec.get("start", 100.0)
        for _ in range(spec.get("n", 24)):
            c = prev + rnd.uniform(-1.2, 1.3)
            o = prev + rnd.uniform(-0.3, 0.3)
            ohlc.append((o, max(o, c) + abs(rnd.gauss(0, 0.6)), min(o, c) - abs(rnd.gauss(0, 0.6)), c))
            prev = c
    n = len(ohlc)
    lo = min(l for _, _, l, _ in ohlc)
    hi = max(h for _, h, _, _ in ohlc)
    for lv in spec.get("levels", []):
        lo, hi = min(lo, lv["y"]), max(hi, lv["y"])
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    pl, pr, pt, pb = x0 + p(10), x1 - p(250), y0 + p(20), y1 - p(20)

    def Y(v):
        return pb - (v - lo) / (hi - lo) * (pb - pt)

    slot = (pr - pl) / n
    bw = slot * 0.62
    for i, (o, h, l, c) in enumerate(ohlc):
        cx = pl + slot * (i + 0.5)
        up = c >= o
        col = AMBER if up else GRAY1
        d.line([(cx, Y(h)), (cx, Y(l))], fill=col, width=p(3))
        top, bot = Y(max(o, c)), Y(min(o, c))
        if bot - top < p(3):
            bot = top + p(3)
        if up:
            d.rectangle([cx - bw / 2, top, cx + bw / 2, bot], fill=col)
        else:
            d.rectangle([cx - bw / 2, top, cx + bw / 2, bot], fill=BG_BOT, outline=col, width=p(3))
    for lv in spec.get("levels", []):
        yy = Y(lv["y"])
        col = INK if lv.get("focus") else (110, 120, 134)
        d.line([(pl, yy), (pr + p(10), yy)], fill=col, width=p(3))
        fl = font("medium" if lv.get("focus") else "regular", 24)
        d.rounded_rectangle([pr + p(20), yy - p(22), x1, yy + p(22)], radius=p(8),
                            fill=PANEL_HI if lv.get("focus") else PANEL)
        d.text((pr + p(34), yy - p(16)), lv["label"], font=fl, fill=INK if lv.get("focus") else INK2)


CHARTS = {"line": chart_line, "bar": chart_bar, "candles": chart_candles}


def slide_chart(spec, ctx):
    img = background(glow=False)
    d = ImageDraw.Draw(img)
    header(d, ctx["label"])
    y = _title_block(d, spec, top=190, size_range=(54, 50, 46, 42), max_h=140)
    if spec.get("body"):
        y += p(20)
        fb = font("regular", 32)
        lines = wrap_tokens(d, rich_tokens(spec["body"]), fb, p(W1 - 2 * M))[:3]
        y = draw_lines(d, p(M), y, lines, fb, p(46), color=INK2)
    y += p(30)
    note = spec.get("note")
    bottom = p(H1 - 190) - (p(52) if note else 0)
    # panel
    d.rounded_rectangle([p(M - 24), y, p(W1 - M + 24), bottom], radius=p(22), fill=PANEL)
    box = (p(M), y + p(30), p(W1 - M), bottom - p(24))
    if spec["chart"].get("title"):
        fc = font("medium", 26)
        d.text((box[0], box[1] - p(4)), spec["chart"]["title"], font=fc, fill=INK)
        box = (box[0], box[1] + p(48), box[2], box[3])
    CHARTS[spec["chart"]["kind"]](d, img, spec["chart"], box)
    if note:
        fn = font("regular", 22)
        d.text((p(M - 24), bottom + p(16)), note, font=fn, fill=MUTED)
    footer(d, ctx["idx"], ctx["total"])
    return img


SLIDES = {
    "cover": slide_cover,
    "text": slide_text,
    "checklist": slide_checklist,
    "stat": slide_stat,
    "formula": slide_formula,
    "compare": slide_compare,
    "matrix": slide_matrix,
    "cycle": slide_cycle,
    "windows": slide_windows,
    "chart": slide_chart,
    "cta": slide_cta,
}


def render_post(post, out_dir):
    """Render all slides of `post` into out_dir as 01.jpg, 02.jpg, ... Returns list of paths."""
    os.makedirs(out_dir, exist_ok=True)
    slides = post["slides"]
    total = len(slides)
    seed = sum(ord(c) for c in post["id"])
    paths = []
    for i, sp in enumerate(slides, 1):
        ctx = {"idx": i, "total": total, "label": post.get("label", ""), "seed": seed}
        img = SLIDES[sp["type"]](sp, ctx)
        out = img.convert("RGB").resize((W1, H1), Image.LANCZOS)
        path = os.path.join(out_dir, f"{i:02d}.jpg")
        out.save(path, "JPEG", quality=92, optimize=True)
        paths.append(path)
    return paths


def caption_text(post):
    parts = [post["caption"].strip()]
    parts.append("Education only, not investment advice. Not SEBI-registered.")
    tags = post.get("hashtags", [])[:5]
    if tags:
        parts.append(" ".join(tags))
    text = "\n\n".join(parts)
    if len(text) > 2200:
        raise ValueError(f"Caption too long ({len(text)} chars) for {post['id']}")
    return text
