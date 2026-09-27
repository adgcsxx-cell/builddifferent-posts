#!/usr/bin/env python3
"""Build Different daily post tool.

  python3 build.py next [--date YYYY-MM-DD]   Render the next unposted post into posts/<date>-<id>/
  python3 build.py render <id> [--out DIR]    Render one post (preview)
  python3 build.py sheet <id> [...]           Contact sheet of all slides for quick review
  python3 build.py urls <dir>                 Public image URLs for a rendered post folder
  python3 build.py mark <id> --date D --dir DIR [--result TEXT]   Record a published post
  python3 build.py status                     How many posts are left in the queue
  python3 build.py check                      Validate every post in the library
"""
import argparse
import datetime as dt
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bd import render  # noqa: E402

LIB = os.path.join(HERE, "content", "library.json")
POSTED = os.path.join(HERE, "content", "posted.json")
CONFIG = os.path.join(HERE, "content", "config.json")

TYPES = set(render.SLIDES)
CHART_KINDS = set(render.CHARTS)


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def ist_today():
    return (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).date().isoformat()


_cmap = None


def supported(ch):
    global _cmap
    if _cmap is None:
        try:
            from fontTools.ttLib import TTFont
            path = next(os.path.join(d, "Poppins-Regular.ttf") for d in render.FONT_DIRS
                        if os.path.exists(os.path.join(d, "Poppins-Regular.ttf")))
            _cmap = set(TTFont(path).getBestCmap())
        except Exception:  # fontTools missing: skip the glyph check
            _cmap = set()
    return not _cmap or ord(ch) in _cmap or ch in "\n"


def slide_texts(sl):
    out = []
    for k in ("kicker", "title", "sub", "body", "callout", "formula", "label", "value", "center", "note", "cue"):
        if isinstance(sl.get(k), str):
            out.append(sl[k])
    out += [x for x in sl.get("items", []) if isinstance(x, str)]
    out += [x for x in sl.get("steps", []) if isinstance(x, str)]
    for card in sl.get("cards", []):
        out += [card.get("name", ""), card.get("result", ""), card.get("result_label", ""), card.get("pill", "")]
        for row in card.get("rows", []):
            out += [str(v) for v in row]
    for row in sl.get("cells", []):
        for c in row:
            out += [c.get("title", ""), c.get("sub", "")]
    ch = sl.get("chart") or {}
    out += [str(x) for x in ch.get("categories", [])]
    out += [ch.get("title", ""), ch.get("x_label", "")]
    out += [p.get("label", "") for p in ch.get("points", [])]
    out += [v.get("label", "") for v in ch.get("vlines", [])]
    out += [lv.get("label", "") for lv in ch.get("levels", [])]
    out += [s.get("name", "") for s in ch.get("series", [])]
    return out


def validate(post):
    errs = []
    for key in ("id", "label", "slides", "caption", "hashtags"):
        if key not in post:
            errs.append(f"missing '{key}'")
    if errs:
        return errs
    if "_" in post["id"]:
        errs.append("id must not contain underscores")
    if not 3 <= len(post["slides"]) <= 10:
        errs.append("a carousel needs 3-10 slides")
    if post["slides"][0]["type"] != "cover":
        errs.append("first slide must be a cover")
    if len(post["hashtags"]) > 5:
        errs.append("Instagram allows at most 5 hashtags")
    for i, sl in enumerate(post["slides"], 1):
        if sl.get("type") not in TYPES:
            errs.append(f"slide {i}: unknown type {sl.get('type')}")
        if sl.get("type") == "chart" and sl.get("chart", {}).get("kind") not in CHART_KINDS:
            errs.append(f"slide {i}: unknown chart kind")
        for t in slide_texts(sl):
            bad = sorted({c for c in t if not supported(c)})
            if bad:
                errs.append(f"slide {i}: characters not in the font: {' '.join(bad)} (in: {t[:40]}...)")
    try:
        render.caption_text(post)
    except ValueError as e:
        errs.append(str(e))
    return errs


def cmd_check(_):
    lib = load(LIB, {"posts": []})
    ids = set()
    bad = 0
    for post in lib["posts"]:
        errs = validate(post)
        if post["id"] in ids:
            errs.append("duplicate id")
        ids.add(post["id"])
        for e in errs:
            print(f"{post['id']}: {e}")
        bad += bool(errs)
    print(f"{len(lib['posts'])} posts checked, {bad} with problems")
    return 1 if bad else 0


