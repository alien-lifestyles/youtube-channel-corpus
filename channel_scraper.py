"""
Channel scraper: channel video lists, transcripts with timestamps, and analysis metadata.
"""

from __future__ import annotations

import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from corpus import (
    append_skipped,
    ensure_corpus_dir,
    load_existing_ids,
    rewrite_index,
    write_manifest,
    write_video,
)

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


@dataclass
class TranscriptSnippet:
    """A single transcript segment with timestamp."""

    start: float
    duration: float
    text: str

    def to_dict(self) -> dict:
        return {"start": self.start, "duration": self.duration, "text": self.text}

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Format seconds as MM:SS."""
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"


@dataclass
class ClipRecommendation:
    """Recommended clip segment for pitch deck."""

    start_seconds: float
    end_seconds: float
    opening_text: str
    video_id: str
    video_title: str

    @property
    def start_formatted(self) -> str:
        return TranscriptSnippet.format_timestamp(self.start_seconds)

    @property
    def end_formatted(self) -> str:
        return TranscriptSnippet.format_timestamp(self.end_seconds)

    def to_dict(self) -> dict:
        return {
            "start": self.start_seconds,
            "end": self.end_seconds,
            "start_formatted": self.start_formatted,
            "end_formatted": self.end_formatted,
            "opening_text": self.opening_text[:100] + "..." if len(self.opening_text) > 100 else self.opening_text,
            "video_id": self.video_id,
            "video_title": self.video_title,
        }


@dataclass
class ScreenshotRecommendation:
    """Recommended screenshot timestamp for pitch deck."""

    timestamp_seconds: float
    video_id: str
    video_title: str

    @property
    def timestamp_formatted(self) -> str:
        return TranscriptSnippet.format_timestamp(self.timestamp_seconds)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp_seconds,
            "timestamp_formatted": self.timestamp_formatted,
            "video_id": self.video_id,
            "video_title": self.video_title,
        }


@dataclass
class SkippedVideo:
    """Video that was skipped due to transcript fetch failure."""

    video_id: str
    title: str
    reason: str

    def to_dict(self) -> dict:
        return {"video_id": self.video_id, "title": self.title, "reason": self.reason}


@dataclass
class ScrapedVideo:
    """Full scraped video data with transcript and analysis metadata."""

    video_id: str
    title: str
    url: str
    duration: Optional[float]
    transcript: list[TranscriptSnippet]
    clip_recommendations: list[ClipRecommendation] = field(default_factory=list)
    screenshot_recommendations: list[ScreenshotRecommendation] = field(default_factory=list)
    description: Optional[str] = None
    upload_date: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    tags: list[str] = field(default_factory=list)
    chapters: list[dict] = field(default_factory=list)
    channel: Optional[str] = None
    channel_id: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    thumbnail: Optional[str] = None
    language: Optional[str] = None

    def to_dict(self) -> dict:
        transcript = [s.to_dict() for s in self.transcript]
        return {
            "video_id": self.video_id,
            "title": self.title,
            "url": self.url,
            "duration": self.duration,
            "duration_str": _format_duration(self.duration),
            "transcript": transcript,
            "transcript_text": " ".join(s.text for s in self.transcript if s.text.strip()),
            "clip_recommendations": [c.to_dict() for c in self.clip_recommendations],
            "screenshot_recommendations": [s.to_dict() for s in self.screenshot_recommendations],
            "description": self.description,
            "upload_date": self.upload_date,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "tags": self.tags,
            "chapters": self.chapters,
            "channel": self.channel,
            "channel_id": self.channel_id,
            "categories": self.categories,
            "thumbnail": self.thumbnail,
            "language": self.language,
        }


def _fetch_transcript_with_timestamps(video_id: str) -> list[TranscriptSnippet]:
    """Fetch transcript preserving timestamps. Raises on failure."""
    api = YouTubeTranscriptApi()

    try:
        fetched = api.fetch(video_id, languages=("en",))
    except Exception:
        try:
            transcript_list = api.list(video_id)
            try:
                transcript = transcript_list.find_transcript(["en"])
            except Exception:
                transcript = transcript_list.find_transcript([])
            fetched = transcript.fetch()
        except Exception:
            try:
                fetched = api.fetch(video_id, languages=())
            except Exception as e:
                raise e

    snippets = []
    for s in fetched.snippets:
        snippets.append(
            TranscriptSnippet(
                start=getattr(s, "start", 0.0),
                duration=getattr(s, "duration", 0.0),
                text=s.text,
            )
        )
    return snippets


def _generate_clip_recommendations(
    snippets: list[TranscriptSnippet],
    video_id: str,
    video_title: str,
    clip_interval_sec: float = 120,
    clip_duration_sec: float = 75,
) -> list[ClipRecommendation]:
    """Generate clip recommendations at natural boundaries (~every 2 min)."""
    if not snippets:
        return []

    recommendations = []
    current_start = 0.0
    last_end = snippets[-1].start + snippets[-1].duration if snippets else 0

    while current_start < last_end - 10:  # Need at least 10 sec of content
        end_time = min(current_start + clip_duration_sec, last_end)
        # Find opening text for this segment
        opening = ""
        for s in snippets:
            if s.start >= current_start:
                opening = s.text
                break
        if not opening:
            for s in reversed(snippets):
                if s.start + s.duration <= end_time:
                    opening = s.text
                    break

        recommendations.append(
            ClipRecommendation(
                start_seconds=current_start,
                end_seconds=end_time,
                opening_text=opening or "(start of segment)",
                video_id=video_id,
                video_title=video_title,
            )
        )
        current_start += clip_interval_sec

    return recommendations


def _generate_screenshot_recommendations(
    snippets: list[TranscriptSnippet],
    video_id: str,
    video_title: str,
    interval_sec: float = 75,
) -> list[ScreenshotRecommendation]:
    """Generate screenshot recommendations every ~60-90 seconds."""
    if not snippets:
        return []

    last_time = snippets[-1].start + snippets[-1].duration if snippets else 0
    recommendations = []
    t = 0.0
    while t < last_time:
        recommendations.append(
            ScreenshotRecommendation(
                timestamp_seconds=t,
                video_id=video_id,
                video_title=video_title,
            )
        )
        t += interval_sec
    return recommendations


def _normalize_channel_url(url: str, videos_tab_only: bool = False) -> str:
    """Normalize channel URL. If videos_tab_only, append /videos. Else use base URL for all tabs."""
    url = url.strip().rstrip("/")
    # Remove existing tab paths for consistency
    for tab in ["/videos", "/streams", "/shorts", "/live"]:
        if url.endswith(tab):
            url = url[: -len(tab)]
    if videos_tab_only:
        if "/@" in url or "/channel/" in url or "/c/" in url or url.endswith("youtube.com"):
            url = url + "/videos"
    return url


def _flatten_entries(entries: list) -> list[dict]:
    """Flatten nested playlist entries (from full channel) into a single list of video dicts."""
    result = []
    for e in entries:
        if not e or not isinstance(e, dict):
            continue
        if e.get("_type") == "playlist":
            sub = e.get("entries") or []
            result.extend(_flatten_entries(sub))
        elif e.get("id"):
            result.append(e)
    return result


def _get_channel_videos(
    channel_url: str,
    max_videos: Optional[int] = None,
    all_tabs: bool = True,
) -> list[dict]:
    """
    Fetch channel video list using yt-dlp. Returns list of {id, title, url, duration}.

    When all_tabs=True (default), uses base channel URL to get videos from all tabs
    (Videos, Shorts, Live), which fetches thousands of videos. When False, uses
    /videos tab only (faster but may be limited to ~200 videos on large channels).
    """
    # Use full channel (all tabs) for complete extraction; /videos tab only when explicitly requested
    url = _normalize_channel_url(channel_url, videos_tab_only=not all_tabs)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "force_generic_extractor": False,
    }
    # playlistend applies to top-level; with all_tabs we have nested playlists, so slice after flatten
    if max_videos and not all_tabs:
        opts["playlistend"] = max_videos

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("Could not extract channel info")

        entries = info.get("entries") or []
        flat_entries = _flatten_entries(entries) if all_tabs else entries
        if max_videos and all_tabs:
            flat_entries = flat_entries[:max_videos]
        videos = []
        for e in flat_entries:
            if not e:
                continue
            vid = e.get("id")
            if not vid:
                continue
            videos.append(
                {
                    "id": vid,
                    "title": e.get("title") or "Unknown",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "duration": e.get("duration"),
                }
            )
        return videos


def _format_duration(duration: Optional[float]) -> str:
    """Format duration in seconds as M:SS or H:MM:SS."""
    if duration is None:
        return ""
    m = int(duration // 60)
    s = int(duration % 60)
    if m >= 60:
        h = m // 60
        m = m % 60
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


_format_duration = _format_duration


def extract_analysis_metadata(info: dict) -> dict:
    """Pull analysis-relevant fields from a yt-dlp video info dict. Never truncates description."""
    if not info:
        return {}
    chapters = []
    for ch in info.get("chapters") or []:
        chapters.append(
            {
                "title": ch.get("title"),
                "start": ch.get("start_time"),
                "end": ch.get("end_time"),
            }
        )
    tags = info.get("tags") or []
    categories = info.get("categories") or []
    return {
        "description": info.get("description") or "",
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "tags": tags if isinstance(tags, list) else [],
        "chapters": chapters,
        "channel": info.get("uploader") or info.get("channel"),
        "channel_id": info.get("channel_id") or info.get("uploader_id"),
        "categories": categories if isinstance(categories, list) else [],
        "thumbnail": info.get("thumbnail"),
        "language": info.get("language") or info.get("original_language"),
        "uploader": info.get("uploader") or info.get("channel"),
    }


def _get_channel_metadata_flat_fast(
    channel_url: str,
    max_videos: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> list[dict]:
    """
    Single flat playlist fetch (fast). Title and URL are reliable; duration may appear when
    YouTube includes it in tab data; view_count / comment_count are usually empty.
    """
    url = _normalize_channel_url(channel_url, videos_tab_only=False)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "force_generic_extractor": False,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("Could not extract channel info")

        entries = info.get("entries") or []
        flat_entries = _flatten_entries(entries)
        if max_videos:
            flat_entries = flat_entries[:max_videos]

        videos: list[dict] = []
        total = len(flat_entries)
        for i, e in enumerate(flat_entries):
            if not e:
                continue
            vid = e.get("id")
            if not vid:
                continue
            title = e.get("title") or "Unknown"
            if progress_callback:
                progress_callback(i + 1, total, title)

            videos.append(
                {
                    "id": vid,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "duration": e.get("duration"),
                    "duration_str": _format_duration(e.get("duration")),
                    "view_count": e.get("view_count"),
                    "comment_count": e.get("comment_count"),
                }
            )
        return videos


def get_channel_metadata(
    channel_url: str,
    max_videos: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    full_extraction: bool = False,
    delay_seconds: float = 0.5,
    base_videos: Optional[list[dict]] = None,
    fast_playlist_only: bool = False,
) -> list[dict]:
    """
    Fetch channel video metadata (title, URL, duration, views, comments) without transcripts.

    Default path: flat playlist for IDs, then one yt-dlp extract_info per video for reliable
    duration, view_count, and comment_count.

    Args:
        full_extraction: If True, also capture upload_date, uploader, likes, thumbnail, description.
        delay_seconds: Delay between per-video requests (rate limiting). Ignored when fast_playlist_only.
        base_videos: Optional pre-fetched list from _get_channel_videos (skips duplicate playlist fetch).
        fast_playlist_only: If True (and not full_extraction), only run flat playlist extraction (fast;
            duration best-effort; views/comments usually empty).
    """
    channel_url = _normalize_channel_url(channel_url)

    if fast_playlist_only and not full_extraction:
        return _get_channel_metadata_flat_fast(channel_url, max_videos, progress_callback)

    if base_videos is None:
        base_videos = _get_channel_videos(channel_url, max_videos)
    videos: list[dict] = []
    opts = {"quiet": True, "no_warnings": True, "force_generic_extractor": False}

    with yt_dlp.YoutubeDL(opts) as ydl:
        for i, v in enumerate(base_videos):
            vid = v["id"]
            url = v["url"]
            title = v.get("title") or "Unknown"

            if progress_callback:
                progress_callback(i + 1, len(base_videos), title)

            try:
                e = ydl.extract_info(url, download=False)
            except Exception:
                videos.append(
                    {
                        "id": vid,
                        "title": title,
                        "url": url,
                        "duration": v.get("duration"),
                        "duration_str": _format_duration(v.get("duration")),
                        "view_count": None,
                        "comment_count": None,
                        **(
                            {
                                "upload_date": None,
                                "uploader": None,
                                "channel_id": None,
                                "like_count": None,
                                "thumbnail": None,
                                "description": None,
                            }
                            if full_extraction
                            else {}
                        ),
                    }
                )
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                continue

            if not e:
                continue

            row: dict = {
                "id": vid,
                "title": e.get("title") or title,
                "url": url,
                "duration": e.get("duration"),
                "duration_str": _format_duration(e.get("duration")),
                "view_count": e.get("view_count"),
                "comment_count": e.get("comment_count"),
            }
            if full_extraction:
                row.update(extract_analysis_metadata(e))

            videos.append(row)

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    return videos


def _has_full_metadata(videos: list[dict]) -> bool:
    """Check if any video has full extraction fields."""
    return any(
        v.get("upload_date") is not None or v.get("like_count") is not None
        for v in videos
    )


def export_metadata_to_csv(videos: list[dict]) -> str:
    """Export video metadata to CSV table. Easy to copy URL column for NotebookLM."""
    import csv
    import io

    out = io.StringIO()
    writer = csv.writer(out)
    has_full = _has_full_metadata(videos)

    if has_full:
        writer.writerow(
            ["Title", "URL", "Duration", "Views", "Comments", "Upload Date", "Channel", "Likes", "Thumbnail", "Description"]
        )
    else:
        writer.writerow(["Title", "URL", "Duration", "Views", "Comments"])

    for v in videos:
        views = str(v.get("view_count") or "") if v.get("view_count") is not None else ""
        comments = str(v.get("comment_count") or "") if v.get("comment_count") is not None else ""
        row = [
            (v.get("title") or "").replace("\n", " "),
            v.get("url", ""),
            v.get("duration_str", ""),
            views,
            comments,
        ]
        if has_full:
            row.extend(
                [
                    v.get("upload_date") or "",
                    (v.get("uploader") or "").replace("\n", " "),
                    str(v.get("like_count") or "") if v.get("like_count") is not None else "",
                    v.get("thumbnail") or "",
                    (v.get("description") or "").replace("\n", " "),
                ]
            )
        writer.writerow(row)
    return out.getvalue()


def export_metadata_to_markdown_table(videos: list[dict]) -> str:
    """Export video metadata to Markdown table."""
    has_full = _has_full_metadata(videos)

    if has_full:
        lines = [
            "| Title | URL | Duration | Views | Comments | Upload Date | Channel | Likes | Thumbnail |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    else:
        lines = [
            "| Title | URL | Duration | Views | Comments |",
            "| --- | --- | --- | --- | --- |",
        ]

    for v in videos:
        title = (v.get("title") or "").replace("|", "\\|").replace("\n", " ")
        url = v.get("url", "")
        duration = v.get("duration_str", "")
        views = v.get("view_count")
        views_str = f"{views:,}" if views is not None else ""
        comments = v.get("comment_count")
        comments_str = f"{comments:,}" if comments is not None else ""

        if has_full:
            upload_date = v.get("upload_date") or ""
            uploader = (v.get("uploader") or "").replace("|", "\\|").replace("\n", " ")
            likes = v.get("like_count")
            likes_str = f"{likes:,}" if likes is not None else ""
            thumb = v.get("thumbnail") or ""
            lines.append(
                f"| {title} | {url} | {duration} | {views_str} | {comments_str} | {upload_date} | {uploader} | {likes_str} | {thumb} |"
            )
        else:
            lines.append(f"| {title} | {url} | {duration} | {views_str} | {comments_str} |")

    return "\n".join(lines)


def export_urls_only(videos: list[dict]) -> str:
    """Export one URL per line for direct paste into NotebookLM."""
    return "\n".join(v.get("url", "") for v in videos)


def scrape_channel(
    channel_url: str,
    max_videos: Optional[int] = None,
    delay_seconds: float = 1.5,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    videos: Optional[list[dict]] = None,
    offset: int = 0,
    limit: Optional[int] = None,
    include_metadata: bool = False,
    generate_recommendations: bool = True,
    output_dir: Optional[str | Path] = None,
    resume: bool = False,
    min_duration: Optional[float] = None,
) -> tuple[list[ScrapedVideo], list[SkippedVideo], int]:
    """
    Scrape a YouTube channel for transcripts (and optional analysis metadata).

    When output_dir is set, each video is written to disk immediately so a long
    scrape can be stopped and resumed.
    """
    if videos is not None:
        total_count = len(videos)
        batch = videos[offset : (offset + limit) if limit is not None else len(videos)]
    else:
        all_videos = _get_channel_videos(channel_url, max_videos)
        total_count = len(all_videos)
        batch = all_videos[offset : (offset + limit) if limit is not None else len(all_videos)]

    corpus_root = Path(output_dir) if output_dir else None
    existing_ids: set[str] = set()
    if corpus_root:
        ensure_corpus_dir(corpus_root)
        if resume:
            existing_ids = load_existing_ids(corpus_root)

    scraped: list[ScrapedVideo] = []
    skipped: list[SkippedVideo] = []
    resumed = 0
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "force_generic_extractor": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) if include_metadata else nullcontext() as ydl:
        for i, v in enumerate(batch):
            video_id = v["id"]
            title = v["title"]
            url = v["url"]
            duration = v.get("duration")

            if progress_callback:
                progress_callback(i + 1, len(batch), title)

            if video_id in existing_ids:
                resumed += 1
                continue

            if min_duration and duration is not None and duration < min_duration:
                item = SkippedVideo(video_id=video_id, title=title, reason=f"Shorter than {min_duration:.0f}s")
                skipped.append(item)
                if corpus_root:
                    append_skipped(corpus_root, item.to_dict())
                continue

            meta: dict = {}
            if ydl is not None:
                try:
                    info = ydl.extract_info(url, download=False) or {}
                    meta = extract_analysis_metadata(info)
                    duration = info.get("duration") if info.get("duration") is not None else duration
                    title = info.get("title") or title
                    if min_duration and duration is not None and duration < min_duration:
                        item = SkippedVideo(
                            video_id=video_id,
                            title=title,
                            reason=f"Shorter than {min_duration:.0f}s",
                        )
                        skipped.append(item)
                        if corpus_root:
                            append_skipped(corpus_root, item.to_dict())
                        if delay_seconds > 0:
                            time.sleep(delay_seconds)
                        continue
                except Exception:
                    meta = {}

            try:
                snippets = _fetch_transcript_with_timestamps(video_id)
            except Exception as e:
                item = SkippedVideo(video_id=video_id, title=title, reason=str(e))
                skipped.append(item)
                if corpus_root:
                    append_skipped(corpus_root, item.to_dict())
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                continue

            clip_recs = (
                _generate_clip_recommendations(snippets, video_id, title)
                if generate_recommendations
                else []
            )
            screenshot_recs = (
                _generate_screenshot_recommendations(snippets, video_id, title)
                if generate_recommendations
                else []
            )

            video = ScrapedVideo(
                video_id=video_id,
                title=title,
                url=url,
                duration=duration,
                transcript=snippets,
                clip_recommendations=clip_recs,
                screenshot_recommendations=screenshot_recs,
                description=meta.get("description"),
                upload_date=meta.get("upload_date"),
                view_count=meta.get("view_count"),
                like_count=meta.get("like_count"),
                comment_count=meta.get("comment_count"),
                tags=meta.get("tags") or [],
                chapters=meta.get("chapters") or [],
                channel=meta.get("channel"),
                channel_id=meta.get("channel_id"),
                categories=meta.get("categories") or [],
                thumbnail=meta.get("thumbnail"),
                language=meta.get("language"),
            )
            scraped.append(video)

            if corpus_root:
                write_video(corpus_root, video.to_dict())
                rewrite_index(corpus_root)

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    if corpus_root:
        channel_name = next((v.channel for v in scraped if v.channel), "")
        write_manifest(
            corpus_root,
            channel_url=channel_url,
            channel_name=channel_name or "",
            scraped_count=len(scraped) + resumed,
            skipped_count=len(skipped),
            resumed_ids=resumed,
            extra={"max_videos": max_videos, "include_metadata": include_metadata},
        )
        rewrite_index(corpus_root)

    return scraped, skipped, total_count


def export_to_json(scraped: list[ScrapedVideo], skipped: list[SkippedVideo]) -> str:
    """Export scraped data to JSON string."""
    import json

    data = {
        "videos": [v.to_dict() for v in scraped],
        "skipped": [s.to_dict() for s in skipped],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def export_to_markdown(scraped: list[ScrapedVideo], skipped: list[SkippedVideo]) -> str:
    """Export scraped data to Markdown string (NotebookLM-ready)."""
    lines = ["# Channel Curriculum - Source Material for NotebookLM\n"]

    for v in scraped:
        lines.append(f"\n## {v.title}\n")
        lines.append(f"**URL:** {v.url}\n")
        if v.duration:
            lines.append(f"**Duration:** {int(v.duration // 60)} min\n")
        lines.append("\n### Transcript (with timestamps)\n\n")
        for s in v.transcript:
            ts = TranscriptSnippet.format_timestamp(s.start)
            lines.append(f"[{ts}] {s.text}\n")
        lines.append("\n### Clip Recommendations\n\n")
        for c in v.clip_recommendations:
            lines.append(
                f"- **{c.start_formatted}–{c.end_formatted}** — {c.opening_text}\n"
            )
        lines.append("\n### Screenshot Recommendations\n\n")
        for rec in v.screenshot_recommendations:
            lines.append(f"- **{rec.timestamp_formatted}** — consider screenshot for slide\n")

    if skipped:
        lines.append("\n---\n\n## Skipped Videos (no transcript)\n\n")
        for s in skipped:
            lines.append(f"- {s.title} ({s.reason})\n")

    return "".join(lines)


def export_to_markdown_from_dicts(videos: list[dict], skipped: list[dict]) -> str:
    """Export scraped data from dict format (e.g. JSON from API) to Markdown string."""
    lines = ["# Channel Curriculum - Source Material for NotebookLM\n"]

    for v in videos:
        title = v.get("title", "Unknown")
        url = v.get("url", "")
        duration = v.get("duration")
        transcript = v.get("transcript", [])
        clip_recs = v.get("clip_recommendations", [])
        screenshot_recs = v.get("screenshot_recommendations", [])

        lines.append(f"\n## {title}\n")
        lines.append(f"**URL:** {url}\n")
        if duration is not None:
            lines.append(f"**Duration:** {int(duration // 60)} min\n")
        lines.append("\n### Transcript (with timestamps)\n\n")
        for s in transcript:
            start = s.get("start", 0)
            ts = TranscriptSnippet.format_timestamp(start)
            lines.append(f"[{ts}] {s.get('text', '')}\n")
        lines.append("\n### Clip Recommendations\n\n")
        for c in clip_recs:
            sf = c.get("start_formatted", TranscriptSnippet.format_timestamp(c.get("start", 0)))
            ef = c.get("end_formatted", TranscriptSnippet.format_timestamp(c.get("end", 0)))
            lines.append(f"- **{sf}–{ef}** — {c.get('opening_text', '')}\n")
        lines.append("\n### Screenshot Recommendations\n\n")
        for rec in screenshot_recs:
            ts_fmt = rec.get("timestamp_formatted", TranscriptSnippet.format_timestamp(rec.get("timestamp", 0)))
            lines.append(f"- **{ts_fmt}** — consider screenshot for slide\n")

    if skipped:
        lines.append("\n---\n\n## Skipped Videos (no transcript)\n\n")
        for s in skipped:
            lines.append(f"- {s.get('title', 'Unknown')} ({s.get('reason', '')})\n")

    return "".join(lines)


def export_to_pdf(scraped: list[ScrapedVideo], skipped: list[SkippedVideo], output_path: str) -> None:
    """Export scraped data to PDF file. Requires reportlab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("Channel Curriculum - Source Material for NotebookLM", styles["Title"]))
        story.append(Spacer(1, 20))

        for v in scraped:
            story.append(Paragraph(v.title.replace("&", "&amp;"), styles["Heading1"]))
            story.append(Paragraph(f"URL: {v.url}", styles["Normal"]))
            story.append(Spacer(1, 10))
            story.append(Paragraph("Transcript:", styles["Heading2"]))
            for s in v.transcript[:50]:  # Limit transcript lines per video
                ts = TranscriptSnippet.format_timestamp(s.start)
                story.append(Paragraph(f"[{ts}] {s.text[:200]}", styles["Normal"]))
            story.append(Paragraph("Clip Recommendations:", styles["Heading2"]))
            for c in v.clip_recommendations[:5]:
                story.append(
                    Paragraph(
                        f"{c.start_formatted}–{c.end_formatted}: {c.opening_text[:80]}...",
                        styles["Normal"],
                    )
                )
            story.append(Spacer(1, 20))

        if skipped:
            story.append(Paragraph("Skipped Videos", styles["Heading1"]))
            for s in skipped:
                story.append(Paragraph(f"- {s.title}", styles["Normal"]))

        doc.build(story)
    except ImportError:
        raise ImportError("PDF export requires reportlab: pip install reportlab")
