"""Turn a post into a 9:16 Instagram Reel (MP4).

The slides are re-rendered losslessly from the post spec and shown as a card inside the Reels safe
zone, with carousel-style swipes between slides and story-style progress segments on top. Charts
draw themselves in: line and candle charts wipe in left to right, bars grow out of the baseline.

Output: 1080x1920, H.264 High, yuv420p (BT.709), 30 fps, silent stereo AAC, moov atom first.
"""
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import render as R

FW, FH = 1080, 1920
FPS = 30
CARD_W = 928                            # 86% of the slide: content stays clear of the like/comment column
CARD_H = round(CARD_W * R.H1 / R.W1)    # 1160
CARD_X = (FW - CARD_W) // 2
CARD_Y = 282                            # below the Reels top bar, above the caption area
RADIUS = 30
SWIPE = 0.45                            # seconds per slide change
REVEAL = {"line": 1.6, "candles": 1.7, "bar": 1.1}
REVEAL_DELAY = 0.25                     # chart axes show briefly before the data draws in
BAR_Y = CARD_Y - 34                     # progress segments


# ------------------------------------------------------------------ timing --
def _words(obj, skip=("type", "kind", "value_format", "y_format", "x_format")):
    if isinstance(obj, str):
        return len(obj.replace("**", "").split())
    if isinstance(obj, dict):
        return sum(_words(v) for k, v in obj.items() if k not in skip)
    if isinstance(obj, list):
        return sum(_words(v) for v in obj)
    return 0


def holds(post):
    """Seconds each slide stays on screen (transitions not included)."""
    out = []
    for i, sl in enumerate(post["slides"]):
        if i == 0:
            out.append(2.8)
        elif sl["type"] == "cta":
            out.append(3.0)
        else:
            t = min(7.0, max(3.5, 1.0 + 0.2 * _words(sl)))
            if sl["type"] == "chart":
                t += REVEAL.get(sl["chart"]["kind"], 1.5) + REVEAL_DELAY
            out.append(round(t, 2))
    return out


# ---------------------------------------------------------------- slides ---
def _render(post, i, show_data=True):
    sp = post["slides"][i]
    if sp["type"] == "cover":
        sp = dict(sp, cue="")                           # no "Swipe" cue in a video
    ctx = {"idx": i + 1, "total": len(post["slides"]), "label": post.get("label", ""),
           "seed": sum(ord(c) for c in post["id"])}
    R.SHOW_DATA = show_data
    try:
        img = R.SLIDES[sp["type"]](sp, ctx)
        geom = dict(R.GEOM)
    finally:
        R.SHOW_DATA = True
    return img.convert("RGB").resize((R.W1, R.H1), Image.LANCZOS), geom


def _to_card(img):
    return img.resize((CARD_W, CARD_H), Image.LANCZOS)


class Slide:
    """Card-sized frames for one slide: `at(t)` gives the card image t seconds into its hold."""

    def __init__(self, post, i):
        sp = post["slides"][i]
        full, geom = _render(post, i)
        self.full = _to_card(full)
        self.anim = None
        if sp["type"] == "chart":
            empty, _ = _render(post, i, show_data=False)
            diff = ImageChops.difference(full, empty).convert("L").point(lambda v: 255 if v > 8 else 0)
            box = diff.getbbox()
            if box:
                k = CARD_W / R.W1
                self.empty = _to_card(empty)
                self.box = tuple(int(round(v * k)) for v in box)
                self.kind = geom.get("kind", sp["chart"]["kind"])
                self.base = geom.get("base", 0) * k if self.kind == "bar" else None
                self.dur = REVEAL.get(self.kind, 1.5)
                self.anim = True

    def at(self, t):
        if not self.anim:
            return self.full
        q = (t - REVEAL_DELAY) / self.dur
        if q <= 0:
            return self.empty
        if q >= 1:
            return self.full
        q = _ease_out(q) if self.kind == "bar" else _ease_in_out(q)
        l, t_, r, b = self.box
        img = self.empty.copy()
        if self.kind == "bar":
            base = int(round(self.base))
            if base > t_:                                   # bars above the baseline grow up
                y = int(round(base - q * (base - t_)))
                img.paste(self.full.crop((l, y, r, base + 2)), (l, y))
            if b > base + 2:                                # negative bars grow down
                y = int(round(base + q * (b - base)))
                img.paste(self.full.crop((l, base, r, y)), (l, base))
        else:
            x = int(round(l + q * (r - l)))
            if x > l:
                img.paste(self.full.crop((l, t_, x, b)), (l, t_))
        return img

    def last(self):
        return self.full

    def first(self):
        return self.empty if self.anim else self.full


def _ease_in_out(q):
    return 4 * q ** 3 if q < 0.5 else 1 - (-2 * q + 2) ** 3 / 2


def _ease_out(q):
    return 1 - (1 - q) ** 3


# ----------------------------------------------------------------- frame ---
def _base():
    t = np.linspace(0, 1, FH)[:, None, None]
    top, bot = np.array((6, 8, 12), float), np.array((13, 17, 24), float)
    img = Image.fromarray(np.repeat((top + (bot - top) * t).astype(np.uint8), FW, axis=1), "RGB")
    shadow = Image.new("L", (FW, FH), 0)
    ImageDraw.Draw(shadow).rounded_rectangle(
        [CARD_X + 6, CARD_Y + 22, CARD_X + CARD_W - 6, CARD_Y + CARD_H + 22], radius=RADIUS, fill=170)
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    return Image.composite(Image.new("RGB", (FW, FH), (0, 0, 0)), img, shadow)


