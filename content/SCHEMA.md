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
