/**
 * SwasthAI — Medical Report Analyzer UI Logic.
 *
 * Uploads a lab-report PDF to POST /report-analysis/analyze and renders
 * whatever the backend returns (recognized values, summary, follow-up
 * questions, disclaimer). This file never computes or guesses a value's
 * status itself — the backend's rule-based extractor is the sole source
 * of truth (AGENTS.md Section 11). The "N values need attention" headline
 * below is purely a display aggregate of statuses the backend already
 * assigned, not a new judgment call.
 */
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('reportFileInput');
    const uploadArea = document.getElementById('uploadAreaReport');
    const browseBtn = document.getElementById('reportBrowseBtn');
    const processingArea = document.getElementById('processingAreaReport');
    const processingTitle = document.getElementById('processingReportTitle');
    const errorMsg = document.getElementById('reportErrorMsg');
    const errorText = document.getElementById('reportErrorText');

    const resultArea = document.getElementById('reportResultArea');
    const statusHeadline = document.getElementById('reportStatusHeadline');
    const summaryText = document.getElementById('reportSummaryText');
    const explanationSection = document.getElementById('reportExplanationSection');
    const explanationText = document.getElementById('reportExplanationText');
    const valuesSection = document.getElementById('reportValuesSection');
    const valuesList = document.getElementById('reportValuesList');
    const screeningSection = document.getElementById('reportScreeningSection');
    const screeningList = document.getElementById('reportScreeningList');
    const questionsSection = document.getElementById('reportQuestionsSection');
    const questionsList = document.getElementById('reportQuestionsList');
    const disclaimerText = document.getElementById('reportDisclaimerText');
    const resetBtn = document.getElementById('reportResetBtn');

    const STATUS_BADGE_CLASS = { high: 'badge-danger', low: 'badge-danger', normal: 'badge-success', abnormal: 'badge-danger' };
    const STATUS_LABELS = { high: 'High', low: 'Low', normal: 'Normal', abnormal: 'Reactive/Positive' };

    // Recognized values are grouped by panel rather than shown as one flat
    // list — the backend already tags each value with the category it
    // belongs to (cbc, lipid, etc.), so this is purely a display grouping,
    // not a new judgment call. Order here is the order panels appear in
    // the results; anything with an unlisted category still renders,
    // just after these.
    const CATEGORY_ORDER = ['cbc', 'lipid', 'liver', 'kidney', 'thyroid', 'glucose', 'iron', 'vitamins', 'vitals'];
    const CATEGORY_LABELS = {
        cbc: 'Complete Blood Count',
        lipid: 'Lipid Profile',
        liver: 'Liver Function',
        kidney: 'Kidney Function',
        thyroid: 'Thyroid Panel',
        glucose: 'Blood Sugar',
        iron: 'Iron Studies',
        vitamins: 'Vitamins',
        vitals: 'Vitals',
    };

    browseBtn.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('click', (e) => {
        if (e.target !== browseBtn) fileInput.click();
    });
    uploadArea.addEventListener('keydown', (e) => {
        if (e.target === browseBtn) return;
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    ['dragleave', 'dragend'].forEach((type) => {
        uploadArea.addEventListener(type, () => uploadArea.classList.remove('drag-over'));
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    resetBtn.addEventListener('click', () => {
        resultArea.style.display = 'none';
        uploadArea.style.display = 'block';
        fileInput.value = '';
    });

    const SUPPORTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'];

    function handleFile(file) {
        hideError();

        if (!SUPPORTED_TYPES.includes(file.type)) {
            showError('Unsupported file type. Please upload a PDF, or a JPEG/PNG photo or scan of your report.');
            return;
        }

        const maxSize = 15 * 1024 * 1024; // 15MB
        if (file.size > maxSize) {
            showError('File is too large. Maximum size is 15MB.');
            return;
        }

        analyzeReport(file);
    }

    async function analyzeReport(file) {
        uploadArea.style.display = 'none';
        processingArea.style.display = 'block';
        // Images go through OCR plus an explanation step (two model calls
        // on a free-tier model) and can genuinely take up to a minute or
        // so, unlike a text-based PDF which is near-instant — set that
        // expectation so it doesn't look stuck.
        processingTitle.textContent = file.type === 'application/pdf'
            ? 'Extracting text and analyzing…'
            : 'Reading your photo and analyzing (this can take up to a minute)…';

        try {
            const data = await SwasthAPI.reportAnalysis.analyze(file);
            showResult(data);
        } catch (err) {
            console.error('Report analysis failed:', err);
            processingArea.style.display = 'none';
            uploadArea.style.display = 'block';
            showError(err.message || 'An unexpected error occurred while analyzing the report.');
        } finally {
            fileInput.value = '';
        }
    }

    function buildStatusHeadline(data) {
        const values = data.values || [];
        const screenings = data.qualitative_results || [];
        const total = values.length + screenings.length;
        const abnormalCount = values.filter((v) => v.status !== 'normal').length
            + screenings.filter((q) => q.status === 'abnormal').length;

        resultArea.classList.remove('status-clear', 'status-attention', 'status-unrecognized');

        if (total === 0) {
            resultArea.classList.add('status-unrecognized');
            statusHeadline.innerHTML = '<i class="fas fa-circle-question status-icon"></i> No parameters recognized';
        } else if (abnormalCount === 0) {
            resultArea.classList.add('status-clear');
            statusHeadline.innerHTML = `<i class="fas fa-circle-check status-icon"></i> All ${total} value(s) look normal`;
        } else {
            resultArea.classList.add('status-attention');
            statusHeadline.innerHTML = `<i class="fas fa-triangle-exclamation status-icon"></i> ${abnormalCount} of ${total} value(s) need attention`;
        }
    }

    // Builds one recognized-value row: name + status badge on top, the
    // actual figure below, and — the part that makes this more than a
    // re-statement of the report — a plain-language line explaining what
    // the test even measures, shown whether or not it's flagged.
    function buildValueRow(v) {
        const li = document.createElement('li');
        li.className = 'value-row';

        const top = document.createElement('div');
        top.className = 'value-row-top';

        const name = document.createElement('span');
        name.className = 'value-name';
        name.textContent = v.label;

        const badge = document.createElement('span');
        badge.className = `badge ${STATUS_BADGE_CLASS[v.status] || 'badge-neutral'}`;
        badge.textContent = STATUS_LABELS[v.status] || v.status;

        top.appendChild(name);
        top.appendChild(badge);
        li.appendChild(top);

        const figure = document.createElement('p');
        figure.className = 'value-figure';
        figure.innerHTML = `${v.value} ${v.unit} <span class="value-range">(typical: ${v.reference_low}-${v.reference_high} ${v.unit})</span>`;
        li.appendChild(figure);

        if (v.description) {
            const desc = document.createElement('p');
            desc.className = 'value-description';
            desc.textContent = v.description;
            li.appendChild(desc);
        }

        return li;
    }

    // Screening results have no numeric figure, just a name, status, and
    // description.
    function buildScreeningRow(q) {
        const li = document.createElement('li');
        li.className = 'value-row';

        const top = document.createElement('div');
        top.className = 'value-row-top';

        const name = document.createElement('span');
        name.className = 'value-name';
        name.textContent = q.label;

        const badge = document.createElement('span');
        badge.className = `badge ${STATUS_BADGE_CLASS[q.status] || 'badge-neutral'}`;
        badge.textContent = q.status === 'abnormal' ? 'Reactive/Positive' : 'Non-Reactive/Negative';

        top.appendChild(name);
        top.appendChild(badge);
        li.appendChild(top);

        if (q.description) {
            const desc = document.createElement('p');
            desc.className = 'value-description';
            desc.textContent = q.description;
            li.appendChild(desc);
        }

        return li;
    }

    function groupByCategory(values) {
        const groups = new Map();
        values.forEach((v) => {
            const key = v.category || 'other';
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(v);
        });
        const orderedKeys = [
            ...CATEGORY_ORDER.filter((k) => groups.has(k)),
            ...[...groups.keys()].filter((k) => !CATEGORY_ORDER.includes(k)),
        ];
        return orderedKeys.map((key) => ({ key, label: CATEGORY_LABELS[key] || key, items: groups.get(key) }));
    }

    function showResult(data) {
        processingArea.style.display = 'none';
        resultArea.style.display = 'block';

        buildStatusHeadline(data);
        summaryText.textContent = data.summary;
        disclaimerText.textContent = data.disclaimer;

        if (data.llm_explanation) {
            explanationSection.style.display = 'block';
            explanationText.textContent = data.llm_explanation;
        } else {
            explanationSection.style.display = 'none';
        }

        valuesList.innerHTML = '';
        if (data.values && data.values.length > 0) {
            valuesSection.style.display = 'block';
            groupByCategory(data.values).forEach((group) => {
                const groupEl = document.createElement('div');
                groupEl.className = 'value-group';

                const title = document.createElement('p');
                title.className = 'value-group-title';
                title.textContent = group.label;
                groupEl.appendChild(title);

                const ul = document.createElement('ul');
                ul.className = 'value-list';
                group.items.forEach((v) => ul.appendChild(buildValueRow(v)));
                groupEl.appendChild(ul);

                valuesList.appendChild(groupEl);
            });
        } else {
            valuesSection.style.display = 'none';
        }

        screeningList.innerHTML = '';
        if (data.qualitative_results && data.qualitative_results.length > 0) {
            screeningSection.style.display = 'block';
            data.qualitative_results.forEach((q) => screeningList.appendChild(buildScreeningRow(q)));
        } else {
            screeningSection.style.display = 'none';
        }

        questionsList.innerHTML = '';
        if (data.questions_to_ask && data.questions_to_ask.length > 0) {
            questionsSection.style.display = 'block';
            data.questions_to_ask.forEach((q) => {
                const li = document.createElement('li');
                li.textContent = q;
                questionsList.appendChild(li);
            });
        } else {
            questionsSection.style.display = 'none';
        }
    }

    function showError(msg) {
        errorText.textContent = msg;
        errorMsg.style.display = 'flex';
    }

    function hideError() {
        errorMsg.style.display = 'none';
    }
});