def _round_mask(outline=0):
    s = 4
    big = Image.new("L", (CARD_W * s, CARD_H * s), 0)
    d = ImageDraw.Draw(big)
    box = [0, 0, CARD_W * s - 1, CARD_H * s - 1]
    if outline:
        d.rounded_rectangle(box, radius=RADIUS * s, outline=255, width=outline * s)
    else:
        d.rounded_rectangle(box, radius=RADIUS * s, fill=255)
    return big.resize((CARD_W, CARD_H), Image.LANCZOS)


class Frame:
    def __init__(self):
        self.base = _base()
        self.mask = _round_mask()
        self.edge = _round_mask(outline=2)
        self.edge_col = Image.new("RGB", (CARD_W, CARD_H), (54, 63, 78))
        self.gap_bg = self.base.crop((CARD_X, CARD_Y, CARD_X + CARD_W, CARD_Y + CARD_H))

    def compose(self, card):
        f = self.base.copy()
        f.paste(card, (CARD_X, CARD_Y), self.mask)
        f.paste(self.edge_col, (CARD_X, CARD_Y), self.edge)
        return f

    def swipe(self, a, b, q):
        gap = 40
        off = int(round(q * (CARD_W + gap)))
        c = self.gap_bg.copy()
        c.paste(a, (-off, 0))
        c.paste(b, (CARD_W + gap - off, 0))
        return c

    @staticmethod
    def progress(f, idx, frac, n):
        d = ImageDraw.Draw(f)
        x0, x1, gap, h = CARD_X + 6, CARD_X + CARD_W - 6, 10, 6
        seg = (x1 - x0 - gap * (n - 1)) / n
        for k in range(n):
            a = x0 + k * (seg + gap)
            d.rounded_rectangle([a, BAR_Y, a + seg, BAR_Y + h], radius=3, fill=(46, 54, 66))
            fill = 1.0 if k < idx else (frac if k == idx else 0.0)
            if fill > 0:
                d.rounded_rectangle([a, BAR_Y, a + max(h, seg * fill), BAR_Y + h], radius=3, fill=R.AMBER)
        return f


# ------------------------------------------------------------------ build ---
def make_reel(post, out_path):
    """Render `post` to an MP4 at out_path. Returns (path, seconds)."""
    n = len(post["slides"])
    slides = [Slide(post, i) for i in range(n)]
    hold = holds(post)
    fr = Frame()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{FW}x{FH}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
           "-map", "0:v", "-map", "1:a", "-shortest",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "19",
           "-g", str(FPS * 2), "-keyint_min", str(FPS), "-bf", "2", "-r", str(FPS),
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = 0
    try:
        for i, sl in enumerate(slides):
            nf = int(round(hold[i] * FPS))
            static = None if sl.anim else fr.compose(sl.full)
            for f in range(nf):
                t = f / FPS
                img = static.copy() if static is not None else fr.compose(sl.at(t))
                fr.progress(img, i, (f + 1) / nf, n)
                proc.stdin.write(img.tobytes())
                frames += 1
            if i + 1 < n:
                a, b = sl.last(), slides[i + 1].first()
                ns = int(round(SWIPE * FPS))
                for f in range(ns):
                    q = _ease_in_out((f + 1) / (ns + 1))
                    img = fr.compose(fr.swipe(a, b, q))
                    fr.progress(img, i + 1, 0.0, n)
                    proc.stdin.write(img.tobytes())
                    frames += 1
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    finally:
        if proc.poll() is None:
            proc.kill()
    return out_path, frames / FPS


def probe(path):
    """Key stream facts for the Instagram Reels checks."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,sample_rate,channels"
                          ":format=duration,size", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def check_specs(path):
    """Return a list of problems against Instagram's Reels video specs (empty list = OK)."""
    info = probe(path)
    v = next(s for s in info["streams"] if s["codec_name"] == "h264")
    a = next((s for s in info["streams"] if s["codec_name"] == "aac"), None)
    dur, size = float(info["format"]["duration"]), int(info["format"]["size"])
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    problems = []
    if (v["width"], v["height"]) != (FW, FH):
        problems.append(f"size {v['width']}x{v['height']}")
    if v["pix_fmt"] != "yuv420p":
        problems.append(f"pix_fmt {v['pix_fmt']}")
    if not 23 <= num / den <= 60:
        problems.append(f"fps {num / den}")
    if not 5 <= dur <= 90:
        problems.append(f"duration {dur:.1f}s")
    if size > 100 * 1024 * 1024:
        problems.append(f"size {size / 1e6:.0f} MB")
    if a is None or int(a["sample_rate"]) > 48000:
        problems.append("audio track missing or >48 kHz")
    with open(path, "rb") as fh:                       # moov atom must come before mdat (faststart)
        head = fh.read(64 * 1024)
    if head.find(b"moov") == -1 or (head.find(b"mdat") != -1 and head.find(b"mdat") < head.find(b"moov")):
        problems.append("moov atom not at the front")
    return problems
