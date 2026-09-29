"""Short Reel format: 12-18 seconds, one idea.

  scene 0  full-screen hook in big type, with the lesson's chart drawing itself in from the first second
  scene 1+ one or two short text beats (lines that stack in, or one big takeaway)
  last     follow ending: "Follow for part 2" when the lesson is part 1 of a pair, else "Follow for more"

Driven by the lesson's `reel` script (content/SCHEMA.md). Sound comes from bd/sound.py and is cut to the
same beat grid, so whooshes land on scene changes and each stacked line gets its own note.
"""
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from . import render as R
from . import sound

FW, FH, FPS = 1080, 1920, 30
MX = 72                                   # side margin
CW = FW - 2 * MX                          # content width
HEADER_Y = 222
PROGRESS_Y = 290
TOP = 346                                 # first content row (below Instagram's top bar)
BOTTOM = 1440                             # last content row (above the caption area)
CHART_SCALE = 1.22                        # chart text 22% larger than on the carousel
ENTER, EXIT, STAGGER = 0.38, 0.26, 0.45
BEAT = sound.BEAT


def ease_out(q):
    q = min(1.0, max(0.0, q))
    return 1 - (1 - q) ** 3


def ease_in(q):
    q = min(1.0, max(0.0, q))
    return q * q


def ease_in_out(q):
    q = min(1.0, max(0.0, q))
    return 4 * q ** 3 if q < 0.5 else 1 - (-2 * q + 2) ** 3 / 2


def words(text):
    return len(text.replace("**", "").split())


def snap(seconds, minimum=4):
    return max(minimum, int(round(seconds / BEAT))) * BEAT


# ---------------------------------------------------------------- layers ---
class Layer:
    """RGBA image placed on the frame; kept premultiplied for fast compositing."""

    def __init__(self, img, x, y):
        a = np.asarray(img.convert("RGBA"), dtype=np.float32)
        self.A = a[..., 3] / 255.0
        self.P = a[..., :3] * self.A[..., None]
        self.x, self.y = x, y
        self.h, self.w = self.A.shape

    @property
    def bottom(self):
        return self.y + self.h

    def draw(self, frame, dx=0.0, dy=0.0, opacity=1.0, P=None):
        if opacity <= 0.003:
            return
        P = self.P if P is None else P
        x, y = int(round(self.x + dx)), int(round(self.y + dy))
        x0, y0, x1, y1 = max(0, x), max(0, y), min(FW, x + self.w), min(FH, y + self.h)
        if x1 <= x0 or y1 <= y0:
            return
        A = self.A[y0 - y:y1 - y, x0 - x:x1 - x] * opacity
        reg = frame[y0:y1, x0:x1]
        reg *= (1.0 - A)[..., None]
        reg += P[y0 - y:y1 - y, x0 - x:x1 - x] * opacity


_scratch = ImageDraw.Draw(Image.new("RGBA", (8, 8)))


