# YouTube APIs for smaller batches

This project lists a channel with **yt-dlp** and pulls captions with **youtube-transcript-api**. That is **not** the official YouTube Data API.

The Data API helps **choose which videos** to process in small pages. It does **not** offer “download 100 transcripts in one call.” Captions are still one video at a time.

## What we do now (no API key)

- List only as many Videos-tab entries as this batch needs (`playlistend`), instead of walking the whole channel.
- Default first batch is **50**, matching `playlistItems.maxResults`.
- Optional **after date** and **before date** (`daterange` / `--date-after` / `--date-before`).
- Optional **skip Shorts** (under 61 seconds).
- Resume from files already on disk.

## If we add a Data API key later

1. `channels.list` → uploads playlist (`UC…` → `UU…`).
2. `playlistItems.list` with `maxResults=50` and `pageToken`.
3. `videos.list` (up to 50 IDs) for duration, `caption` flag, publish date.
4. Fetch captions for those IDs only; save `nextPageToken`.

Do **not** walk a catalog with `search.list` (quota is expensive; ~500 video cap per channel search).

Official `captions.download` is for videos **you own**, with OAuth. Other people’s public captions stay on timedtext / innertube.

Default Data API quota is about **10,000 units/day**.
