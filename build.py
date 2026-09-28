#!/usr/bin/env python3
"""Build Different daily post tool.

  python3 build.py next [--date YYYY-MM-DD]   Render the next unposted post into posts/<date>-<id>/
  python3 build.py render <id> [--out DIR]    Render one post (preview)
  python3 build.py sheet <id> [...]           Contact sheet of all slides for quick review
  python3 build.py urls <dir>                 Public image URLs for a rendered post folder
  python3 build.py mark <id> --date D --dir DIR [--result TEXT]   Record a published post
  python3 build.py status                     How many posts are left in the queue
  python3 build.py check                      Validate every post in the library
  python3 build.py reel [--id ID] [--date D]  Make today's Reel (reels/<date>-<id>.mp4) from a lesson's reel script:
                                              part 2 of the last Reel's pair if one is due, else the oldest
                                              carousel posted before today that has no Reel yet
  python3 build.py reel-preview <id>           Still frames of a lesson's Reel for review (preview/reel-<id>/)
  python3 build.py mark-reel <id> --date D --file F [--result TEXT]   Record a published Reel
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
REELS = os.path.join(HERE, "content", "reels.json")
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
    by_id = {p["id"]: p for p in lib["posts"]}
    for post in lib["posts"]:
        errs = validate(post) + validate_reel(post, by_id)
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


def reel_candidate(today, reels, posted, lib, want_id=None):
    """Which lesson gets today's Reel.
    1. `want_id` if given.
    2. Part 2 of a pair: if the last Reel's script names a `next` lesson that has no Reel yet.
    3. Otherwise the oldest carousel posted before today that has no Reel yet."""
    have = {r["id"] for r in reels}
    if want_id:
        return want_id if want_id in lib else None
    if reels:
        nxt = lib.get(reels[-1]["id"], {}).get("reel", {}).get("next")
        if nxt and nxt not in have and nxt in lib:
            return nxt
    for p in posted:
        if p.get("dir") not in (None, "", "manual") and p["date"] < today and p["id"] not in have:
            return p["id"]
    return None


def reel_caption(post, lib):
    r = post.get("reel", {})
    extra = ""
    if r.get("part") == 1 and r.get("next_title"):
        extra = f"Part 1 of 2. Part 2 is next: {r['next_title'].rstrip('.')}. Follow so you don't miss it."
    elif r.get("part") == 2 and r.get("prev") in lib and lib[r["prev"]].get("reel"):
        extra = "Part 2 of 2. Missed part 1? It's on the profile: " + lib[r["prev"]]["reel"]["hook"].replace("**", "")
    return render.caption_text(dict(post, caption=post["caption"].strip() + ("\n\n" + extra if extra else "")))


def validate_reel(post, lib):
    """Problems with a lesson's reel script (empty list = fine)."""
    r = post.get("reel")
    if not r:
        return []
    errs = []
    if not isinstance(r.get("hook"), str) or len(r["hook"].replace("**", "").split()) > 16:
        errs.append("reel: hook missing or longer than 16 words")
    cs = r.get("chart_slide")
    if cs and not (1 <= cs <= len(post["slides"]) and post["slides"][cs - 1]["type"] == "chart"):
        errs.append("reel: chart_slide must point at a chart slide")
    scenes = r.get("scenes", [])
    if not 1 <= len(scenes) <= 2:
        errs.append("reel: needs 1 or 2 scenes after the hook")
    texts = [r.get("hook", ""), r.get("kicker", ""), r.get("next_title", "")]
    for sc in scenes:
        texts += [sc.get("kicker", "")] + sc.get("lines", [])
        big = sc.get("big", [])
        texts += big if isinstance(big, list) else [big]
        if "lines" in sc and not 2 <= len(sc["lines"]) <= 4:
            errs.append("reel: a lines scene needs 2-4 lines")
        if any(len(t.replace("**", "")) > 34 for t in sc.get("lines", [])):
            errs.append("reel: keep each line to 34 characters or fewer")
    if r.get("part") == 1 and not (r.get("next") in lib and r.get("next_title")):
        errs.append("reel: part 1 needs `next` (a lesson id) and `next_title`")
    if r.get("next") in lib and not lib[r["next"]].get("reel"):
        errs.append(f"reel: part 2 ({r['next']}) has no reel script yet")
    for t in texts:
        bad = sorted({c for c in t if not supported(c)})
        if bad:
            errs.append(f"reel: characters not in the font: {' '.join(bad)}")
    if not errs:
        from bd import short
        _, total = short.plan(post)
        if not 11 <= total <= 18.5:
            errs.append(f"reel: {total:.1f} s long; aim for 12-18 s (shorten or add text)")
    return errs


