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
        });
    });

    // Channel form
    const channelForm = document.getElementById('channel-form');
    const channelUrlInput = document.getElementById('channel-url');
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

    const metadataOnlyCheckbox = document.getElementById('metadata-only');
    const fullExtractionCheckbox = document.getElementById('full-extraction');
    const fastPlaylistLabel = document.getElementById('fast-playlist-label');
    const fastPlaylistCheckbox = document.getElementById('fast-playlist');
    const fastPlaylistHint = document.getElementById('fast-playlist-hint');
    const fullExtractionLabel = document.getElementById('full-extraction-label');
    const fullExtractionHint = document.getElementById('full-extraction-hint');
    const delayLabel = document.getElementById('delay-label');
    const batchSizeLabel = document.getElementById('batch-size-label');
    const batchSizeSelect = document.getElementById('batch-size');
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

    function syncMetadataOptionUi() {
        const meta = metadataOnlyCheckbox.checked;
        const fast = fastPlaylistCheckbox.checked;
        const full = fullExtractionCheckbox.checked;
        fastPlaylistLabel.style.display = meta ? 'flex' : 'none';
        fastPlaylistHint.style.display = meta && fast ? 'block' : 'none';
        fullExtractionLabel.style.display = meta ? 'flex' : 'none';
        fullExtractionHint.style.display = meta && full ? 'block' : 'none';
        delayLabel.style.display = meta && !fast ? 'flex' : (meta ? 'none' : 'flex');
        batchSizeLabel.style.display = meta ? 'none' : 'flex';
    }

    metadataOnlyCheckbox.addEventListener('change', function() {
        const checked = this.checked;
        if (!checked) {
            fullExtractionCheckbox.checked = false;
            fastPlaylistCheckbox.checked = false;
        }
        syncMetadataOptionUi();
    });
    fastPlaylistCheckbox.addEventListener('change', function() {
        if (this.checked) fullExtractionCheckbox.checked = false;
        syncMetadataOptionUi();
    });
    fullExtractionCheckbox.addEventListener('change', function() {
        if (this.checked) fastPlaylistCheckbox.checked = false;
        syncMetadataOptionUi();
    });
    syncMetadataOptionUi();

    async function runChannelScrape(url, maxVideos, delay, metadataOnly, fullExtraction, fastPlaylistOnly, offset, limit) {
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
                limit: limit
            })
        });
        const startData = await startRes.json();
        if (!startRes.ok) {
            throw new Error(startData.error || 'Failed to start scrape');
        }
        return startData.job_id;
    }

    channelForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const url = channelUrlInput.value.trim();
        const maxVideos = parseInt(document.getElementById('max-videos').value, 10) || 200;
        const delay = parseFloat(document.getElementById('channel-delay').value) || 1.5;
        const metadataOnly = metadataOnlyCheckbox.checked;
        const fullExtraction = metadataOnly && fullExtractionCheckbox.checked;
        const fastPlaylistOnly = metadataOnly && fastPlaylistCheckbox.checked && !fullExtraction;
        const batchSize = metadataOnly ? 100 : (parseInt(batchSizeSelect.value, 10) || 100);

        if (!url) {
            showError('Please enter a channel URL');
            return;
        }

        hideError();
        hideTranscript();
        hideChannelResult();
        loadNextBtn.style.display = 'none';
        setChannelLoadingState(true);
        channelProgress.style.display = 'block';
        channelProgressText.textContent = metadataOnly
            ? (fastPlaylistOnly ? 'Loading channel playlist (fast)...' : 'Fetching metadata...')
            : 'Starting...';
        channelProgressFill.style.width = '0%';

        try {
            const jobId = await runChannelScrape(url, maxVideos, delay, metadataOnly, fullExtraction, fastPlaylistOnly, 0, batchSize);
            const pollInterval = setInterval(async () => {
                const statusRes = await fetch('/scrape-channel/status/' + jobId);
                const status = await statusRes.json();
                if (status.status === 'running') {
                    const mode = fullExtraction ? 'full metadata' : (fastPlaylistOnly ? 'playlist' : (metadataOnly ? 'metadata' : 'transcript'));
                    channelProgressText.textContent = status.total
                        ? `Fetching ${mode} ${status.current} of ${status.total}: ${(status.video_title || '').substring(0, 40)}...`
                        : `Fetching ${fullExtraction ? 'full metadata' : (fastPlaylistOnly ? 'playlist' : (metadataOnly ? 'metadata' : 'transcripts'))}...`;
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
    });

    loadNextBtn.addEventListener('click', async function() {
        if (!lastChannelUrl) return;
        loadNextBtn.disabled = true;
        const nextOffset = accumulatedVideos.length + accumulatedSkipped.length;
        const maxVideos = parseInt(document.getElementById('max-videos').value, 10) || 200;
        const delay = parseFloat(document.getElementById('channel-delay').value) || 1.5;
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
                        ? `Fetching transcript ${status.current} of ${status.total}: ${(status.video_title || '').substring(0, 40)}...`
                        : 'Fetching transcripts...';
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
            channelResultTitle.textContent = 'Channel Video List (NotebookLM URLs)';
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

            channelResultTitle.textContent = 'Channel Curriculum';
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

    downloadCsvBtn.addEventListener('click', function() {
        if (!lastChannelResult || !lastChannelResult.csv) return;
        const blob = new Blob([lastChannelResult.csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'channel_videos.csv';
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

