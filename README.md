# Build Different: daily post engine

Generates the daily educational carousels for [@builddifferent.trading](https://www.instagram.com/builddifferent.trading/)
and hosts the images so Instagram can fetch them.

- `content/library.json` is the queue of posts (built by `content/make_library.py`, extended by hand or by the daily run)
- `content/SCHEMA.md` has the post format and the content rules (education only, no recent market data, max 5 hashtags)
- `build.py` renders, validates and records posts
- `RUNBOOK.md` is the daily procedure
- `posts/` holds the published images (public, so Instagram can download them)

Educational content only. Not investment advice. Not SEBI-registered.