def next_post():
    lib = load(LIB, {"posts": []})
    done = {p["id"] for p in load(POSTED, [])}
    for post in lib["posts"]:
        if post["id"] not in done:
            return post
    return None


def cmd_next(a):
    post = next_post()
    if post is None:
        print(json.dumps({"error": "queue empty: add posts to content/library.json"}))
        return 2
    errs = validate(post)
    if errs:
        print(json.dumps({"error": "invalid post", "id": post["id"], "problems": errs}, ensure_ascii=False))
        return 3
    date = a.date or ist_today()
    out = os.path.join(HERE, "posts", f"{date}-{post['id']}")
    files = render.render_post(post, out)
    cap = render.caption_text(post)
    with open(os.path.join(out, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(cap + "\n")
    rel = [os.path.relpath(p, HERE) for p in files]
    print(json.dumps({"id": post["id"], "dir": os.path.relpath(out, HERE), "files": rel, "urls": urls_for(rel),
                      "caption": cap}, ensure_ascii=False, indent=1))
    return 0


def urls_for(rel_files):
    cfg = load(CONFIG, {})
    owner, repo, branch = cfg.get("github_owner"), cfg.get("repo"), cfg.get("branch", "main")
    if not owner or not repo:
        return []
    return [f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{p}" for p in rel_files]


def cmd_urls(a):
    d = os.path.join(HERE, a.dir) if not os.path.isabs(a.dir) else a.dir
    files = sorted(f for f in os.listdir(d) if f.endswith(".jpg"))
    print("\n".join(urls_for([os.path.relpath(os.path.join(d, f), HERE) for f in files])))
    return 0


def cmd_render(a):
    lib = load(LIB, {"posts": []})
    post = next((p for p in lib["posts"] if p["id"] == a.id), None)
    if post is None:
        print("no such post")
        return 1
    errs = validate(post)
    for e in errs:
        print("WARNING:", e)
    out = a.out or os.path.join(HERE, "preview", post["id"])
    for pth in render.render_post(post, out):
        print(pth)
    return 0


def cmd_sheet(a):
    lib = load(LIB, {"posts": []})
    for pid in a.ids:
        post = next(p for p in lib["posts"] if p["id"] == pid)
        out = os.path.join(HERE, "preview", pid)
        files = render.render_post(post, out)
        thumbs = [Image.open(f).resize((360, 450)) for f in files]
        sheet = Image.new("RGB", (len(thumbs) * 370 + 10, 470), (40, 40, 40))
        for i, t in enumerate(thumbs):
            sheet.paste(t, (10 + i * 370, 10))
        path = os.path.join(HERE, "preview", f"sheet-{pid}.jpg")
        sheet.save(path, quality=88)
        print(path)
    return 0


def cmd_mark(a):
    posted = load(POSTED, [])
    d = os.path.join(HERE, a.dir) if not os.path.isabs(a.dir) else a.dir
    files = sorted(f for f in os.listdir(d) if f.endswith(".jpg"))
    posted.append({"id": a.id, "date": a.date, "dir": os.path.relpath(d, HERE),
                   "slides": len(files), "result": a.result or "published"})
    save(POSTED, posted)
    print(f"recorded {a.id} for {a.date}")
    return 0


def cmd_status(_):
    lib = load(LIB, {"posts": []})
    done = {p["id"] for p in load(POSTED, [])}
    left = [p["id"] for p in lib["posts"] if p["id"] not in done]
    print(json.dumps({"posted": len(done), "remaining": len(left), "next": left[:3]}, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("next")
    s.add_argument("--date")
    s = sub.add_parser("render")
    s.add_argument("id")
    s.add_argument("--out")
    s = sub.add_parser("sheet")
    s.add_argument("ids", nargs="+")
    s = sub.add_parser("urls")
    s.add_argument("dir")
    s = sub.add_parser("mark")
    s.add_argument("id")
    s.add_argument("--date", required=True)
    s.add_argument("--dir", required=True)
    s.add_argument("--result")
    sub.add_parser("status")
    sub.add_parser("check")
    a = ap.parse_args()
    return {"next": cmd_next, "render": cmd_render, "sheet": cmd_sheet, "urls": cmd_urls, "mark": cmd_mark,
            "status": cmd_status, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
