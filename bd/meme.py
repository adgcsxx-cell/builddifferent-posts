"""Meme Reel format: a two-beat "expectation vs reality" joke that lands on a lesson.

  beat 1  caption A over a ranking board ("Career rankings": the trader crowned at #1)   <- first frame / thumbnail
  beat 2  caption swaps to B, the trader's row drops to the bottom, turns red, loses the crown, a tag pops in
  then    one or two `punch` lines in big type (the lesson's point, its own numbers), then the follow ending

The joke is always on the overconfident trader, never a claim that trading pays. Script lives in
content/memes.json (see "Meme Reels" in content/SCHEMA.md). Everything is drawn here, no outside images.
"""
from PIL import Image, ImageDraw

from . import render as R
from . import short as S

RED = (236, 96, 88)
ROW_H, ROW_GAP = 118, 16
SWITCH, MOVE = 2.9, 0.85          # when beat 2 starts, how long the drop takes


def _row_image(label, color_bg, color_text, rank_color, width, crown=False, weight="bold", border=None):
    w2, h2 = R.p(width), R.p(ROW_H)
    img = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w2 - 1, h2 - 1], radius=R.p(22), fill=color_bg + (255,),
                        outline=(border + (255,)) if border else None, width=R.p(3) if border else 0)
    f = R.font(weight, 50)
    d.text((R.p(150), h2 // 2), label, font=f, fill=color_text, anchor="lm")
    return img.resize((width, ROW_H), Image.LANCZOS)


def _crown(size=74, color=R.AMBER):
    s2 = R.p(size)
    img = Image.new("RGBA", (s2, s2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    b, t = s2 * 0.86, s2 * 0.22
    pts = [(s2 * 0.08, b), (s2 * 0.08, s2 * 0.42), (s2 * 0.30, s2 * 0.62), (s2 * 0.5, t),
           (s2 * 0.70, s2 * 0.62), (s2 * 0.92, s2 * 0.42), (s2 * 0.92, b)]
    d.polygon(pts, fill=color)
    for cx, cy in ((0.08, 0.40), (0.5, 0.20), (0.92, 0.40)):
        r = s2 * 0.07
        d.ellipse([s2 * cx - r, s2 * cy - r, s2 * cx + r, s2 * cy + r], fill=color)
    return img.resize((size, size), Image.LANCZOS)


class Board:
    """Ranking board whose `me` row falls from the top slot to the bottom one."""
    timed = True

    def __init__(self, title, rows, me, tag, y):
        self.n = len(rows)
        self.me = me
        self.x, self.w = S.MX, S.CW
        self.title = S.kicker_layer(title, S.MX, y, color=R.MUTED, size=30)
        self.top = y + self.title.h + 24
        self.slot_y = [self.top + i * (ROW_H + ROW_GAP) for i in range(self.n)]
        others = [r for i, r in enumerate(rows) if i != me]
        self.order_a = [rows[me]] + others                    # me first
        self.order_b = others + [rows[me]]                    # me last
        self.me_a = S.Layer(_row_image(rows[me], R.PANEL_HI, R.INK, R.AMBER, self.w, border=R.AMBER), self.x, 0)
        self.me_b = S.Layer(_row_image(rows[me], (44, 24, 26), RED, RED, self.w, border=RED), self.x, 0)
        self.rows = {r: S.Layer(_row_image(r, R.PANEL, R.INK2, R.MUTED, self.w, weight="medium"), self.x, 0)
                     for r in others}
        f = R.font("bold", 46)
        self.ranks = []
        for i in range(self.n):
            im = Image.new("RGBA", (R.p(110), R.p(ROW_H)), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((R.p(40), R.p(ROW_H) // 2), f"#{i + 1}", font=f, fill=R.MUTED, anchor="lm")
            self.ranks.append(S.Layer(im.resize((110, ROW_H), Image.LANCZOS), self.x, self.slot_y[i]))
        self.crown = S.Layer(_crown(), self.x + self.w - 110, 0)
        self.tag = None
        if tag:
            self.tag, _ = S.text_layer(tag, "bold", [60], 320, 120, 0, 0, color=RED)

    @property
    def bottom(self):
        return self.slot_y[-1] + ROW_H

    def draw(self, frame, t, dx, dy, opacity):
        q = S.ease_in_out((t - SWITCH) / MOVE)
        self.title.draw(frame, dx, dy, opacity)
        for name, lay in self.rows.items():
            ya = self.slot_y[self.order_a.index(name)]
            yb = self.slot_y[self.order_b.index(name)]
            lay.y = int(ya + (yb - ya) * q)
            lay.draw(frame, dx, dy, opacity)
        y_me = self.slot_y[0] + (self.slot_y[-1] - self.slot_y[0]) * S.ease_in((t - SWITCH) / MOVE) ** 0.8
        self.me_a.y = self.me_b.y = int(y_me)
        c = min(1.0, max(0.0, (t - SWITCH - 0.25) / 0.4))     # turns red as it falls
        self.me_a.draw(frame, dx, dy, opacity * (1 - c))
        self.me_b.draw(frame, dx, dy, opacity * c)
        for r in self.ranks:                                  # rank numbers stay put, rows slide under them
            r.draw(frame, dx, dy, opacity)
        # crown: sits on the row, then tumbles off and fades as the row drops
        u = (t - SWITCH) / 0.7
        self.crown.y = int(self.slot_y[0] + (ROW_H - self.crown.h) / 2 - 2)
        if u <= 0:
            self.crown.draw(frame, dx, dy, opacity)
        elif u < 1:
            self.crown.draw(frame, dx + 40 * u, dy - 60 * u + 260 * u * u, opacity * (1 - u))
        if self.tag and t > SWITCH + MOVE:
            e = S.ease_out((t - SWITCH - MOVE) / 0.3)
            self.tag.x = self.x + self.w - self.tag.w - 36
            self.tag.y = int(self.slot_y[-1] + (ROW_H - self.tag.h) / 2 + 6)
            self.tag.draw(frame, dx, dy + 20 * (1 - e), opacity * e)


class Captions:
    """Caption A, then caption B from SWITCH on (quick cross-fade with a small lift)."""
    timed = True

    def __init__(self, a, b, y):
        size = min(self._size(a), self._size(b))
        self.a, _ = S.text_layer(a, "bold", [size], S.CW, 260, S.MX, y, lh_mult=1.1)
        self.b, _ = S.text_layer(b, "bold", [size], S.CW, 260, S.MX, y, lh_mult=1.1)

    @staticmethod
    def _size(text):
        for s in (76, 72, 68, 64, 60, 56, 52):
            f = R.font("bold", s)
            if len(R.wrap_tokens(S._scratch, R.rich_tokens(text), f, R.p(S.CW))) <= 2:
                return s
        return 52

    @property
    def bottom(self):
        return max(self.a.bottom, self.b.bottom)

    def draw(self, frame, t, dx, dy, opacity):
        out = S.ease_in((t - SWITCH) / 0.2)
        inn = S.ease_out((t - SWITCH - 0.15) / 0.3)
        self.a.draw(frame, dx, dy - 30 * out, opacity * (1 - out))
        if inn > 0:
            self.b.draw(frame, dx, dy + 30 * (1 - inn), opacity * inn)


def meme_scenes(post, script):
    a, b = script["panels"]
    kick = S.kicker_layer(script.get("kicker", "Trader life"), S.MX, S.TOP, size=32)
    caps = Captions(a["caption"], b["caption"], S.TOP + 64)
    board = Board(script["board"]["title"], script["board"]["rows"], script["board"].get("me", 0),
                  b.get("tag"), caps.bottom + 56)
    total = board.bottom - S.TOP
    shift = int(max(0, (S.BOTTOM - S.TOP - total) / 2) - 30)
    kick.y += shift
    caps.a.y += shift
    caps.b.y += shift
    board = Board(script["board"]["title"], script["board"]["rows"], script["board"].get("me", 0),
                  b.get("tag"), caps.bottom + 56)
    sc = S.Scene(S.snap(SWITCH + MOVE + 1.6, minimum=6))
    sc.items = [(kick, 0), (caps, 0), (board, 0)]
    sc.events = [(0.0, "impact"), (SWITCH, "whoosh"), (SWITCH + MOVE, "pop")]
    scenes = [sc]
    if script.get("punch"):
        scenes.append(S.big_scene({"big": script["punch"]}))
    return scenes
