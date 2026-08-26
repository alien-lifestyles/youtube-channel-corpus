#!/usr/bin/env python3
"""
CLI for building an on-disk YouTube channel corpus.

Default: transcripts + analysis metadata, written per video so you can stop and resume.
"""

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

from channel_scraper import (
    _get_channel_videos,
    _normalize_channel_url,
    export_metadata_to_csv,
    export_metadata_to_markdown_table,
    export_to_json,
    export_to_markdown,
    export_to_pdf,
    export_urls_only,
    get_channel_metadata,
    scrape_channel,
)
from corpus import channel_slug_from_url, ensure_corpus_dir


def _default_corpus_dir(channel_url: str) -> Path:
    return Path("data") / channel_slug_from_url(channel_url)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local corpus of YouTube channel transcripts and metadata for analysis."
    )
    parser.add_argument(
        "channel_url",
        help="YouTube channel URL (e.g. https://www.youtube.com/@ChannelName)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Corpus directory (default: data/<channel-slug>). For --metadata-only, a file path is also accepted.",
    )
    parser.add_argument(
        "--max-videos",
        "-n",
        type=int,
        default=None,
        help="Maximum number of videos to process (default: no limit)",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.5,
        help="Delay in seconds between fetches (default: 1.5)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=None,
        help="Skip videos shorter than this many seconds (e.g. 61 to skip most Shorts)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Transcripts only; skip per-video yt-dlp metadata (faster, less useful for analysis)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-fetch videos even if they already exist in the corpus",
    )
    parser.add_argument(
        "--recommendations",
        action="store_true",
        help="Also generate clip/screenshot recommendations (legacy curriculum mode)",
    )
    parser.add_argument(
        "--metadata-only",
        "-m",
        action="store_true",
        help="Only fetch video metadata (no transcripts). Writes index.csv / table, not a full corpus.",
    )
    parser.add_argument(
        "--full-extraction",
        action="store_true",
        help="With --metadata-only: fetch upload date, likes, description, etc. per video (slower).",
    )
    parser.add_argument(
        "--fast-playlist",
        action="store_true",
        help="With --metadata-only: one flat playlist fetch only (fast; views/comments usually empty).",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["corpus", "json", "md", "pdf", "csv", "table", "urls"],
        default="corpus",
        help="Output format. Default 'corpus' writes data/<channel>/ videos + index. Other formats are single-file dumps.",
    )

    args = parser.parse_args()

    if args.metadata_only:
        return _run_metadata_only(args)

    output_dir = Path(args.output) if args.output else _default_corpus_dir(args.channel_url)
    if args.format == "corpus":
        ensure_corpus_dir(output_dir)

    def progress(current: int, total: int, title: str) -> None:
        pbar.ncols = 80
        pbar.set_postfix_str(title[:40] + "..." if len(title) > 40 else title)
        pbar.update(1)

    channel_url = _normalize_channel_url(args.channel_url)
    try:
        videos = _get_channel_videos(channel_url, args.max_videos)
        total = len(videos)
    except Exception as e:
        print(f"Error fetching channel: {e}", file=sys.stderr)
        return 1

    if total == 0:
        print("No videos found on channel.", file=sys.stderr)
        return 1

    print(f"Found {total} videos. Writing corpus to {output_dir.resolve()}", file=sys.stderr)
    pbar = tqdm(total=total, unit="video", desc="Scraping")

    try:
        scraped, skipped, _ = scrape_channel(
            channel_url=args.channel_url,
            max_videos=args.max_videos,
            delay_seconds=args.delay,
            progress_callback=progress,
            videos=videos,
            include_metadata=not args.no_metadata,
            generate_recommendations=args.recommendations,
            output_dir=output_dir if args.format == "corpus" else None,
            resume=not args.no_resume,
            min_duration=args.min_duration,
        )
    except Exception as e:
        print(f"Error during scrape: {e}", file=sys.stderr)
        return 1
    finally:
        pbar.close()

    if skipped:
        print(f"\nSkipped {len(skipped)} videos:", file=sys.stderr)
        for s in skipped[:20]:
            print(f"  - {s.title}: {s.reason}", file=sys.stderr)
        if len(skipped) > 20:
            print(f"  ... and {len(skipped) - 20} more", file=sys.stderr)

    if args.format == "corpus":
        print(
            f"Corpus ready: {len(scraped)} new transcripts in {output_dir / 'videos'}",
            file=sys.stderr,
        )
        print(f"Index: {output_dir / 'index.csv'}", file=sys.stderr)
        return 0

    if not scraped:
        print("No videos with transcripts could be scraped.", file=sys.stderr)
        return 1

    if args.format == "json":
        out = export_to_json(scraped, skipped)
        dest = Path(args.output) if args.output else output_dir / "corpus.json"
        dest.write_text(out, encoding="utf-8")
        print(f"Wrote {dest}", file=sys.stderr)
    elif args.format == "md":
        out = export_to_markdown(scraped, skipped)
        dest = Path(args.output) if args.output else output_dir / "corpus.md"
        dest.write_text(out, encoding="utf-8")
        print(f"Wrote {dest}", file=sys.stderr)
    elif args.format == "pdf":
        dest = Path(args.output) if args.output else output_dir / "corpus.pdf"
        try:
            export_to_pdf(scraped, skipped, str(dest))
            print(f"Wrote {dest}", file=sys.stderr)
        except ImportError:
            print("PDF export requires reportlab: pip install reportlab", file=sys.stderr)
            return 1

    return 0


