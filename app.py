import os
import re
import threading
import time
import uuid
from typing import Optional

from flask import Flask, render_template, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi

from channel_scraper import (
    _get_channel_videos,
    _normalize_channel_url,
    export_metadata_to_csv,
    export_metadata_to_markdown_table,
    export_to_markdown,
    export_to_markdown_from_dicts,
    export_urls_only,
    get_channel_overview,
    get_channel_metadata,
    scrape_channel,
)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

# In-memory job store for channel scrape progress (job_id -> {status, current, total, video_title, result, error})
_scrape_jobs: dict = {}
_scrape_jobs_lock = threading.Lock()

# Channel video list cache: key = normalized URL, value = (videos list, timestamp)
# TTL: 60 minutes. Used for batch fetching so we don't re-fetch YouTube for each batch.
_channel_video_cache: dict = {}
_channel_cache_lock = threading.Lock()
_CHANNEL_CACHE_TTL_SEC = 60 * 60

def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/get-transcript', methods=['POST'])
def get_transcript():
    """Extract and return YouTube video transcript."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        # Extract video ID from URL
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL format. Please use a valid YouTube video URL.'}), 400
        
        # Fetch transcript using the new API (v1.2.3+)
        try:
            # Create an instance of YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            
            # Try multiple methods to get transcript
            try:
                # Method 1: Direct fetch (preferred language: English)
                fetched_transcript = api.fetch(video_id, languages=('en',))
                transcript_text = ' '.join([snippet.text for snippet in fetched_transcript.snippets])
            except Exception as e1:
                try:
                    # Method 2: List available transcripts and try to find English
                    transcript_list_obj = api.list(video_id)
                    try:
                        # Try to find generated English transcript
                        transcript = transcript_list_obj.find_transcript(['en'])
                        fetched_transcript = transcript.fetch()
                        transcript_text = ' '.join([snippet.text for snippet in fetched_transcript.snippets])
                    except:
                        # If English not available, get the first available transcript
                        transcript = transcript_list_obj.find_transcript([])
                        fetched_transcript = transcript.fetch()
                        transcript_text = ' '.join([snippet.text for snippet in fetched_transcript.snippets])
                except Exception as e2:
                    # Method 3: Try to get any available transcript without language preference
                    try:
                        fetched_transcript = api.fetch(video_id, languages=())
                        transcript_text = ' '.join([snippet.text for snippet in fetched_transcript.snippets])
                    except Exception as e3:
                        # If all methods fail, raise the original error
                        raise e1
            
            if not transcript_text:
                raise Exception('Could not retrieve transcript')
            
            return jsonify({
                'success': True,
                'transcript': transcript_text,
                'video_id': video_id
            })
        
        except Exception as e:
            error_msg = str(e).lower()
            error_str = str(e)
            
            # Handle specific error types
            if 'no element found' in error_str or 'xml' in error_msg or 'line 1, column 0' in error_str:
                return jsonify({
                    'error': 'Unable to fetch transcript. This may be due to YouTube blocking the request, network issues, or the video not having captions. Please try again in a few moments or verify the video has captions enabled.'
                }), 500
            elif 'no transcript' in error_msg or 'transcripts are disabled' in error_msg or 'could not retrieve' in error_msg:
                return jsonify({
                    'error': 'Transcript not available. This video may not have captions enabled.'
                }), 404
            elif 'video unavailable' in error_msg or 'private video' in error_msg or 'video does not exist' in error_msg:
                return jsonify({
                    'error': 'Video not found or is private. Please check the URL.'
                }), 404
            else:
                return jsonify({
                    'error': f'Error fetching transcript: {str(e)}'
                }), 500
    
    except Exception as e:
        return jsonify({
            'error': f'An unexpected error occurred: {str(e)}'
        }), 500


def _get_cached_or_fetch_videos(
    channel_url: str,
    max_videos: int,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
    min_duration: Optional[float] = None,
) -> list:
    """Get channel video list from cache or fetch. Updates cache on fetch."""
    norm_url = _normalize_channel_url(channel_url)
    cache_key = (norm_url, max_videos, date_after or "", date_before or "", min_duration or 0)
    now = time.time()

    with _channel_cache_lock:
        entry = _channel_video_cache.get(cache_key)
        if entry:
            videos, ts = entry
            if now - ts < _CHANNEL_CACHE_TTL_SEC and len(videos) >= max_videos:
                return videos
        videos = _get_channel_videos(
            channel_url,
            max_videos,
            date_after=date_after,
            date_before=date_before,
            min_duration=min_duration,
        )
        _channel_video_cache[cache_key] = (videos, now)
        return videos


def _run_channel_scrape(
    job_id: str,
    channel_url: str,
    max_videos: int,
    delay: float,
    metadata_only: bool = False,
    full_extraction: bool = False,
    fast_playlist_only: bool = False,
    offset: int = 0,
    limit: int = 100,
    min_duration: Optional[float] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
) -> None:
    """Background task to scrape channel or fetch metadata only."""
    try:
        def progress(current: int, total: int, video_title: str) -> None:
            with _scrape_jobs_lock:
                if job_id in _scrape_jobs:
                    _scrape_jobs[job_id].update(
                        current=current,
                        total=total,
                        video_title=video_title,
                    )

        if metadata_only:
            videos = get_channel_metadata(
                channel_url=channel_url,
                max_videos=max_videos,
                progress_callback=progress,
                full_extraction=full_extraction,
                delay_seconds=delay,
                fast_playlist_only=fast_playlist_only and not full_extraction,
                date_after=date_after,
                date_before=date_before,
                min_duration=min_duration,
            )
            result = {
                "metadata_only": True,
                "videos": videos,
                "table": export_metadata_to_markdown_table(videos),
                "csv": export_metadata_to_csv(videos),
                "urls": export_urls_only(videos),
                "total": len(videos),
                "offset": 0,
                "has_more": False,
            }
        else:
            needed = offset + limit
            fetch_n = needed + 1
            if max_videos:
                fetch_n = min(max_videos, needed + 1)
            videos = _get_cached_or_fetch_videos(
                channel_url,
                fetch_n,
                date_after=date_after,
                date_before=date_before,
                min_duration=min_duration,
            )
            total_count = len(videos)
            scraped, skipped, _ = scrape_channel(
                channel_url=channel_url,
                max_videos=max_videos,
                delay_seconds=delay,
                progress_callback=progress,
                videos=videos,
                offset=offset,
                limit=limit,
                min_duration=min_duration,
                date_after=date_after,
                date_before=date_before,
            )
            more_listed = len(videos) > needed
            under_cap = max_videos is None or needed < max_videos
            result = {
                "metadata_only": False,
                "videos": [v.to_dict() for v in scraped],
                "skipped": [s.to_dict() for s in skipped],
                "markdown": export_to_markdown(scraped, skipped),
                "total": total_count,
                "offset": offset,
                "limit": limit,
                "has_more": more_listed and under_cap,
            }

        with _scrape_jobs_lock:
            if job_id in _scrape_jobs:
                _scrape_jobs[job_id].update(
                    status="done",
                    result=result,
                    current=_scrape_jobs[job_id].get("total", 0),
                )
    except Exception as e:
        with _scrape_jobs_lock:
            if job_id in _scrape_jobs:
                _scrape_jobs[job_id].update(status="error", error=str(e))


@app.route("/channel-info", methods=["POST"])
def channel_info_route():
    """Return channel snapshot before a scrape (count, dates, tags)."""
    try:
        data = request.get_json() or {}
        channel_url = (data.get("channel_url") or data.get("url") or "").strip()
        if not channel_url:
            return jsonify({"error": "Please provide a channel URL"}), 400
        overview = get_channel_overview(channel_url)
        return jsonify(overview)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/scrape-channel', methods=['POST'])
def scrape_channel_route():
    """Start a channel scrape job. Returns job_id for polling."""
    try:
        data = request.get_json() or {}
        channel_url = (data.get("channel_url") or data.get("url") or "").strip()
        max_videos = data.get("max_videos")
        delay = float(data.get("delay", 1.5))
        metadata_only = bool(data.get("metadata_only", False))
        full_extraction = bool(data.get("full_extraction", False))
        fast_playlist_only = bool(data.get("fast_playlist_only", False))
        offset = int(data.get("offset", 0))
        limit = int(data.get("limit", 50))
        min_duration = data.get("min_duration")
        date_after = (data.get("date_after") or "").strip() or None
        date_before = (data.get("date_before") or "").strip() or None
        if min_duration is not None and min_duration != "":
            min_duration = float(min_duration)
        else:
            min_duration = None

        if not channel_url:
            return jsonify({"error": "Please provide a channel URL"}), 400

        if max_videos is not None:
            max_videos = int(max_videos)
            if max_videos < 1 or max_videos > 2000:
                return jsonify({"error": "max_videos must be between 1 and 2000"}), 400

        if limit < 1 or limit > 200:
            return jsonify({"error": "limit must be between 1 and 200"}), 400

        if offset < 0:
            return jsonify({"error": "offset must be >= 0"}), 400

        job_id = str(uuid.uuid4())
        with _scrape_jobs_lock:
            _scrape_jobs[job_id] = {
                "status": "running",
                "current": 0,
                "total": 0,
                "video_title": "",
            }

        # Delay between per-video requests (metadata: stats + optional full fields; curriculum: transcripts)
        effective_delay = delay
        thread = threading.Thread(
            target=_run_channel_scrape,
            args=(
                job_id,
                channel_url,
                max_videos,
                effective_delay,
                metadata_only,
                full_extraction,
                fast_playlist_only,
                offset,
                limit,
                min_duration,
                date_after,
                date_before,
            ),
        )
        thread.daemon = True
        thread.start()

        return jsonify({"job_id": job_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/export-markdown', methods=['POST'])
def export_markdown_route():
    """Export accumulated videos and skipped to markdown. Used for Copy when batching."""
    try:
        data = request.get_json() or {}
        videos = data.get("videos", [])
        skipped = data.get("skipped", [])

        if not isinstance(videos, list) or not isinstance(skipped, list):
            return jsonify({"error": "videos and skipped must be arrays"}), 400

        markdown = export_to_markdown_from_dicts(videos, skipped)
        return jsonify({"markdown": markdown})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/scrape-channel/status/<job_id>')
def scrape_channel_status(job_id):
    """Poll for channel scrape progress and result."""
    with _scrape_jobs_lock:
        job = _scrape_jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] == "done":
        return jsonify({
            "status": "done",
            "result": job["result"],
        })

    if job["status"] == "error":
        return jsonify({
            "status": "error",
            "error": job.get("error", "Unknown error"),
        })

    return jsonify({
        "status": "running",
        "current": job.get("current", 0),
        "total": job.get("total", 0),
        "video_title": job.get("video_title", ""),
    })


if __name__ == '__main__':
    port = int(os.environ.get("PORT", "3000"))
    debug = os.environ.get("YT_SCRAPER_DEBUG", "0") == "1"
    app.run(debug=debug, host="127.0.0.1", port=port, use_reloader=debug)

