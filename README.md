# YouTube Channel Corpus Scraper

Pull transcripts and analysis-ready metadata from YouTube channels, and save them as a local corpus you can stop, resume, and feed to Claude / NotebookLM.

This started as a single-video transcript tool. It now defaults to **bulk channel collection** for studying beliefs, values, frameworks, and storytelling.

## What you get

For each channel, files land in `data/<channel-slug>/`:

```
data/SomeCreator/
  manifest.json          # scrape stats
  index.csv              # one row per video (dates, views, duration, transcript size)
  skipped.jsonl          # videos with no captions / errors
  videos/
    abc123.json          # full record (transcript + metadata)
    abc123.md            # LLM-friendly markdown
```

Each video record includes, when YouTube provides them:

- Timed transcript (priority) and a plain-text copy
- Title, URL, duration, upload date
- Description (full, not truncated)
- View / like / comment counts
- Tags, chapters, channel name

## Setup

```bash
cd ~/YouTube-Transcript-Scraper
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11 recommended (3.10+ should work).

## Bulk scrape (the main path)

```bash
python scrape_channel.py "https://www.youtube.com/@ChannelName"
```

That writes `data/<slug>/` and **resumes by default**. If it stops or YouTube rate-limits you, run the same command again; videos that already have a transcript are skipped.

Useful flags:

| Flag | Meaning |
| --- | --- |
| `-n 50` | Cap at 50 videos |
| `--delay 2` | Wait 2s between videos (safer on large channels) |
| `--min-duration 61` | Skip Shorts / clips under 61 seconds |
| `--no-metadata` | Transcripts only (faster) |
| `-o data/my-channel` | Custom output folder |

Then analyze:

1. Open `index.csv` to see coverage.
2. Drop `videos/*.md` into NotebookLM, or point Cursor/Claude at the folder with `prompts/analyze-channel.md`.

## Catalog first (no transcripts)

If you only need titles and URLs:

```bash
python scrape_channel.py "https://www.youtube.com/@ChannelName" --metadata-only --fast-playlist
```

For duration, views, and comments (slower, one request per video):

```bash
python scrape_channel.py "https://www.youtube.com/@ChannelName" --metadata-only
```

## Web UI (single video + light channel jobs)

```bash
python app.py
```

Open [http://localhost:3000](http://localhost:3000). The browser is fine for a handful of videos. For a favorite channel with hundreds of videos, use the CLI so results live on disk instead of in the page.

## Notes

- No YouTube API key. Uses `yt-dlp` for listings/metadata and `youtube-transcript-api` for captions.
- Captions must exist (manual or auto-generated). Videos without captions are skipped and logged.
- Be polite with `--delay`. YouTube will rate-limit aggressive scraping.
- Re-run is cheap: resume is on unless you pass `--no-resume`.
