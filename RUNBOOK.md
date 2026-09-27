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
5. `git add posts content && git commit -m "Post <id>" && git push`.
6. Wait until every URL from step 3 returns HTTP 200 (raw.githubusercontent.com can lag a minute).
7. Publish with Zapier: app `InstagramBusinessCLIAPI`, action `publish_media_v2`
   (tool `instagram_for_business_publish_photo_s`) with
   `instagramPageId` = value in `content/config.json`, `media` = the URL list in slide order,
   `caption` = the printed caption. Publish once; if the call errors, do not retry blindly: check the profile first.
8. `python3 build.py mark <id> --date <date> --dir <folder> --result "<post URL or result>"`, commit and push.
9. Report: one line with the lesson title and the post link.

## If something breaks

- Zapier auth error or stale connection: stop and tell the owner to reconnect Instagram in Zapier.
- Instagram rejects the media: check the URLs open as images, then retry once.
- Queue empty and no time to write: skip the day and report it. Never post filler or anything outside the rules.
