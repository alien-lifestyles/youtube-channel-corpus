"""
On-disk channel corpus for analysis.

Layout:
    data/<channel>/
      manifest.json
      index.csv
      skipped.jsonl
      videos/<video_id>.json
      videos/<video_id>.md
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


def channel_slug_from_url(url: str) -> str:
    """Derive a filesystem-safe folder name from a channel URL."""
    url = (url or "").strip().rstrip("/")
    if "/@" in url:
        handle = url.split("/@")[-1].split("/")[0]
        return _safe_slug(handle.lstrip("@") or "channel")
    if "/channel/" in url:
        return _safe_slug(url.split("/channel/")[-1].split("/")[0] or "channel")
    if "/c/" in url:
        return _safe_slug(url.split("/c/")[-1].split("/")[0] or "channel")
    return "channel"


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return slug or "channel"


def corpus_paths(output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    videos = output_dir / "videos"
    return {
        "root": output_dir,
        "videos": videos,
        "manifest": output_dir / "manifest.json",
        "index": output_dir / "index.csv",
        "skipped": output_dir / "skipped.jsonl",
    }


def ensure_corpus_dir(output_dir: Path) -> dict[str, Path]:
    paths = corpus_paths(output_dir)
    paths["videos"].mkdir(parents=True, exist_ok=True)
    return paths


def load_existing_ids(output_dir: Path) -> set[str]:
    """Video IDs that already have a JSON record with a transcript."""
    videos_dir = corpus_paths(output_dir)["videos"]
    if not videos_dir.exists():
        return set()
    found: set[str] = set()
    for path in videos_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        transcript = data.get("transcript") or []
        if data.get("video_id") and transcript:
            found.add(data["video_id"])
        elif path.stem:
            # Treat any well-formed JSON as done so resume stays conservative.
            if data.get("transcript_text"):
                found.add(path.stem)
    return found


def format_timestamp(seconds: float) -> str:
    total = int(seconds or 0)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_upload_date(value: Optional[str]) -> str:
    if not value:
        return ""
    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    return value


def transcript_plain_text(transcript: list[dict]) -> str:
    return " ".join(
        (s.get("text") or "").strip()
        for s in transcript
        if (s.get("text") or "").strip()
    )


def video_to_markdown(video: dict) -> str:
    """LLM-friendly markdown: metadata first, then full timed transcript."""
    title = video.get("title") or "Untitled"
    url = video.get("url") or ""
    duration = video.get("duration")
    duration_str = video.get("duration_str") or (
        format_timestamp(duration) if duration is not None else ""
    )
    lines = [
        f"# {title}\n",
        "",
        f"- **URL:** {url}",
        f"- **Video ID:** {video.get('video_id') or ''}",
        f"- **Channel:** {video.get('channel') or ''}",
        f"- **Uploaded:** {format_upload_date(video.get('upload_date'))}",
        f"- **Duration:** {duration_str}",
        f"- **Views:** {video.get('view_count') if video.get('view_count') is not None else ''}",
        f"- **Likes:** {video.get('like_count') if video.get('like_count') is not None else ''}",
        f"- **Comments:** {video.get('comment_count') if video.get('comment_count') is not None else ''}",
    ]
    tags = video.get("tags") or []
    if tags:
        lines.append(f"- **Tags:** {', '.join(str(t) for t in tags)}")
    categories = video.get("categories") or []
    if categories:
        lines.append(f"- **Categories:** {', '.join(str(c) for c in categories)}")
    lines.append("")

    description = (video.get("description") or "").strip()
    if description:
        lines.extend(["## Description", "", description, ""])

    chapters = video.get("chapters") or []
    if chapters:
        lines.extend(["## Chapters", ""])
        for ch in chapters:
            start = format_timestamp(ch.get("start") or 0)
            ch_title = ch.get("title") or ""
            lines.append(f"- [{start}] {ch_title}")
        lines.append("")

    lines.extend(["## Transcript", ""])
    transcript = video.get("transcript") or []
    if transcript:
        for s in transcript:
            ts = format_timestamp(s.get("start") or 0)
            text = (s.get("text") or "").strip()
            if text:
                lines.append(f"[{ts}] {text}")
    else:
        plain = (video.get("transcript_text") or "").strip()
        lines.append(plain or "_No transcript._")

    lines.append("")
    return "\n".join(lines)


INDEX_FIELDS = [
    "video_id",
    "title",
    "url",
    "upload_date",
    "duration_str",
    "duration",
    "view_count",
    "like_count",
    "comment_count",
    "channel",
    "has_transcript",
    "transcript_chars",
    "tag_count",
    "chapter_count",
]


def write_video(output_dir: Path, video: dict) -> Path:
    """Write one video's JSON + markdown. Returns the JSON path."""
    paths = ensure_corpus_dir(output_dir)
    video_id = video.get("video_id") or "unknown"
    record = dict(video)
    transcript = record.get("transcript") or []
    record["transcript_text"] = record.get("transcript_text") or transcript_plain_text(transcript)
    record["has_transcript"] = bool(record["transcript_text"])
    json_path = paths["videos"] / f"{video_id}.json"
    md_path = paths["videos"] / f"{video_id}.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(video_to_markdown(record), encoding="utf-8")
    return json_path


def append_skipped(output_dir: Path, skipped: dict) -> None:
    paths = ensure_corpus_dir(output_dir)
    row = dict(skipped)
    row["skipped_at"] = datetime.now(timezone.utc).isoformat()
    with paths["skipped"].open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def rewrite_index(output_dir: Path, videos: Optional[Iterable[dict]] = None) -> None:
    """Rewrite index.csv from provided videos, or by scanning videos/*.json."""
    paths = ensure_corpus_dir(output_dir)
    rows: list[dict]
    if videos is None:
        rows = []
        for path in sorted(paths["videos"].glob("*.json")):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    else:
        rows = list(videos)

    with paths["index"].open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for video in rows:
            transcript = video.get("transcript") or []
            text = video.get("transcript_text") or transcript_plain_text(transcript)
            writer.writerow(
                {
                    "video_id": video.get("video_id") or "",
                    "title": (video.get("title") or "").replace("\n", " "),
                    "url": video.get("url") or "",
                    "upload_date": format_upload_date(video.get("upload_date")),
                    "duration_str": video.get("duration_str") or "",
                    "duration": video.get("duration") if video.get("duration") is not None else "",
                    "view_count": video.get("view_count") if video.get("view_count") is not None else "",
                    "like_count": video.get("like_count") if video.get("like_count") is not None else "",
                    "comment_count": video.get("comment_count") if video.get("comment_count") is not None else "",
                    "channel": video.get("channel") or "",
                    "has_transcript": "yes" if text else "no",
                    "transcript_chars": len(text),
                    "tag_count": len(video.get("tags") or []),
                    "chapter_count": len(video.get("chapters") or []),
                }
            )


def write_manifest(
    output_dir: Path,
    *,
    channel_url: str,
    channel_name: str = "",
    scraped_count: int = 0,
    skipped_count: int = 0,
    resumed_ids: int = 0,
    extra: Optional[dict] = None,
) -> None:
    paths = ensure_corpus_dir(output_dir)
    payload = {
        "channel_url": channel_url,
        "channel_name": channel_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "scraped_count": scraped_count,
        "skipped_count": skipped_count,
        "resumed_ids": resumed_ids,
        "corpus_dir": str(paths["root"].resolve()),
    }
    if extra:
        payload.update(extra)
    paths["manifest"].write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Names used by channel_scraper.py
append_skipped = append_skipped
rewrite_index = rewrite_index
write_video = write_video
