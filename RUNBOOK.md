# Daily posting runbook (@builddifferent.trading)

One carousel per day at about 7:20 PM IST. Everything a fresh session needs is in this repository.

## Daily steps

1. `pip install --break-system-packages -q pillow numpy fonttools` if missing. Fonts: Poppins in
   `/usr/share/fonts/truetype/google-fonts` (or `fonts/` in this repo).
2. `python3 build.py status`. If fewer than 7 posts remain, write new ones first (see `content/SCHEMA.md`),
   append them to `content/library.json`, and run `python3 build.py check` until it reports 0 problems.
3. `python3 build.py next --date <today in IST>`. It prints the post id, folder, files, public URLs and caption.
4. **Look at every slide** (open the JPGs). Check that nothing overlaps or is cut off, the numbers are right and
   the text follows the content rules. Fix the spec and re-run if anything is off. Never publish a slide you
   haven't looked at.
5. `git add posts content && git commit -m "Post <id>" && git push` (if the push is rejected because the Reels job
   pushed first, `git pull --rebase` and push again).
6. Wait until every URL from step 3 returns HTTP 200 (raw.githubusercontent.com can lag a minute).
7. Publish with Zapier: app `InstagramBusinessCLIAPI`, action `publish_media_v2`
   (tool `instagram_for_business_publish_photo_s`) with
   `instagramPageId` = value in `content/config.json`, `media` = the URL list in slide order,
   `caption` = the printed caption. Publish once; if the call errors, do not retry blindly: check the profile first.
8. `python3 build.py mark <id> --date <date> --dir <folder> --result "<post URL or result>"`, commit and push.
9. Report: one line with the lesson title and the post link.

## Reels (Tue, Thu, Sat around 12:55 PM IST)

A Reel is a 12-18 second video with one idea: a full-screen hook with the lesson's chart drawing itself in,
one or two short text beats, and a follow ending, over original generated sound. It is built from the lesson's
`reel` script (see "Reel scripts" in `content/SCHEMA.md`). Reels come in pairs where possible: part 1 ends with
"Follow for part 2", and the job always publishes that part 2 as the very next Reel.

1. Same setup as the daily steps, plus `pip install --break-system-packages -q scipy` and ffmpeg with libx264 and
   aac (`ffmpeg -hide_banner -encoders | grep -E "libx264|aac"`; `apt-get install -y ffmpeg` if missing).
2. `python3 build.py status` shows `next_reel` and whether it has a script. If it has none, write one in
   `content/library.json` following the schema (hook from the cover title, the lesson's chart, one or two beats
   using the lesson's own numbers; make it part 1 of a pair with a natural follow-up lesson when one fits, and give
   that lesson a part 2 script too). Run `python3 build.py check` until it reports 0 problems.
   Keep at least 4 unused scripts ahead (`unused_reel_scripts`); write more when it drops below that.
3. `python3 build.py reel --date <today in IST>`. It refuses if `content/reels.json` already has a Reel for today
   (never post two). It writes `reels/<date>-<id>.mp4` and prints the id, file, public URL, length, spec problems
   and caption. Exit code 4 means the video failed the Instagram spec check: stop and report.
4. Look at it: `python3 build.py reel-preview <id>` writes stills (cover/thumbnail, chart drawing in, each scene);
   open every one. Nothing may be cut off, overlap, or sit in the bottom quarter (Instagram's caption covers it).
5. `git add reels content && git commit -m "Reel <id>" && git push`, then wait until the URL returns HTTP 200.
6. Publish with Zapier: app `InstagramBusinessCLIAPI`, action `publish_video`
   (tool `instagram_for_business_publish_video`) with `instagramPageId` from `content/config.json`,
   `video` = the URL, `caption` = the printed caption.
   - "Video is still processing": Instagram needed longer than Zapier waits, and nothing went live
     (an unpublished upload expires by itself). Wait 3 minutes and call once more with the same values; after
     2 such retries, stop and report. So far the first retry has always worked.
   - Instagram rejects the file: retry once with `https://cdn.jsdelivr.net/gh/<owner>/<repo>@<commit sha>/<file>`.
7. `python3 build.py mark-reel <id> --date <date> --file <file> --result "<link or result>"`, commit and push.
8. Report: one line with the lesson title, part 1 or 2, and the Reel link.

## If something breaks

- Zapier auth error or stale connection: stop and tell the owner to reconnect Instagram in Zapier.
- Instagram rejects the media: check the URLs open as images, then retry once.
- Queue empty and no time to write: skip the day and report it. Never post filler or anything outside the rules.