def _text_image(lines, fnt, lh, color=R.INK, width=None):
    """Draw pre-wrapped rich-text lines at 2x and return the 1x RGBA image."""
    w2 = int(width * 2) if width else int(max(R.line_width(_scratch, ln, fnt) for ln in lines)) + R.p(10)
    h2 = int(lh * len(lines) + fnt.size * 0.42)
    img = Image.new("RGBA", (w2 + w2 % 2, h2 + h2 % 2), (0, 0, 0, 0))
    R.draw_lines(ImageDraw.Draw(img), 0, 0, lines, fnt, lh, color=color)
    return img.resize((img.width // 2, img.height // 2), Image.LANCZOS)


def text_layer(text, weight, sizes, max_w, max_h, x, y, color=R.INK, lh_mult=1.12):
    fnt, lines, lh = R.fit_text(_scratch, text, weight, sizes, max_w, max_h, lh_mult)
    return Layer(_text_image(lines, fnt, lh, color), x, y), fnt.size / 2


def one_row_size(texts, weight, sizes, max_w):
    """Largest size at which every text fits on one row (falls back to the smallest)."""
    for s in sizes:
        f = R.font(weight, s)
        if all(R.line_width(_scratch, [w for w in R.rich_tokens(t)], f) <= R.p(max_w) for t in texts):
            return s
    return sizes[-1]


def kicker_layer(text, x, y, color=R.AMBER, size=28, upper=True):
    text = text.upper() if upper else text
    f = R.font("medium", size)
    w = R.tracked_width(_scratch, text, f, 5 if upper else 1)
    img = Image.new("RGBA", (int(w) + R.p(8), R.p(size * 1.5)), (0, 0, 0, 0))
    R.tracked(ImageDraw.Draw(img), (0, 0), text, f, color, 5 if upper else 1)
    return Layer(img.resize((img.width // 2, img.height // 2), Image.LANCZOS), x, y)


def header_layer(label):
    img = Image.new("RGBA", (R.p(FW), R.p(56)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = R.font("medium", 26)
    d.rectangle([R.p(MX), R.p(24), R.p(MX + 44), R.p(30)], fill=R.AMBER)
    R.tracked(d, (R.p(MX + 62), R.p(8)), "BUILD DIFFERENT", f, R.INK, 6)
    if label:
        fl = R.font("medium", 22)
        lw = R.tracked_width(d, label.upper(), fl, 4)
        R.tracked(d, (R.p(FW - MX) - lw, R.p(12)), label.upper(), fl, R.MUTED, 4)
    return Layer(img.resize((FW, 56), Image.LANCZOS), 0, HEADER_Y)


# ---------------------------------------------------------------- chart ----
class ChartPanel:
    """The lesson's chart on a panel, drawn twice (ghost marks / full) and wiped in."""

    REVEAL = {"bar": 1.25, "line": 1.5, "candles": 1.6}
    timed = True

    def __init__(self, spec, note, x, y, w, h):
        k = CHART_SCALE
        vw, vh = w / k, h / k
        imgs, geoms = {}, {}
        for mode in ("ghost", True):
            R.SHOW_DATA = mode
            try:
                c = Image.new("RGBA", (R.p(vw), R.p(vh)), (0, 0, 0, 0))
                d = ImageDraw.Draw(c)
                d.rounded_rectangle([0, 0, c.width - 1, c.height - 1], radius=R.p(20), fill=R.PANEL + (255,))
                box = (R.p(24), R.p(22), c.width - R.p(24), c.height - R.p(12))
                if spec.get("title"):
                    d.text((box[0], box[1]), spec["title"], font=R.font("medium", 24), fill=R.INK)
                    box = (box[0], box[1] + R.p(46), box[2], box[3])
                R.CHARTS[spec["kind"]](d, c, spec, box)
                geoms[mode] = dict(R.GEOM)
            finally:
                R.SHOW_DATA = True
            imgs[mode] = c.resize((int(w), int(h)), Image.LANCZOS)
        self.s = w / (c.width / R.S)                      # virtual 1x units -> final px
        self.full = Layer(imgs[True], x, y)
        self.ghost_P = Layer(imgs["ghost"], x, y).P
        self.kind = spec["kind"]
        g = geoms[True]
        diff = np.abs(self.full.P - self.ghost_P).sum(axis=-1) > 12
        ys, xs = np.nonzero(diff)
        self.box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if len(xs) else None
        self.base = g.get("base", 0) * self.s if self.kind == "bar" else None
        self.focus = []                                   # ripple centres, frame coordinates
        if self.kind == "bar":
            for i in g.get("hl", []):
                cx, top, _ = g["bars"][i]
                self.focus.append((x + cx * self.s, y + (top - 22) * self.s))
        elif self.kind == "line":
            self.focus = [(x + px * self.s, y + py * self.s) for px, py in g.get("points", [])]
        self.note = None
        if note:
            self.note, _ = text_layer(note, "regular", [23, 21, 19], CW, 60, MX - 12 + 16, y + h + 14,
                                      color=R.MUTED, lh_mult=1.3)
        self.reveal_start = 0.15
        self.reveal = self.REVEAL.get(self.kind, 1.4)
        self.emph_at = self.reveal_start + self.reveal + 0.3

    @property
    def bottom(self):
        return self.note.bottom if self.note else self.full.bottom

    def P_at(self, t):
        q = (t - self.reveal_start) / self.reveal
        if self.box is None or q >= 1:
            return self.full.P
        if q <= 0:
            return self.ghost_P
        l, tp, r, b = self.box
        P = self.ghost_P.copy()
        if self.kind == "bar":
            q = ease_out(q)
            base = int(round(self.base))
            if base > tp:
                yw = int(round(base - q * (base - tp)))
                P[yw:base + 2, l:r] = self.full.P[yw:base + 2, l:r]
            if b > base + 2:
                yw = int(round(base + q * (b - base)))
                P[base:yw, l:r] = self.full.P[base:yw, l:r]
        else:
            xw = int(round(l + ease_in_out(q) * (r - l)))
            P[tp:b, l:xw] = self.full.P[tp:b, l:xw]
        return P

    def draw(self, frame, t, dx, dy, opacity):
        self.full.draw(frame, dx, dy, opacity, P=self.P_at(t))
        if self.note:
            self.note.draw(frame, dx, dy, opacity)
        for k, (cx, cy) in enumerate(self.focus[:3]):
            for j in range(2):                              # double ripple on each focus point
                u = (t - self.emph_at - 0.12 * k - 0.22 * j) / 0.75
                if 0 <= u <= 1:
                    ring(frame, cx + dx, cy + dy, 16 + 60 * ease_out(u), 5.0, R.AMBER, 0.9 * (1 - u) * opacity)


def ring(frame, cx, cy, r, width, color, alpha):
    R_ = int(r + width + 2)
    x0, y0 = max(0, int(cx - R_)), max(0, int(cy - R_))
    x1, y1 = min(FW, int(cx + R_ + 1)), min(FH, int(cy + R_ + 1))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    a = np.clip(width / 2 + 0.5 - np.abs(dist - r), 0, 1) * alpha
    reg = frame[y0:y1, x0:x1]
    reg *= (1 - a)[..., None]
    reg += a[..., None] * np.array(color, dtype=np.float32)


# ---------------------------------------------------------------- scenes ---
class Scene:
    """A set of elements with entrance delays. `first` scenes are visible from frame 0."""

    def __init__(self, duration):
        self.duration = duration
        self.items = []            # (drawable, delay)
        self.events = []           # (local time, kind, arg) for the sound

    def draw(self, frame, t, is_last, first=False):
        exit_q = 0.0 if is_last else ease_in((t - (self.duration - EXIT)) / EXIT)
        for obj, delay in self.items:
            e = 1.0 if first else ease_out((t - delay) / ENTER)
            if e <= 0:
                continue
            dy = 46 * (1 - e) - 64 * exit_q
            op = e * (1 - exit_q)
            if getattr(obj, "timed", False):
                obj.draw(frame, t, 0, dy, op)
            else:
                obj.draw(frame, 0, dy, op)


def _centre(layers, gaps):
    """Stack layers vertically (with gaps before each) and centre the stack between TOP and BOTTOM."""
    total = sum(l.h for l in layers) + sum(gaps)
    y = TOP + max(0, (BOTTOM - TOP - total) / 2) - 30
    for l, g in zip(layers, gaps):
        y += g
        l.y = int(y)
        y += l.h


def hook_scene(post, script):
    """Full-screen hook: kicker + the claim in the biggest type that fits, centred. Nothing else on screen,
    so the very first frame (also the grid thumbnail) reads in under a second."""
    kick = kicker_layer(script.get("kicker", post.get("pillar", "")), MX, TOP, size=32)
    hook, size = text_layer(script["hook"], "bold", [150, 140, 130, 120, 112, 104, 96, 88], CW, 820,
                            MX, TOP + 56, lh_mult=1.06)
    _centre([kick, hook], [0, 30])
    has_chart = bool(script.get("chart") or script.get("chart_slide"))
    dur = snap(0.9 + 0.2 * words(script["hook"]), minimum=4 if has_chart else 5)
    sc = Scene(dur)
    sc.items = [(kick, 0), (hook, 0)]
    sc.events = [(0.0, "impact")]
    return sc


def chart_scene(post, script):
    """The lesson's chart, large, drawing itself in right after the hook."""
    spec, note = script.get("chart"), script.get("chart_note")
    if not spec and script.get("chart_slide"):
        sp = post["slides"][script["chart_slide"] - 1]
        spec, note = sp["chart"], sp.get("note")
    if not spec:
        return None
    kick = kicker_layer(script.get("chart_kicker", "The math"), MX, 0, size=32)
    ph = 820
    chart = ChartPanel(spec, note, MX - 12, 0, FW - 2 * (MX - 12), ph)
    total = kick.h + 30 + (chart.bottom - chart.full.y)
    y = TOP + max(0, (BOTTOM - TOP - total) / 2) - 20
    kick.y = int(y)
    dy = int(y + kick.h + 30)
    chart.full.y = dy
    if chart.note:
        chart.note.y = dy + ph + 14
    chart.focus = [(fx, fy + dy) for fx, fy in chart.focus]
    chart.reveal_start = 0.3
    chart.emph_at = chart.reveal_start + chart.reveal + 0.3
    sc = Scene(snap(chart.emph_at + 1.3, minimum=5))
    sc.items = [(kick, 0.05), (chart, 0.1)]
    if chart.focus:
        sc.events = [(chart.emph_at, "pop")]
    return sc


def lines_scene(scene):
    items, layers, gaps = [], [], []
    if scene.get("kicker"):
        kl = kicker_layer(scene["kicker"], MX, 0, size=32)
        layers.append(kl)
        gaps.append(0)
    size = one_row_size(scene["lines"], "medium", [72, 68, 64, 60, 56, 52, 48, 44, 40], CW)
    for i, ln in enumerate(scene["lines"]):
        lay, _ = text_layer(ln, "medium", [size], CW, 400, MX, 0, lh_mult=1.18)
        layers.append(lay)
        gaps.append(26 if i == 0 else int(size * 0.42))
    _centre(layers, gaps)
    delays = []
    d0 = 0.05
    if scene.get("kicker"):
        delays.append(d0)
        d0 += 0.2
    for i in range(len(scene["lines"])):
        delays.append(d0 + STAGGER * i)
    last_in = delays[-1] + ENTER
    n_words = sum(words(t) for t in scene["lines"])
    sc = Scene(snap(last_in + 0.9 + 0.1 * n_words, minimum=6))
    sc.items = list(zip(layers, delays))
    first_line = 1 if scene.get("kicker") else 0
    sc.events = [(delays[first_line + i], "blip", i) for i in range(len(scene["lines"]))]
    return sc


def big_scene(scene):
    paras = scene["big"] if isinstance(scene["big"], list) else [scene["big"]]
    text = "\n".join(paras)
    sizes = [104, 98, 92, 86, 80, 74, 68, 62]
    for s in sizes:                                      # one size for all paragraphs
        f = R.font("bold", s)
        lh = R.p(s * 1.1)
        h = sum(lh * len(R.wrap_tokens(_scratch, R.rich_tokens(p), f, R.p(CW))) for p in paras)
        if h + R.p(s * 0.4) * (len(paras) - 1) <= R.p(760):
            break
    layers = [text_layer(p, "bold", [s], CW, 900, MX, 0, lh_mult=1.1)[0] for p in paras]
    _centre(layers, [0] + [int(s * 0.4)] * (len(layers) - 1))
    delays = [0.05 + 0.42 * i for i in range(len(layers))]
    sc = Scene(snap(delays[-1] + ENTER + 0.6 + 0.2 * words(text), minimum=5))
    sc.items = list(zip(layers, delays))
    return sc


def cta_scene(script, next_title=None):
    next_title = next_title or script.get("next_title")
    part1 = script.get("part") == 1 and next_title
    heads = ["Follow for", "**part 2**" if part1 else "**more**"]         # explicit break: never orphan the "2"
    size = one_row_size(heads, "bold", [132, 124, 116, 108, 100, 92], CW)
    f = R.font("bold", size)
    h = Layer(_text_image([R.rich_tokens(t) for t in heads], f, R.p(size * 1.06)), MX, 0)
    sub = f"Next: {next_title}" if part1 else "A new trading lesson every day"
    s, _ = text_layer(sub, "medium", [46, 42, 38], CW, 130, MX, 0, color=R.INK2, lh_mult=1.3)
    handle = kicker_layer("@builddifferent.trading", MX, 0, color=R.MUTED, size=34, upper=False)
    _centre([h, s, handle], [0, 30, 40])
    sc = Scene(snap(3.2, minimum=5))
    sc.items = [(h, 0.05), (s, 0.4), (handle, 0.7)]
    sc.events = [(0.12, "chime")]
    return sc


def build_scenes(post, script, next_title=None):
    if script.get("format") == "meme":
        from .meme import meme_scenes
        return meme_scenes(post, script) + [cta_scene(script, next_title)]
    scenes = [hook_scene(post, script)]
    ch = chart_scene(post, script)
    if ch:
        scenes.append(ch)
    for s in script.get("scenes", []):
        scenes.append(lines_scene(s) if "lines" in s else big_scene(s))
    scenes.append(cta_scene(script, next_title))
    return scenes


def timeline(scenes):
    starts, t = [], 0.0
    for s in scenes:
        starts.append(t)
        t += s.duration
    return starts, t


# ------------------------------------------------------------ background ---
def _background():
    t = np.linspace(0, 1, FH, dtype=np.float32)[:, None, None]
    top, bot = np.array(R.BG_TOP, np.float32), np.array(R.BG_BOT, np.float32)
    static = np.repeat(top + (bot - top) * t, FW, axis=1)
    yy, xx = np.mgrid[0:FH, 0:FW].astype(np.float32)
    glow = np.exp(-(((xx - (FW - 90)) / 330) ** 2 + ((yy - 250) / 330) ** 2))
    static += glow[..., None] * np.array(R.AMBER, np.float32) * 0.085
    grid = np.zeros((FH + 400, FW), np.float32)
    grid[::90, :] = 1
    grid[:, ::90] = 1
    return static, grid


# ----------------------------------------------------------------- build ---
def make_short(post, out_path, next_title=None, work_dir=None, script=None):
    """Render the lesson's reel script to an MP4. Returns (path, seconds)."""
    script = script or post["reel"]
    scenes = build_scenes(post, script, next_title)
    starts, total = timeline(scenes)
    events = []
    for i, (sc, st) in enumerate(zip(scenes, starts)):
        if i > 0:
            events.append((st, "whoosh"))
        events += [(st + e[0],) + tuple(e[1:]) for e in sc.events]
    work_dir = work_dir or tempfile.mkdtemp()
    wav = os.path.join(work_dir, "sound.wav")
    sound.render(total, events, wav, breakdown_at=starts[-1])

    static, grid = _background()
    header = header_layer(post.get("label", ""))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{FW}x{FH}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-map", "0:v", "-map", "1:a", "-shortest",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "19",
           "-g", str(FPS * 2), "-keyint_min", str(FPS), "-bf", "2", "-r", str(FPS),
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(total * FPS))
    track = np.array((40, 48, 60), np.float32)
    try:
        for f in range(n):
            t = f / FPS
            off = int(t * 14) % 90                       # grid drifts upward, slowly
            frame = static.copy()
            frame += grid[off:off + FH, :, None] * 6.5
            header.draw(frame)
            x1 = MX + CW * min(1.0, (t + 1 / FPS) / total)
            frame[PROGRESS_Y:PROGRESS_Y + 4, MX:FW - MX] = track
            frame[PROGRESS_Y:PROGRESS_Y + 4, MX:int(x1)] = np.array(R.AMBER, np.float32)
            i = max(k for k, st in enumerate(starts) if st <= t + 1e-9)
            scenes[i].draw(frame, t - starts[i], is_last=(i == len(scenes) - 1), first=(i == 0))
            proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    finally:
        if proc.poll() is None:
            proc.kill()
    return out_path, n / FPS


def plan(post, next_title=None, script=None):
    """Scene lengths without rendering video (used by build.py check)."""
    scenes = build_scenes(post, script or post["reel"], next_title)
    return [round(s.duration, 2) for s in scenes], round(timeline(scenes)[1], 2)


def preview(post, times, out_dir, next_title=None, script=None):
    """Write still frames at the given times (seconds) as PNGs, for review. Returns the paths."""
    scenes = build_scenes(post, script or post["reel"], next_title)
    starts, total = timeline(scenes)
    static, grid = _background()
    header = header_layer(post.get("label", ""))
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    track = np.array((40, 48, 60), np.float32)
    for t in times:
        t = min(max(0.0, t), total - 1 / FPS)
        off = int(t * 14) % 90
        frame = static.copy()
        frame += grid[off:off + FH, :, None] * 6.5
        header.draw(frame)
        x1 = MX + CW * min(1.0, (t + 1 / FPS) / total)
        frame[PROGRESS_Y:PROGRESS_Y + 4, MX:FW - MX] = track
        frame[PROGRESS_Y:PROGRESS_Y + 4, MX:int(x1)] = np.array(R.AMBER, np.float32)
        i = max(k for k, st in enumerate(starts) if st <= t + 1e-9)
        scenes[i].draw(frame, t - starts[i], is_last=(i == len(scenes) - 1), first=(i == 0))
        path = os.path.join(out_dir, f"t{t:05.2f}.png")
        Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8)).save(path)
        paths.append(path)
    return paths
