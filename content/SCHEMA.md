# Post schema and content rules

Every post in `content/library.json` is one Instagram carousel (3–10 slides, 1080×1350).
`python3 build.py check` validates the whole library; run it after every edit.

## Content rules (non-negotiable)

- **Education only.** No buy/sell/hold calls, no price targets, no "trade this tomorrow", no tips on specific stocks.
- **No recent market data.** SEBI rules (from 1 July 2026): any real price data used in education must be at least
  30 days old. Prefer math, synthetic charts or simulations, and say so in the chart `note`.
- **No performance claims.** No P&L screenshots, no "I made X%", no guaranteed returns.
- Every chart has a `note` saying what it is (math / simulation / synthetic / old data with date).
- Numbers in slides and captions must be computed, not guessed. Put the computation in `make_library.py`
  or compute it in a scratch script before writing the JSON.
- Max **5 hashtags** (Instagram limit). The builder appends the disclaimer line to every caption automatically.
- Slide text must only use characters Poppins supports: no `→`, `✓`, `✕`, `∝` (captions may use emoji and arrows).
- IDs: `NN-short-slug`, lowercase, hyphens, **no underscores**. Labels: `Lesson NN · Pillar`.
- Rotate pillars: Risk → Systems → Options → Psychology → Fundamentals. Keep the tone plain, calm and specific.

## Post object

```json
{
  "id": "33-example-slug",
  "pillar": "Risk",
  "label": "Lesson 33 · Risk",
  "slides": [ ... ],
  "caption": "Hook line.\n\nBody...\n\nQuestion or call to action.",
  "hashtags": ["#riskmanagement", "#tradingeducation"]
}
```

Wrap words in `**double asterisks**` to highlight them in amber. In `body` text, a new line starts a new
paragraph and a line starting with `- ` becomes a bullet.

## Slide types

| type | fields |
|---|---|
| `cover` (must be first) | `kicker`, `title`, `sub` |
| `text` | `title`, `body`, optional `callout` |
| `checklist` | `title`, `items` (3–8 strings) |
| `stat` | optional `kicker`, `value` (short, e.g. `"23"`, `"18%"`), `label`, optional `body` |
| `formula` | `title`, `formula` (use `\n` to break lines), `body` |
| `compare` | `title`, `cards` (2 × `{name, rows:[[k,v],...], result, result_label, pill, good, neutral}`), `body` |
| `matrix` | `title`, `x_axis` [2], `y_axis` [2], `cells` 2×2 of `{title, sub}`, `highlight` [row,col], `body` |
| `cycle` | `title`, `steps` (3–5), `center`, `highlight` (index), `body` |
| `windows` | `title`, `total`, `rows` [[train_start, train_end, test_end]...], `labels`, `axis_label`, `body` |
| `chart` | `title`, `body`, `chart` (below), `note` |
| `cta` (last) | nothing required |

## Charts (`slide.chart`)

- `{"kind": "bar", "title", "categories", "values", "value_format": "{:.0f}%", "highlight": [i], "highlight_range": [a,b], "x_label", "label_all", "show_y_axis", "label_every"}`
- `{"kind": "line", "title", "x", "series": [{"name", "values", "focus": true, "end_label"}], "y_format", "x_format", "x_ticks", "y_ticks", "x_label", "x_reverse", "zero_line", "area", "area_base", "end_dots", "points": [{"series", "x", "label", "dx", "dy"}], "vlines": [{"x", "label", "side", "label_pos"}], "regions": [{"x0", "x1", "label", "label_pos"}]}`
- `{"kind": "candles", "ohlc": [[o,h,l,c], ...], "levels": [{"y", "label", "focus"}]}` (synthetic only)

Chart style rules: one focus series in amber, everything else gray; a legend appears automatically for 2+ series;
label selectively (end points, the one number that matters), never every point; one y-axis only.

## Reel scripts (`post.reel`)

A Reel is a 12–18 second video with **one idea**, built from a lesson's `reel` script by `bd/short.py`:
a full-screen hook with the lesson's chart drawing itself in, one or two short text beats, then a follow
ending. Sound is generated (bd/sound.py), so nothing needs licensing.

```json
"reel": {
  "kicker": "Risk math · Part 1",
  "hook": "Lose **50%** and you need **+100%** just to get back to zero.",
  "chart_slide": 2,
  "scenes": [
    {"kicker": "Why?", "lines": ["Start with ₹1,00,000", "Lose 50%: now **₹50,000**"]},
    {"big": ["Small losses are cheap to fix.", "Big losses can take **years**."]}
  ],
  "part": 1, "next": "07-risk-per-trade", "next_title": "How much to risk on one trade"
}
```

- `hook`: at most 16 words, the lesson's strongest claim, with the key numbers in `**amber**`. Usually the cover title.
- `chart_slide`: 1-based index of the lesson's chart slide to show under the hook (omit for text-only hooks).
- `scenes`: 1 or 2. A `lines` scene stacks 2–4 short lines (34 characters max each, one fact per line, each gets
  its own note in the sound); a `big` scene is one or two short takeaway sentences in large type.
- Pairs: a part 1 names `next` (the lesson id of part 2) and `next_title` (what part 2 answers) and ends with
  "Follow for part 2". The part 2 lesson needs its own script with `"part": 2, "prev": "<part 1 id>"`; the
  Reels job publishes it as the very next Reel, so the promise is always kept. Single Reels leave `part` out
  and end with "Follow for more".
- Every number must come from the lesson itself (computed in `make_library.py`), and the content rules above apply.
- `python3 build.py check` validates scripts and their length; `python3 build.py reel-preview <id>` writes stills.

### Opening frame

Every Reel now opens on the hook alone, in the biggest type that fits and centred, so the first frame (also the
grid thumbnail) reads in under a second. When the script has a chart, it follows as its own scene, large, under
a small kicker (`chart_kicker`, default "The math").

## Meme Reels (`content/memes.json`)

A meme Reel is a two-beat "expectation vs reality" joke that lands on a lesson's point, drawn by `bd/meme.py`
(no outside images or meme templates). The joke is always on the overconfident trader. It must never suggest
that trading pays, beats a career, or makes money.

```json
{
  "id": "meme-01-career-rankings",
  "lesson": "07-risk-per-trade",
  "approved": false,
  "format": "meme",
  "kicker": "Trader life",
  "panels": [
    {"caption": "Me after **3 green trades** in a row:"},
    {"caption": "Me after **10 losses** in a row, risking 5% each:", "tag": "-40%"}
  ],
  "board": {"title": "Career rankings", "rows": ["Trader (me)", "Doctor", "CEO", "Pilot"], "me": 0},
  "punch": ["Same 10 losses at 1% risk: only **-9.6%**.", "Confidence is not a **risk plan**."],
  "caption": "...", "hashtags": ["#tradingmemes", "..."]
}
```

- Beat 1: panel 1's caption over the board, with the `me` row crowned at #1. Beat 2: the caption swaps, the
  `me` row drops to last, turns red and shows `tag`. Then the `punch` lines (1 or 2), then "Follow for more".
- `lesson`: the lesson whose numbers back the joke. Every number in the tag, punch and caption comes from it.
- `approved`: the Reels job only uses memes with `"approved": true`. Ad approves each new meme after
  seeing it, so new memes start as `false`.
- Scheduling: an approved, unused meme goes out after each finished pair or single Reel, never inside a pair
  and never twice in a row.
- `python3 build.py check` validates memes and `python3 build.py reel-preview <meme id>` writes stills.