def _run_metadata_only(args: argparse.Namespace) -> int:
    if args.fast_playlist and args.full_extraction:
        print("Error: use either --fast-playlist or --full-extraction, not both.", file=sys.stderr)
        return 1

    channel_url = _normalize_channel_url(args.channel_url)

    if args.fast_playlist:
        print(
            "Fast playlist mode: single channel fetch (duration best-effort; views/comments often empty)...",
            file=sys.stderr,
        )
        pbar_holder: dict = {"pbar": None}

        def progress(current: int, tot: int, title: str) -> None:
            if pbar_holder["pbar"] is None:
                pbar_holder["pbar"] = tqdm(total=tot, unit="video", desc="Playlist", ncols=80)
            pbar = pbar_holder["pbar"]
            pbar.set_postfix_str(title[:40] + "..." if len(title) > 40 else title)
            pbar.update(1)

        try:
            videos = get_channel_metadata(
                channel_url=args.channel_url,
                max_videos=args.max_videos,
                progress_callback=progress,
                full_extraction=False,
                delay_seconds=0,
                fast_playlist_only=True,
            )
        except Exception as e:
            print(f"Error fetching channel: {e}", file=sys.stderr)
            return 1
        finally:
            if pbar_holder["pbar"] is not None:
                pbar_holder["pbar"].close()
    else:
        try:
            preview = _get_channel_videos(channel_url, args.max_videos)
            total = len(preview)
        except Exception as e:
            print(f"Error fetching channel: {e}", file=sys.stderr)
            return 1

        if total == 0:
            print("No videos found on channel.", file=sys.stderr)
            return 1

        pbar = tqdm(total=total, unit="video", desc="Metadata")

        def progress(current: int, tot: int, title: str) -> None:
            pbar.ncols = 80
            pbar.set_postfix_str(title[:40] + "..." if len(title) > 40 else title)
            pbar.update(1)

        if args.full_extraction:
            print("Fetching full metadata per video (~1-3 sec each)...", file=sys.stderr)
        else:
            print(
                "Fetching per-video stats (duration, views, comments; one yt-dlp request per video)...",
                file=sys.stderr,
            )
        try:
            videos = get_channel_metadata(
                channel_url=args.channel_url,
                max_videos=args.max_videos,
                progress_callback=progress,
                full_extraction=args.full_extraction,
                delay_seconds=max(0.0, args.delay),
                base_videos=preview,
            )
        except Exception as e:
            print(f"Error fetching channel: {e}", file=sys.stderr)
            return 1
        finally:
            pbar.close()

    if not videos:
        print("No videos found on channel.", file=sys.stderr)
        return 1

    fmt = args.format if args.format in ("csv", "table", "urls", "json") else "csv"

    if fmt == "csv":
        out = export_metadata_to_csv(videos)
    elif fmt == "table":
        out = export_metadata_to_markdown_table(videos)
    elif fmt == "urls":
        out = export_urls_only(videos)
    else:
        out = json.dumps(videos, indent=2, ensure_ascii=False)

    dest: Path
    if args.output:
        dest = Path(args.output)
        if dest.suffix == "":
            ensure_corpus_dir(dest)
            dest = dest / ("index.csv" if fmt == "csv" else f"metadata.{fmt}")
    else:
        dest = _default_corpus_dir(args.channel_url)
        ensure_corpus_dir(dest)
        dest = dest / ("index.csv" if fmt == "csv" else f"metadata.{fmt}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    print(f"Wrote {dest} ({len(videos)} videos)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
