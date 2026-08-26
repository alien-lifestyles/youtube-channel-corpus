# YouTube Channel Corpus

A small local app that copies **YouTube captions** (the same text as **Show transcript** on a video) onto your computer.

You do not need a YouTube API key. You do not need to know how to code.

---

## Start the app (Mac)

1. Download or clone this folder onto your computer.
2. Open the folder in Finder.
3. Double-click **`Open UI`**.
4. A Terminal window will open. Leave it open.
5. Your browser should open to [http://localhost:3000](http://localhost:3000).

That app is signed and notarized with Apple. The first time, macOS may still ask if you want to open it — choose **Open**.

If you prefer Terminal:

```bash
cd ~/YouTube-Transcript-Scraper
./start.sh
```

**To stop:** click the Terminal window and press **Control + C**.

---

## What to do in the browser

- **Single Video** — paste a YouTube video link, then click **Get Transcript**.
- **Channel Scraper** — paste a channel link (like `https://www.youtube.com/@ChannelName`) to pull captions from many videos.

What you get is the video’s **caption track** (manual or auto-generated). If a video has no captions, it is skipped.

---

## Where the files go

For bigger channel jobs, saved files live in a `data` folder inside this project. Each video can have:

- the transcript (the captions, with times)
- extra info like title, date, and description

You can open those files later, or drop them into a tool like NotebookLM.

---

## Extra (optional, terminal)

If you prefer typing commands, from this folder:

```bash
./start.sh
```

That does the same thing as double-clicking **Open UI.command**.

To pull a whole channel from the terminal (resumes if you stop and run it again):

```bash
source .venv/bin/activate
python scrape_channel.py "https://www.youtube.com/@ChannelName"
```

---

## Notes

- You need Python 3.10 or newer on your Mac. The one-click file will try to set the rest up for you.
- This runs only on your computer (`localhost`). It is not a website on the internet.
- YouTube may slow you down if you pull too many videos too fast. That is normal. You can stop and start again later.
