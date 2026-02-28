/**
 * Log Analyzer — Frontend Application
 *
 * Handles file upload, API communication, and dynamic results rendering.
 * No framework dependencies — vanilla JS with Fetch API.
 */

(function () {
    'use strict';

    // ── DOM References ─────────────────────────────────────────────
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');
    const uploadProgress = document.getElementById('upload-progress');
    const progressText = document.getElementById('progress-text');
    const uploadSection = document.getElementById('upload-section');
    const resultsSection = document.getElementById('results-section');
    const summaryGrid = document.getElementById('summary-grid');
    const resultsList = document.getElementById('results-list');
    const errorCard = document.getElementById('error-card');
    const errorMessage = document.getElementById('error-message');
    const errorDismiss = document.getElementById('error-dismiss');
    const healthStatus = document.getElementById('health-status');
    const newAnalysisBtn = document.getElementById('new-analysis-btn');

    // ── State ──────────────────────────────────────────────────────
    let currentResults = [];
    let currentFilter = 'all';

    // ── Health Check ───────────────────────────────────────────────
    async function checkHealth() {
        try {
            const res = await fetch('/health');
            if (res.ok) {
                healthStatus.className = 'health-badge health-healthy';
                healthStatus.querySelector('.health-text').textContent = 'Online';
            } else {
                throw new Error('Unhealthy');
            }
        } catch {
            healthStatus.className = 'health-badge health-unhealthy';
            healthStatus.querySelector('.health-text').textContent = 'Offline';
        }
    }

    // ── Error Display ──────────────────────────────────────────────
    function showError(msg) {
        errorMessage.textContent = msg;
        errorCard.style.display = 'flex';
        setTimeout(() => { errorCard.style.display = 'none'; }, 8000);
    }

    function hideError() {
        errorCard.style.display = 'none';
    }

    // ── File Upload ────────────────────────────────────────────────
    function handleFileSelect(file) {
        if (!file) return;

        const ext = file.name.split('.').pop().toLowerCase();
        if (!['log', 'txt'].includes(ext)) {
            showError('Unsupported file type. Please upload a .log or .txt file.');
            return;
        }

        uploadFile(file);
    }

    async function uploadFile(file) {
        // Show progress
        uploadZone.style.display = 'none';
        uploadProgress.style.display = 'flex';
        progressText.textContent = `Analyzing ${file.name}...`;
        hideError();

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/analyze', {
                method: 'POST',
                body: formData,
            });

            const data = await res.json();

            if (!res.ok) {
                showError(data.detail || data.error || 'Analysis failed');
                resetUpload();
                return;
            }

            currentResults = data.results || [];
            renderResults(data);

        } catch (err) {
            showError(`Network error: ${err.message}`);
            resetUpload();
        }
    }

    function resetUpload() {
        uploadZone.style.display = 'block';
        uploadProgress.style.display = 'none';
        fileInput.value = '';
    }

    // ── Results Rendering ──────────────────────────────────────────
    function renderResults(data) {
        // Show results, hide upload
        uploadSection.style.display = 'none';
        resultsSection.style.display = 'block';

        // Render summary
        const summary = data.summary || {};
        const dist = summary.severity_distribution || {};

        summaryGrid.innerHTML = `
            <div class="glass-card summary-card">
                <div class="summary-label">Total Entries</div>
                <div class="summary-value">${summary.total_entries || 0}</div>
                <div class="summary-sub">${data.filename || 'Unknown file'}</div>
            </div>
            <div class="glass-card summary-card">
                <div class="summary-label">Anomalies</div>
                <div class="summary-value" style="color: var(--severity-high)">${summary.anomalies_detected || 0}</div>
                <div class="summary-sub">${summary.anomaly_percentage || 0}% of entries</div>
            </div>
            <div class="glass-card summary-card summary-critical">
                <div class="summary-label">Critical</div>
                <div class="summary-value">${dist.CRITICAL || 0}</div>
            </div>
            <div class="glass-card summary-card summary-high">
                <div class="summary-label">High</div>
                <div class="summary-value">${dist.HIGH || 0}</div>
            </div>
            <div class="glass-card summary-card summary-medium">
                <div class="summary-label">Medium</div>
                <div class="summary-value">${dist.MEDIUM || 0}</div>
            </div>
            <div class="glass-card summary-card summary-low">
                <div class="summary-label">Low</div>
                <div class="summary-value">${dist.LOW || 0}</div>
            </div>
        `;

        renderFilteredResults();
    }

    function renderFilteredResults() {
        const filtered = currentFilter === 'all'
            ? currentResults
            : currentResults.filter(r => r.severity.level === currentFilter);

        if (filtered.length === 0) {
            resultsList.innerHTML = '<div class="glass-card no-results"><p>No entries match the current filter.</p></div>';
            return;
        }

        // Sort: CRITICAL first, then HIGH, MEDIUM, LOW
        const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
        filtered.sort((a, b) => (order[a.severity.level] || 4) - (order[b.severity.level] || 4));

        resultsList.innerHTML = filtered.map((r, idx) => renderResultCard(r, idx)).join('');

        // Attach expand listeners
        document.querySelectorAll('.result-card').forEach(card => {
            card.addEventListener('click', () => {
                card.classList.toggle('expanded');
            });
        });
    }

    function renderResultCard(result, idx) {
        const entry = result.log_entry;
        const severity = result.severity;
        const anomaly = result.anomaly;
        const explanation = result.explanation;
        const severityLower = severity.level.toLowerCase();

        const message = escapeHtml(truncate(entry.message, 200));
        const fullMessage = escapeHtml(entry.raw || entry.message);

        return `
            <div class="glass-card result-card" data-severity="${severity.level}">
                <div class="result-header">
                    <div class="result-meta">
                        <span class="line-badge">L${entry.line_number}</span>
                        <span class="level-badge">${entry.log_level}</span>
                        ${entry.log_type !== 'UNCLASSIFIED' ? `<span class="line-badge">${entry.log_type}</span>` : ''}
                        ${entry.ip_address ? `<span class="line-badge">${entry.ip_address}</span>` : ''}
                    </div>
                    <span class="severity-badge severity-badge-${severityLower}">${severity.level}</span>
                </div>
                <div class="result-message">${message}</div>

                <div class="result-detail">
                    ${explanation.summary ? `
                    <div class="detail-section">
                        <h4>Summary</h4>
                        <p>${escapeHtml(explanation.summary)}</p>
                    </div>` : ''}

                    ${explanation.possible_causes && explanation.possible_causes.length ? `
                    <div class="detail-section">
                        <h4>Possible Causes</h4>
                        <ul>${explanation.possible_causes.map(c => `<li>${escapeHtml(c)}</li>`).join('')}</ul>
                    </div>` : ''}

                    ${explanation.remediation && explanation.remediation.length ? `
                    <div class="detail-section">
                        <h4>Remediation</h4>
                        <ul>${explanation.remediation.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
                    </div>` : ''}

                    <div class="detail-section">
                        <h4>Scores</h4>
                        <div class="score-grid">
                            <div class="score-item">
                                <div class="score-label">Severity Score</div>
                                <div class="score-value">${severity.score.toFixed(3)}</div>
                            </div>
                            <div class="score-item">
                                <div class="score-label">Rule Score</div>
                                <div class="score-value">${anomaly.rule_score.toFixed(3)}</div>
                            </div>
                            <div class="score-item">
                                <div class="score-label">ML Score</div>
                                <div class="score-value">${anomaly.ml_score.toFixed(3)}</div>
                            </div>
                            <div class="score-item">
                                <div class="score-label">Confidence</div>
                                <div class="score-value">${anomaly.confidence.toFixed(3)}</div>
                            </div>
                        </div>
                    </div>

                    ${explanation.confidence_note ? `
                    <p class="confidence-note">${escapeHtml(explanation.confidence_note)}</p>` : ''}

                    <div class="detail-section">
                        <h4>Raw Log Entry</h4>
                        <div class="result-message">${fullMessage}</div>
                    </div>
                </div>
            </div>
        `;
    }

    // ── Helpers ─────────────────────────────────────────────────────
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function truncate(str, max) {
        if (!str) return '';
        return str.length > max ? str.slice(0, max - 3) + '...' : str;
    }

    // ── Event Listeners ─────────────────────────────────────────────
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    uploadZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        handleFileSelect(e.target.files[0]);
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFileSelect(e.dataTransfer.files[0]);
    });

    // Filters
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            renderFilteredResults();
        });
    });

    // Error dismiss
    errorDismiss.addEventListener('click', hideError);

    // New analysis
    newAnalysisBtn.addEventListener('click', () => {
        resultsSection.style.display = 'none';
        uploadSection.style.display = 'block';
        resetUpload();
        currentResults = [];
        currentFilter = 'all';
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('.filter-btn[data-filter="all"]').classList.add('active');
    });

    // Init
    checkHealth();
    setInterval(checkHealth, 30000);
})();