def cmd_reel(a):
    from bd import reel, short
    today = a.date or ist_today()
    reels = load(REELS, [])
    if not a.force and any(r["date"] == today for r in reels):
        print(json.dumps({"error": f"a Reel is already recorded for {today}; not making another"}))
        return 5
    lib = {p["id"]: p for p in load(LIB, {"posts": []})["posts"]}
    pid = reel_candidate(today, reels, load(POSTED, []), lib, a.id)
    if pid is None:
        print(json.dumps({"error": "no lesson is waiting for a Reel" if not a.id else f"unknown lesson {a.id}"}))
        return 2
    post = lib[pid]
    if not post.get("reel"):
        print(json.dumps({"error": f"{pid} has no reel script: write one (content/SCHEMA.md, 'Reel scripts'), "
                                   "run python3 build.py check, then run this again", "id": pid}))
        return 6
    errs = validate_reel(post, lib)
    if errs:
        print(json.dumps({"error": "reel script problems", "id": pid, "problems": errs}, ensure_ascii=False))
        return 3
    out = os.path.join(HERE, "reels", f"{today}-{pid}.mp4")
    path, secs = short.make_short(post, out)
    problems = reel.check_specs(path)
    rel = os.path.relpath(path, HERE)
    print(json.dumps({"id": pid, "part": post["reel"].get("part"), "file": rel, "url": urls_for([rel])[0],
                      "seconds": round(secs, 1), "mb": round(os.path.getsize(path) / 1e6, 2),
                      "problems": problems, "caption": reel_caption(post, lib)}, ensure_ascii=False, indent=1))
    return 4 if problems else 0


def cmd_reel_preview(a):
    from bd import short
    lib = {p["id"]: p for p in load(LIB, {"posts": []})["posts"]}
    post = lib.get(a.id)
    if not post or not post.get("reel"):
        print("no reel script for", a.id)
        return 1
    scenes = short.build_scenes(post, post["reel"])
    starts, total = short.timeline(scenes)
    times = [0.0, 0.7, starts[0] + scenes[0].duration - 0.5]
    times += [st + sc.duration - 0.6 for st, sc in zip(starts[1:], scenes[1:])]
    for pth in short.preview(post, times, os.path.join(HERE, "preview", f"reel-{a.id}")):
        print(pth)
    return 0


def cmd_mark_reel(a):
    reels = load(REELS, [])
    reels.append({"id": a.id, "date": a.date, "file": a.file, "result": a.result or "published"})
    save(REELS, reels)
    print(f"recorded Reel {a.id} for {a.date}")
    return 0


def cmd_status(_):
    lib = load(LIB, {"posts": []})
    posted = load(POSTED, [])
    done = {p["id"] for p in posted}
    left = [p["id"] for p in lib["posts"] if p["id"] not in done]
    reels = load(REELS, [])
    lib_by_id = {p["id"]: p for p in lib["posts"]}
    nxt = reel_candidate(ist_today(), reels, posted, lib_by_id)
    scripted = [p["id"] for p in lib["posts"] if p.get("reel") and p["id"] not in {r["id"] for r in reels}]
    print(json.dumps({"posted": len(done), "remaining": len(left), "next": left[:3],
                      "reels_posted": len(reels), "next_reel": nxt,
                      "next_reel_has_script": bool(nxt and lib_by_id[nxt].get("reel")),
                      "unused_reel_scripts": len(scripted)}, indent=1))
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
    s = sub.add_parser("reel")
    s.add_argument("--id")
    s.add_argument("--date")
    s.add_argument("--force", action="store_true", help="make one even if a Reel is recorded for today")
    s = sub.add_parser("reel-preview")
    s.add_argument("id")
    s = sub.add_parser("mark-reel")
    s.add_argument("id")
    s.add_argument("--date", required=True)
    s.add_argument("--file", required=True)
    s.add_argument("--result")
    a = ap.parse_args()
    return {"next": cmd_next, "render": cmd_render, "sheet": cmd_sheet, "urls": cmd_urls, "mark": cmd_mark,
            "status": cmd_status, "check": cmd_check, "reel": cmd_reel, "reel-preview": cmd_reel_preview,
            "mark-reel": cmd_mark_reel}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
