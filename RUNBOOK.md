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

A Reel turns an already-published carousel into a 9:16 video: slides as a card in the Reels safe zone,
swipe transitions, progress bars, and charts that draw themselves in. It reaches people who don't follow
the page yet, which carousels rarely do.

1. Same setup as the daily steps, plus ffmpeg with libx264 and aac (`ffmpeg -hide_banner -encoders | grep -E "libx264|aac"`;
   `apt-get install -y ffmpeg` if missing).
2. `python3 build.py reel --date <today in IST>`. It refuses if `content/reels.json` already has a Reel for today
   (never post two). By default it picks the oldest published carousel, posted before today, that has no Reel yet;
   it writes `reel.mp4` into that carousel's folder and prints the id, file, public URL, length and caption.
   Exit code 4 means the video failed the Instagram spec check: stop and report.
3. Look at it: pull frames with `ffmpeg -ss <seconds> -i <file> -frames:v 1 frame.png` at 0 s (the cover, which is
   also the thumbnail), during a chart slide and on the last slide. Nothing may be cut off.
4. `git add posts content && git commit -m "Reel <id>" && git push`, then wait until the URL returns HTTP 200.
5. Publish with Zapier: app `InstagramBusinessCLIAPI`, action `publish_video`
   (tool `instagram_for_business_publish_video`) with `instagramPageId` from `content/config.json`,
   `video` = the URL, `caption` = the printed caption.
   - "Video is still processing": Instagram needed longer than Zapier waits, and nothing went live
     (an unpublished upload expires by itself). Wait 3 minutes and call once more with the same values; after
     2 such retries, stop and report.
   - Instagram rejects the file: retry once with `https://cdn.jsdelivr.net/gh/<owner>/<repo>@<commit sha>/<file>`.
6. `python3 build.py mark-reel <id> --date <date> --file <file> --result "<link or result>"`, commit and push.
7. Report: one line with the lesson title and the Reel link.

## If something breaks

- Zapier auth error or stale connection: stop and tell the owner to reconnect Instagram in Zapier.
- Instagram rejects the media: check the URLs open as images, then retry once.
- Queue empty and no time to write: skip the day and report it. Never post filler or anything outside the rules.
