document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('transcript-form');
    const urlInput = document.getElementById('youtube-url');
    const getTranscriptBtn = document.getElementById('get-transcript-btn');
    const btnText = getTranscriptBtn.querySelector('.btn-text');
    const btnLoader = getTranscriptBtn.querySelector('.btn-loader');
    const transcriptContainer = document.getElementById('transcript-container');
    const transcriptText = document.getElementById('transcript-text');
    const errorMessage = document.getElementById('error-message');
    const copyBtn = document.getElementById('copy-btn');
    const copyText = copyBtn.querySelector('.copy-text');

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tab = this.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(tab + '-tab').classList.add('active');
            hideError();
            hideTranscript();
            hideChannelResult();
            if (typeof hideScrapeConfirm === 'function') hideScrapeConfirm();
        });
    });

    // Channel form
    const channelForm = document.getElementById('channel-form');
    const channelUrlInput = document.getElementById('channel-url');
    const getChannelInfoBtn = document.getElementById('get-channel-info-btn');
    const channelInfoPanel = document.getElementById('channel-info-panel');
    let lastChannelSlug = '';
    const scrapeChannelBtn = document.getElementById('scrape-channel-btn');
    const channelBtnText = scrapeChannelBtn.querySelector('.btn-text');
    const channelBtnLoader = scrapeChannelBtn.querySelector('.btn-loader');
    const channelProgress = document.getElementById('channel-progress');
    const channelProgressText = document.getElementById('channel-progress-text');
    const channelProgressFill = document.getElementById('channel-progress-fill');
    const channelResultContainer = document.getElementById('channel-result-container');
    const channelResultText = document.getElementById('channel-result-text');
    const copyChannelBtn = document.getElementById('copy-channel-btn');
    const copyChannelText = copyChannelBtn.querySelector('.copy-channel-text');

    const delayLabel = document.getElementById('delay-label');
    const batchSizeLabel = document.getElementById('batch-size-label');
    const batchSizeSelect = document.getElementById('batch-size');
    const listStyleFieldset = document.getElementById('list-style-fieldset');
    const scrapeSummary = document.getElementById('scrape-summary');
    const scrapeConfirm = document.getElementById('scrape-confirm');
    const scrapeConfirmText = document.getElementById('scrape-confirm-text');
    const scrapeConfirmStart = document.getElementById('scrape-confirm-start');
    const scrapeConfirmCancel = document.getElementById('scrape-confirm-cancel');
    const loadNextBtn = document.getElementById('load-next-btn');
    const loadNextText = loadNextBtn.querySelector('.load-next-text');
    const copyUrlsBtn = document.getElementById('copy-urls-btn');
    const copyUrlsText = copyUrlsBtn.querySelector('.copy-urls-text');
    const downloadCsvBtn = document.getElementById('download-csv-btn');
    const downloadCsvText = downloadCsvBtn.querySelector('.download-csv-text');
    const channelResultTitle = document.getElementById('channel-result-title');
    let lastChannelResult = null;
    let accumulatedVideos = [];
    let accumulatedSkipped = [];
    let lastChannelUrl = '';
    let lastOffset = 0;
    let lastBatchSize = 100;

    function getScrapeOptions() {
        const goal = document.querySelector('input[name="scrape-goal"]:checked')?.value || 'captions';
        const listStyle = document.querySelector('input[name="list-style"]:checked')?.value || 'quick';
        const metadataOnly = goal === 'list';
        const fullExtraction = metadataOnly && listStyle === 'full';
        const fastPlaylistOnly = metadataOnly && listStyle === 'quick';
        const maxVideos = parseInt(document.getElementById('max-videos').value, 10) || 200;
        const delay = parseFloat(document.getElementById('channel-delay').value) || 1.5;
        const batchSize = metadataOnly ? 50 : (parseInt(batchSizeSelect.value, 10) || 50);
        const year = document.querySelector('.year-btn.active')?.dataset.year || '';
        const dateAfter = year ? `${year}-01-01` : '';
        const dateBefore = year ? `${year}-12-31` : '';
        const skipShorts = document.getElementById('skip-shorts')?.checked;
        const minDuration = skipShorts ? 61 : null;
        return {
            goal,
            listStyle,
            metadataOnly,
            fullExtraction,
            fastPlaylistOnly,
            maxVideos,
            delay,
            batchSize,
            dateAfter,
            dateBefore,
            minDuration,
        };
    }

    function describeScrape(opts) {
        const n = opts.maxVideos;
        let dateBit = '';
        if (opts.dateAfter && opts.dateBefore) {
            dateBit = ` Only videos from ${opts.dateAfter.slice(0, 4)}.`;
        }
        const shortsBit = opts.minDuration ? ' Shorts under 1 minute are skipped.' : '';
        if (!opts.metadataOnly) {
            const mins = Math.max(1, Math.round((Math.min(n, opts.batchSize) * opts.delay) / 60));
            return `Up to ${n} videos, newest first. You’ll get captions (YouTube’s caption track, same as Show transcript). Videos with no captions are skipped.${shortsBit}${dateBit} About ${opts.delay} seconds between videos. This page: ${opts.batchSize} (YouTube lists 50 at a time); you can load more after. Roughly ${mins} minute(s) for this batch.`;
        }
        if (opts.fastPlaylistOnly) {
            return `Up to ${n} videos. Titles and links only. No captions. Fast. Length and views may be blank.${shortsBit}${dateBit}`;
        }
        return `Up to ${n} videos. Titles, links, and extra details (date, likes, description) when YouTube provides them. No captions. Slower — about ${opts.delay} seconds per video.${shortsBit}${dateBit}`;
    }

    function syncScrapeOptionUi() {
        const opts = getScrapeOptions();
        listStyleFieldset.hidden = !opts.metadataOnly;
        batchSizeLabel.style.display = opts.metadataOnly ? 'none' : 'flex';
        delayLabel.style.display = opts.fastPlaylistOnly ? 'none' : 'flex';
        scrapeSummary.textContent = describeScrape(opts);
        scrapeConfirmText.textContent = describeScrape(opts) + ' Start this scrape?';
    }

    function hideScrapeConfirm() {
        scrapeConfirm.hidden = true;
    }

    document.querySelectorAll('input[name="scrape-goal"], input[name="list-style"]').forEach((el) => {
        el.addEventListener('change', syncScrapeOptionUi);
    });
    function renderYearButtons(startYear, endYear) {
        const wrap = document.getElementById('year-buttons');
        const selected = document.querySelector('.year-btn.active')?.dataset.year || '';
        const years = [];
        for (let y = endYear; y >= startYear; y--) years.push(String(y));
        wrap.innerHTML = `<button type="button" class="year-btn ${selected ? '' : 'active'}" data-year="">All years</button>` +
            years.map((y) => `<button type="button" class="year-btn ${selected === y ? 'active' : ''}" data-year="${y}">${y}</button>`).join('');
        wrap.querySelectorAll('.year-btn').forEach((btn) => {
            btn.addEventListener('click', function() {
                wrap.querySelectorAll('.year-btn').forEach((b) => b.classList.remove('active'));
                this.classList.add('active');
                syncScrapeOptionUi();
            });
        });
        if (selected && !years.includes(selected)) {
            wrap.querySelector('[data-year=""]')?.classList.add('active');
        }
    }

    const thisYear = new Date().getFullYear();
    renderYearButtons(thisYear - 12, thisYear);

    document.getElementById('max-videos').addEventListener('input', syncScrapeOptionUi);
    document.getElementById('channel-delay').addEventListener('input', syncScrapeOptionUi);
    document.getElementById('skip-shorts').addEventListener('change', syncScrapeOptionUi);
    batchSizeSelect.addEventListener('change', syncScrapeOptionUi);
    syncScrapeOptionUi();

    async function runChannelScrape(url, maxVideos, delay, metadataOnly, fullExtraction, fastPlaylistOnly, offset, limit) {
        const extra = getScrapeOptions();
        const startRes = await fetch('/scrape-channel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                channel_url: url,
                max_videos: maxVideos,
                delay: delay,
                metadata_only: metadataOnly,
                full_extraction: fullExtraction,
                fast_playlist_only: fastPlaylistOnly,
                offset: offset,
                limit: limit,
                min_duration: extra.minDuration,
                date_after: extra.dateAfter || null,
                date_before: extra.dateBefore || null,
            })
        });
        const startData = await startRes.json();
        if (!startRes.ok) {
            throw new Error(startData.error || 'Failed to start scrape');
        }
        return startData.job_id;
    }

    function progressLabel(opts) {
        if (!opts.metadataOnly) return 'captions';
        if (opts.fastPlaylistOnly) return 'video list';
        return 'video details';
    }

    async function startChannelScrape() {
        const url = channelUrlInput.value.trim();
        const opts = getScrapeOptions();
        const { maxVideos, delay, metadataOnly, fullExtraction, fastPlaylistOnly, batchSize } = opts;

        hideScrapeConfirm();
        hideError();
        hideTranscript();
        hideChannelResult();
        loadNextBtn.style.display = 'none';
        setChannelLoadingState(true);
        channelProgress.style.display = 'block';
        channelProgressText.textContent = opts.metadataOnly
            ? (opts.fastPlaylistOnly ? 'Loading channel list…' : 'Fetching video details…')
            : 'Starting captions…';
        channelProgressFill.style.width = '0%';

        try {
            const jobId = await runChannelScrape(url, maxVideos, delay, metadataOnly, fullExtraction, fastPlaylistOnly, 0, batchSize);
            const label = progressLabel(opts);
            const pollInterval = setInterval(async () => {
                const statusRes = await fetch('/scrape-channel/status/' + jobId);
                const status = await statusRes.json();
                if (status.status === 'running') {
                    channelProgressText.textContent = status.total
                        ? `Fetching ${label} ${status.current} of ${status.total}: ${(status.video_title || '').substring(0, 40)}…`
                        : `Fetching ${label}…`;
                    channelProgressFill.style.width = status.total ? (status.current / status.total * 100) + '%' : '30%';
                } else if (status.status === 'done') {
                    clearInterval(pollInterval);
                    setChannelLoadingState(false);
                    channelProgress.style.display = 'none';
                    displayChannelResult(status.result, url, 0, batchSize);
                } else if (status.status === 'error') {
                    clearInterval(pollInterval);
                    setChannelLoadingState(false);
                    channelProgress.style.display = 'none';
                    showError(status.error || 'Scrape failed');
                }
            }, 500);
        } catch (error) {
            setChannelLoadingState(false);
            channelProgress.style.display = 'none';
            showError(error.message || 'Network error');
            console.error(error);
        }
    }

    channelForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const url = channelUrlInput.value.trim();
        if (!url) {
            showError('Please enter a channel URL');
            return;
        }
        hideError();
        syncScrapeOptionUi();
        scrapeConfirm.hidden = false;
        scrapeConfirm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    scrapeConfirmStart.addEventListener('click', startChannelScrape);
    scrapeConfirmCancel.addEventListener('click', hideScrapeConfirm);

    loadNextBtn.addEventListener('click', async function() {
        if (!lastChannelUrl) return;
        loadNextBtn.disabled = true;
        const nextOffset = accumulatedVideos.length + accumulatedSkipped.length;
        const maxVideos = parseInt(document.getElementById('max-videos').value, 10) || 200;
        const delay = getScrapeOptions().delay;
        const metadataOnly = false;
        const fullExtraction = false;

        hideError();
        setChannelLoadingState(true);
        channelProgress.style.display = 'block';
        channelProgressText.textContent = `Fetching batch starting at video ${nextOffset + 1}...`;
        channelProgressFill.style.width = '0%';

        try {
            const jobId = await runChannelScrape(lastChannelUrl, maxVideos, delay, metadataOnly, fullExtraction, false, nextOffset, lastBatchSize);
            const pollInterval = setInterval(async () => {
                const statusRes = await fetch('/scrape-channel/status/' + jobId);
                const status = await statusRes.json();
                if (status.status === 'running') {
                    channelProgressText.textContent = status.total
                        ? `Fetching captions ${status.current} of ${status.total}: ${(status.video_title || '').substring(0, 40)}...`
                        : 'Fetching captions...';
                    channelProgressFill.style.width = status.total ? (status.current / status.total * 100) + '%' : '30%';
                } else if (status.status === 'done') {
                    clearInterval(pollInterval);
                    setChannelLoadingState(false);
                    channelProgress.style.display = 'none';
                    loadNextBtn.disabled = false;
                    displayChannelResult(status.result, lastChannelUrl, nextOffset, lastBatchSize);
                } else if (status.status === 'error') {
                    clearInterval(pollInterval);
                    setChannelLoadingState(false);
                    channelProgress.style.display = 'none';
                    loadNextBtn.disabled = false;
                    showError(status.error || 'Scrape failed');
                }
            }, 500);
        } catch (error) {
            setChannelLoadingState(false);
            channelProgress.style.display = 'none';
            loadNextBtn.disabled = false;
            showError(error.message || 'Network error');
            console.error(error);
        }
    });

    copyChannelBtn.addEventListener('click', async function() {
        let text;
        if (lastChannelResult?.metadata_only) {
            text = channelResultText.textContent;
        } else if (accumulatedVideos.length > 0 || accumulatedSkipped.length > 0) {
            try {
                const res = await fetch('/export-markdown', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ videos: accumulatedVideos, skipped: accumulatedSkipped })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Export failed');
                text = data.markdown;
            } catch (e) {
                showError(e.message || 'Failed to export');
                return;
            }
        } else {
            text = channelResultText.textContent;
        }
        try {
            await navigator.clipboard.writeText(text);
            const orig = copyChannelText.textContent;
            copyChannelText.textContent = 'Copied!';
            copyChannelBtn.classList.add('copied');
            setTimeout(() => {
                copyChannelText.textContent = orig;
                copyChannelBtn.classList.remove('copied');
            }, 2000);
        } catch (err) {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
                copyChannelText.textContent = 'Copied!';
                copyChannelBtn.classList.add('copied');
                setTimeout(() => {
                    copyChannelText.textContent = orig;
                    copyChannelBtn.classList.remove('copied');
                }, 2000);
            } catch (e) {
                showError('Failed to copy');
            }
            document.body.removeChild(ta);
        }
    });

    function setChannelLoadingState(loading) {
        scrapeChannelBtn.disabled = loading;
        channelBtnText.style.display = loading ? 'none' : 'inline';
        channelBtnLoader.style.display = loading ? 'inline-block' : 'none';
    }

    function displayChannelResult(result, channelUrl, offset, batchSize) {
        hideTranscript();
        if (result.metadata_only) {
            lastChannelResult = result;
            accumulatedVideos = [];
            accumulatedSkipped = [];
            loadNextBtn.style.display = 'none';
            channelResultTitle.textContent = 'Channel results (video list)';
            channelResultText.textContent = result.table || '';
            channelResultText.classList.add('table-content');
            copyChannelBtn.querySelector('.copy-channel-text').textContent = 'Copy Table';
            copyUrlsBtn.style.display = 'inline-flex';
            downloadCsvBtn.style.display = 'inline-flex';
        } else {
            if (offset === 0) {
                accumulatedVideos = result.videos || [];
                accumulatedSkipped = result.skipped || [];
            } else {
                accumulatedVideos = accumulatedVideos.concat(result.videos || []);
                accumulatedSkipped = accumulatedSkipped.concat(result.skipped || []);
            }
            lastChannelUrl = channelUrl || lastChannelUrl;
            lastOffset = offset;
            lastBatchSize = batchSize || 100;

            lastChannelResult = {
                metadata_only: false,
                videos: accumulatedVideos,
                skipped: accumulatedSkipped,
                markdown: result.markdown
            };

            channelResultTitle.textContent = 'Channel results';
            const displayMd = accumulatedVideos.length > 0 ? result.markdown : '';
            if (offset > 0) {
                const prevMd = channelResultText.textContent || '';
                channelResultText.textContent = prevMd + (prevMd.endsWith('\n') ? '' : '\n\n') + displayMd.replace(/^# Channel Curriculum[^\n]*\n\n?/i, '');
            } else {
                channelResultText.textContent = displayMd;
            }
            channelResultText.classList.remove('table-content');
            copyChannelBtn.querySelector('.copy-channel-text').textContent = 'Copy Markdown';
            copyUrlsBtn.style.display = 'none';
            downloadCsvBtn.style.display = 'none';

            if (result.has_more) {
                loadNextText.textContent = 'Load next ' + lastBatchSize;
                loadNextBtn.style.display = 'inline-flex';
            } else {
                loadNextBtn.style.display = 'none';
            }
        }
        channelResultContainer.style.display = 'block';
        channelResultContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function isoToMmddyyyy(iso) {
        if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return '';
        return iso.slice(5, 7) + iso.slice(8, 10) + iso.slice(0, 4);
    }

    function downloadFilename(ext) {
        const fromUrl = (channelUrlInput.value.match(/@([^/?]+)/) || [])[1];
        const slug = lastChannelSlug || (fromUrl ? fromUrl.replace(/[^A-Za-z0-9]+/g, '') : '') || 'channel';
        const year = document.querySelector('.year-btn.active')?.dataset.year || '';
        const range = year ? `0101${year}_1231${year}` : 'all';
        return `${slug}_${range}.${ext}`;
    }

    getChannelInfoBtn.addEventListener('click', async function() {
        const url = channelUrlInput.value.trim();
        if (!url) {
            showError('Please enter a channel URL');
            return;
        }
        hideError();
        getChannelInfoBtn.disabled = true;
        getChannelInfoBtn.textContent = 'Looking up…';
        channelInfoPanel.hidden = false;
        channelInfoPanel.innerHTML = '<p>Fetching channel info (this can take ~10–20 seconds)…</p>';
        try {
            const res = await fetch('/channel-info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel_url: url }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Could not fetch channel info');
            lastChannelSlug = data.slug || '';
            const oldestY = parseInt((data.oldest_date || '').slice(0, 4), 10);
            const newestY = parseInt((data.newest_date || '').slice(0, 4), 10);
            if (oldestY && newestY) {
                renderYearButtons(oldestY, newestY);
            }
            const tags = (data.tags || []).join(', ') || '—';
            const subs = data.subscriber_count != null
                ? Number(data.subscriber_count).toLocaleString()
                : '—';
            channelInfoPanel.innerHTML = `
                <h3>${data.channel || 'Channel'}</h3>
                <dl>
                    <dt>Videos</dt><dd>${data.video_count ?? '—'}</dd>
                    <dt>Subscribers</dt><dd>${subs}</dd>
                    <dt>First published</dt><dd>${data.oldest_date || '—'} ${data.oldest_title ? ' — ' + data.oldest_title : ''}</dd>
                    <dt>Latest video</dt><dd>${data.newest_date || '—'} ${data.newest_title ? ' — ' + data.newest_title : ''}</dd>
                    <dt>Tags / topics</dt><dd>${tags}</dd>
                </dl>
            `;
        } catch (err) {
            channelInfoPanel.hidden = true;
            showError(err.message || 'Could not fetch channel info');
        } finally {
            getChannelInfoBtn.disabled = false;
            getChannelInfoBtn.textContent = 'Get channel info';
        }
    });

    downloadCsvBtn.addEventListener('click', function() {
        if (!lastChannelResult || !lastChannelResult.csv) return;
        const blob = new Blob([lastChannelResult.csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = downloadFilename('csv');
        a.click();
        URL.revokeObjectURL(url);
    });

    copyUrlsBtn.addEventListener('click', async function() {
        if (!lastChannelResult || !lastChannelResult.urls) return;
        const text = lastChannelResult.urls;
        try {
            await navigator.clipboard.writeText(text);
            const orig = copyUrlsText.textContent;
            copyUrlsText.textContent = 'Copied!';
            copyUrlsBtn.classList.add('copied');
            setTimeout(() => {
                copyUrlsText.textContent = orig;
                copyUrlsBtn.classList.remove('copied');
            }, 2000);
        } catch (err) {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
                copyUrlsText.textContent = 'Copied!';
                copyUrlsBtn.classList.add('copied');
                setTimeout(() => {
                    copyUrlsText.textContent = 'Copy URLs';
                    copyUrlsBtn.classList.remove('copied');
                }, 2000);
            } catch (e) {
                showError('Failed to copy');
            }
            document.body.removeChild(ta);
        }
    });

    function hideChannelResult() {
        channelResultContainer.style.display = 'none';
        loadNextBtn.style.display = 'none';
        accumulatedVideos = [];
        accumulatedSkipped = [];
        lastChannelUrl = '';
        lastOffset = 0;
    }

    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const url = urlInput.value.trim();
        
        if (!url) {
            showError('Please enter a YouTube URL');
            return;
        }

        // Hide previous results
        hideError();
        hideTranscript();
        
        // Show loading state
        setLoadingState(true);

        try {
            const response = await fetch('/get-transcript', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                hideChannelResult();
                displayTranscript(data.transcript);
            } else {
                showError(data.error || 'Failed to fetch transcript');
            }
        } catch (error) {
            showError('Network error. Please check your connection and try again.');
            console.error('Error:', error);
        } finally {
            setLoadingState(false);
        }
    });

    // Copy to clipboard functionality
    copyBtn.addEventListener('click', async function() {
        const text = transcriptText.textContent;
        
        try {
            await navigator.clipboard.writeText(text);
            
            // Visual feedback
            const originalText = copyText.textContent;
            copyText.textContent = 'Copied!';
            copyBtn.classList.add('copied');
            
            setTimeout(() => {
                copyText.textContent = originalText;
                copyBtn.classList.remove('copied');
            }, 2000);
        } catch (err) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            
            try {
                document.execCommand('copy');
                const originalText = copyText.textContent;
                copyText.textContent = 'Copied!';
                copyBtn.classList.add('copied');
                
                setTimeout(() => {
                    copyText.textContent = originalText;
                    copyBtn.classList.remove('copied');
                }, 2000);
            } catch (fallbackErr) {
                showError('Failed to copy to clipboard');
            }
            
            document.body.removeChild(textArea);
        }
    });

    function setLoadingState(loading) {
        if (loading) {
            getTranscriptBtn.disabled = true;
            btnText.style.display = 'none';
            btnLoader.style.display = 'inline-block';
        } else {
            getTranscriptBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    }

    function displayTranscript(text) {
        transcriptText.textContent = text;
        transcriptContainer.style.display = 'block';
        transcriptContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function hideTranscript() {
        transcriptContainer.style.display = 'none';
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    }

    function hideError() {
        errorMessage.style.display = 'none';
    }
});

