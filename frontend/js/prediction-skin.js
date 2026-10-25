/**
 * SwasthAI - Skin Disease Detection UI Logic
 * Automated Multi-Scale Lesion Analysis, Grad-CAM Saliency, & Top-3 Differential Assessment.
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');

    const processingArea = document.getElementById('processingArea');
    const resultArea = document.getElementById('resultArea');
    const errorMsg = document.getElementById('errorMsg');
    
    const previewImg = document.getElementById('previewImg');
    const resultLabel = document.getElementById('resultLabel');
    const malignantCalmNote = document.getElementById('malignantCalmNote');
    const confidenceLevelBadge = document.getElementById('confidenceLevelBadge');
    const rawScoreText = document.getElementById('rawScoreText');
    const uncertainResultAlert = document.getElementById('uncertainResultAlert');

    const differentialSection = document.getElementById('differentialSection');
    const differentialList = document.getElementById('differentialList');
    const toggleDifferentialBtn = document.getElementById('toggleDifferentialBtn');
    const toggleDifferentialText = document.getElementById('toggleDifferentialText');
    const toggleDifferentialIcon = document.getElementById('toggleDifferentialIcon');
    const differentialContent = document.getElementById('differentialContent');
    const clinicalCorrelationNote = document.getElementById('clinicalCorrelationNote');
    const resetBtn = document.getElementById('resetBtn');

    const camControlArea = document.getElementById('camControlArea');
    const showOriginalBtn = document.getElementById('showOriginalBtn');
    const showHeatmapBtn = document.getElementById('showHeatmapBtn');

    const familyProfileSelect = document.getElementById('familyProfileSelect');
    const saveRecordBtn = document.getElementById('saveRecordBtn');
    const saveRecordStatus = document.getElementById('saveRecordStatus');

    let currentFile = null;
    let originalDataUrl = null;
    let currentHeatmapUrl = null;
    let currentOriginalUrl = null;
    let isDifferentialOpen = false;
    let currentResultData = null;

    // --- Clean Label Mapping ---
    const CLINICAL_LABEL_MAP = {
        'Acne and Rosacea Photos': 'Acne and Rosacea',
        'Actinic Keratosis Basal Cell Carcinoma and other Malignant Lesions': 'Actinic Keratosis & Malignant Lesions',
        'Atopic Dermatitis Photos': 'Atopic Dermatitis (Eczema)',
        'Bullous Disease Photos': 'Bullous (Blistering) Disease',
        'Cellulitis Impetigo and other Bacterial Infections': 'Cellulitis, Impetigo & Bacterial Infections',
        'Eczema Photos': 'Eczema & Dermatitis',
        'Exanthems and Drug Eruptions': 'Allergic Skin Eruptions & Exanthems (Hives-like Rash)',
        'Hair Loss Photos Alopecia and other Hair Diseases': 'Alopecia & Hair Disorders',
        'Herpes HPV and other STDs Photos': 'Herpes, HPV & Viral Lesions',
        'Light Diseases and Disorders of Pigmentation': 'Pigmentation & Photodermatoses',
        'Lupus and other Connective Tissue diseases': 'Lupus & Connective Tissue Diseases',
        'Melanoma Skin Cancer Nevi and Moles': 'Melanoma, Nevi & Moles',
        'Nail Fungus and other Nail Disease': 'Onychomycosis & Nail Diseases',
        'Poison Ivy Photos and other Contact Dermatitis': 'Contact Dermatitis & Poison Ivy',
        'Psoriasis pictures Lichen Planus and related diseases': 'Psoriasis & Lichen Planus',
        'Scabies Lyme Disease and other Infestations and Bites': 'Scabies, Bites & Infestations',
        'Seborrheic Keratoses and other Benign Tumors': 'Seborrheic Keratoses & Benign Tumors',
        'Systemic Disease': 'Systemic Disease Manifestations',
        'Tinea Ringworm Candidiasis and other Fungal Infections': 'Tinea, Ringworm & Fungal Infections',
        'Urticaria Hives': 'Urticaria (Hives & Wheals)',
        'Vascular Tumors': 'Vascular Tumors & Hemangiomas',
        'Vasculitis Photos': 'Vasculitis',
        'Warts Molluscum and other Viral Infections': 'Warts, Molluscum & Viral Infections'
    };

    function formatClinicalLabel(rawLabel) {
        if (!rawLabel) return 'Unknown Condition';
        if (CLINICAL_LABEL_MAP[rawLabel]) return CLINICAL_LABEL_MAP[rawLabel];
        return rawLabel
            .replace(/ Photos/ig, '')
            .replace(/ pictures /ig, ' & ')
            .replace(/ and other.*$/ig, '')
            .trim();
    }

    function isMalignantOrCancerCategory(rawLabel) {
        if (!rawLabel) return false;
        if (typeof getSkinClinicalInsight === 'function') {
            const ins = getSkinClinicalInsight(rawLabel);
            if (ins && ins.isMalignantCategory) return true;
        }
        return /malignant|melanoma|cancer|carcinoma|actinic keratosis/i.test(rawLabel);
    }

    // --- Collapsible Differential Toggle ---
    if (toggleDifferentialBtn) {
        toggleDifferentialBtn.addEventListener('click', () => {
            isDifferentialOpen = !isDifferentialOpen;
            if (isDifferentialOpen) {
                if (differentialContent) differentialContent.style.display = 'block';
                if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(180deg)';
            } else {
                if (differentialContent) differentialContent.style.display = 'none';
                if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(0deg)';
            }
        });
    }

    // --- Load Family Profiles for Save Option ---
    async function loadFamilyProfiles() {
        if (!familyProfileSelect) return;
        const token = localStorage.getItem(typeof SWASTHAI_TOKEN_KEY !== 'undefined' ? SWASTHAI_TOKEN_KEY : 'swasthai_token');
        if (!token) return;

        const apiBase = typeof SWASTHAI_API_BASE !== 'undefined' ? SWASTHAI_API_BASE : 'http://127.0.0.1:8000/api/v1';
        try {
            const response = await fetch(`${apiBase}/predict/family-profiles`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) return;
            const data = await response.json();
            const profiles = data.profiles || [];
            if (profiles.length > 0) {
                familyProfileSelect.innerHTML = '';
                profiles.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.name + (p.relationship && p.relationship !== 'Self' ? ` (${p.relationship})` : ' (Personal Profile)');
                    familyProfileSelect.appendChild(opt);
                });
            }
        } catch (err) {
            console.warn('Could not load family profiles for skin record save:', err);
        }
    }

    // Call early if logged in
    loadFamilyProfiles();

    // --- File Selection Handlers ---

    // Click to browse
    browseBtn.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('click', (e) => {
        if (e.target !== browseBtn) fileInput.click();
    });
    
    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    ['dragleave', 'dragend'].forEach(type => {
        uploadArea.addEventListener(type, () => {
            uploadArea.classList.remove('drag-over');
        });
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    // Grad-CAM Heatmap Toggle Listeners
    if (showOriginalBtn && showHeatmapBtn) {
        showOriginalBtn.addEventListener('click', () => {
            if (currentOriginalUrl) {
                previewImg.src = currentOriginalUrl;
                showOriginalBtn.className = 'btn btn-sm btn-primary';
                showHeatmapBtn.className = 'btn btn-sm btn-outline';
            }
        });
        showHeatmapBtn.addEventListener('click', () => {
            if (currentHeatmapUrl) {
                previewImg.src = currentHeatmapUrl;
                showHeatmapBtn.className = 'btn btn-sm btn-primary';
                showOriginalBtn.className = 'btn btn-sm btn-outline';
            }
        });
    }

    // Reset UI
    resetBtn.addEventListener('click', () => {
        resultArea.style.display = 'none';
        processingArea.style.display = 'none';
        errorMsg.style.display = 'none';
        uploadArea.style.display = 'block';
        fileInput.value = '';
        currentFile = null;
        originalDataUrl = null;
        currentHeatmapUrl = null;
        currentOriginalUrl = null;
        currentResultData = null;
        if (camControlArea) camControlArea.style.display = 'none';
        if (malignantCalmNote) malignantCalmNote.style.display = 'none';
        if (uncertainResultAlert) uncertainResultAlert.style.display = 'none';
        if (clinicalCorrelationNote) clinicalCorrelationNote.style.display = 'none';
        if (saveRecordStatus) {
            saveRecordStatus.style.display = 'none';
            saveRecordStatus.textContent = '';
        }
        if (saveRecordBtn) {
            saveRecordBtn.disabled = false;
            saveRecordBtn.innerHTML = '<i class="fas fa-bookmark text-primary"></i> <span>Save to Health Record</span>';
        }
        isDifferentialOpen = false;
        if (differentialContent) differentialContent.style.display = 'none';
        if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(0deg)';
        if (differentialSection) differentialSection.style.display = 'none';
        if (differentialList) differentialList.innerHTML = '';
    });

    // --- Save to Health Record Handler ---
    if (saveRecordBtn) {
        saveRecordBtn.addEventListener('click', async () => {
            if (!currentResultData) return;
            const token = localStorage.getItem(typeof SWASTHAI_TOKEN_KEY !== 'undefined' ? SWASTHAI_TOKEN_KEY : 'swasthai_token');
            if (!token) {
                if (saveRecordStatus) {
                    saveRecordStatus.innerHTML = '<span class="text-warning"><i class="fas fa-exclamation-circle"></i> Please <a href="login.html" style="text-decoration: underline; color: inherit; font-weight: 600;">log in</a> to save assessments to your health record.</span>';
                    saveRecordStatus.style.display = 'block';
                }
                return;
            }

            saveRecordBtn.disabled = true;
            saveRecordBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';
            if (saveRecordStatus) saveRecordStatus.style.display = 'none';

            const selectedProfileId = familyProfileSelect ? familyProfileSelect.value : 'self';
            const selectedProfileName = (familyProfileSelect && familyProfileSelect.options[familyProfileSelect.selectedIndex])
                ? familyProfileSelect.options[familyProfileSelect.selectedIndex].text
                : 'Self';

            const payload = {
                label: currentResultData.primaryRaw,
                clinical_label: currentResultData.primaryLabel,
                confidence_level: currentResultData.confLevel,
                confidence: currentResultData.primaryConfidence,
                top_3: (currentResultData.differential || []).slice(0, 3).map(d => ({
                    label: d.label,
                    clinical_label: formatClinicalLabel(d.label),
                    confidence: d.confidence != null ? d.confidence : (d.percentage != null ? d.percentage / 100 : 0),
                    percentage: d.percentage != null ? d.percentage : Math.round((d.confidence || 0) * 100)
                })),
                family_member_id: (selectedProfileId && selectedProfileId !== 'self') ? selectedProfileId : null,
                family_member_name: selectedProfileName
            };

            const apiBase = typeof SWASTHAI_API_BASE !== 'undefined' ? SWASTHAI_API_BASE : 'http://127.0.0.1:8000/api/v1';
            try {
                const res = await fetch(`${apiBase}/predict/skin/save`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                });
                const resData = await res.json();
                if (!res.ok) {
                    throw new Error(resData.detail || 'Failed to save record');
                }
                saveRecordBtn.innerHTML = '<i class="fas fa-check text-success"></i> <span>Saved</span>';
                if (saveRecordStatus) {
                    saveRecordStatus.innerHTML = '<span class="text-success"><i class="fas fa-check-circle"></i> Assessment saved to health record. View anytime in Digital Records.</span>';
                    saveRecordStatus.style.display = 'block';
                }
            } catch (err) {
                console.error('Error saving record:', err);
                saveRecordBtn.disabled = false;
                saveRecordBtn.innerHTML = '<i class="fas fa-bookmark text-primary"></i> <span>Save to Health Record</span>';
                if (saveRecordStatus) {
                    saveRecordStatus.innerHTML = `<span class="text-danger"><i class="fas fa-exclamation-circle"></i> ${err.message || 'Error saving to records'}</span>`;
                    saveRecordStatus.style.display = 'block';
                }
            }
        });
    }

    // --- Main Logic (Fully Automated) ---

    function handleFile(file) {
        // Clear previous errors
        errorMsg.style.display = 'none';
        
        // Validate file on frontend
        const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
        if (!validTypes.includes(file.type)) {
            showError("Invalid file type. Please upload a JPEG or PNG image.");
            return;
        }
        
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            showError("File is too large. Maximum size is 10MB.");
            return;
        }

        currentFile = file;

        // Read file into image preview
        const reader = new FileReader();
        reader.onload = (e) => {
            originalDataUrl = e.target.result;
            previewImg.src = originalDataUrl;
        };
        reader.readAsDataURL(file);

        // Instantly run automated multi-scale prediction
        uploadForPrediction(file);
    }

    async function uploadForPrediction(file) {
        // UI State: Automated Processing
        uploadArea.style.display = 'none';
        resultArea.style.display = 'none';
        processingArea.style.display = 'block';
        errorMsg.style.display = 'none';
        
        const formData = new FormData();
        const filename = file.name || 'skin_image.jpg';
        formData.append('file', file, filename);
        
        try {
            const token = localStorage.getItem(typeof SWASTHAI_TOKEN_KEY !== 'undefined' ? SWASTHAI_TOKEN_KEY : 'swasthai_token'); 
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;
            
            const apiBase = typeof SWASTHAI_API_BASE !== 'undefined' ? SWASTHAI_API_BASE : 'http://127.0.0.1:8000/api/v1';
            const response = await fetch(`${apiBase}/predict/skin`, {
                method: 'POST',
                headers: headers,
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || `Server error: ${response.status}`);
            }
            
            showResult(data, originalDataUrl);
            
        } catch (err) {
            console.error('Prediction failed:', err);
            processingArea.style.display = 'none';
            uploadArea.style.display = 'block';
            showError(err.message || 'An unexpected error occurred during prediction.');
        }
    }

    function showResult(data, displayDataUrl) {
        processingArea.style.display = 'none';
        resultArea.style.display = 'block';
        resultArea.classList.add('result-skin');
        
        currentOriginalUrl = displayDataUrl || originalDataUrl;
        currentHeatmapUrl = data.heatmap_overlay || null;

        if (currentOriginalUrl) {
            previewImg.src = currentOriginalUrl;
        }

        if (camControlArea) {
            if (currentHeatmapUrl) {
                camControlArea.style.display = 'block';
                if (showOriginalBtn) showOriginalBtn.className = 'btn btn-sm btn-primary';
                if (showHeatmapBtn) showHeatmapBtn.className = 'btn btn-sm btn-outline';
            } else {
                camControlArea.style.display = 'none';
            }
        }

        const primaryRaw = data.label || "Unknown Condition";
        const primaryLabel = formatClinicalLabel(primaryRaw);
        const primaryConfidence = typeof data.confidence === 'number' ? data.confidence : 0;
        const primaryPct = Math.round(primaryConfidence * 100);
        const differential = data.differential_diagnosis || [];

        // 1. Result Label: Pattern similarity representation (never diagnosis)
        if (resultLabel) {
            resultLabel.textContent = primaryLabel;
        }

        // 2. Extra calm note for categories containing malignant or cancer terms
        if (malignantCalmNote) {
            if (isMalignantOrCancerCategory(primaryRaw)) {
                malignantCalmNote.style.display = 'block';
            } else {
                malignantCalmNote.style.display = 'none';
            }
        }

        // 3. Confidence Level categorization (High >= 70%, Medium 40-70%, Low < 40%)
        let confLevel = "Medium";
        let badgeClass = "conf-badge conf-medium";
        let badgeIcon = "fa-circle-half-stroke";
        let badgeText = "Medium similarity";

        if (primaryPct >= 70) {
            confLevel = "High";
            badgeClass = "conf-badge conf-high";
            badgeIcon = "fa-circle-check";
            badgeText = "High similarity";
        } else if (primaryPct < 40) {
            confLevel = "Low";
            badgeClass = "conf-badge conf-low";
            badgeIcon = "fa-circle-exclamation";
            badgeText = "Low similarity";
        }

        if (confidenceLevelBadge) {
            confidenceLevelBadge.className = badgeClass;
            confidenceLevelBadge.innerHTML = `<i class="fas ${badgeIcon}"></i> ${badgeText}`;
        }

        if (rawScoreText) {
            rawScoreText.textContent = `(${primaryPct}% model similarity score)`;
        }

        // Uncertain result notice if confidence is Low
        if (uncertainResultAlert) {
            uncertainResultAlert.style.display = (primaryPct < 40) ? 'block' : 'none';
        }

        // 4. Clinical Insight Box: Category-specific educational overview (from skin-clinical-insights.js)
        if (clinicalCorrelationNote) {
            const insight = (typeof getSkinClinicalInsight === 'function')
                ? getSkinClinicalInsight(primaryRaw)
                : null;

            if (insight) {
                clinicalCorrelationNote.innerHTML = `
                    <div style="padding: 0.95rem 1.15rem; background: var(--bg-surface-alt); border: 1px solid var(--border); border-left: 4px solid var(--primary); border-radius: var(--radius-sm); font-size: 0.85rem; color: var(--text-secondary); line-height: 1.55;">
                        <strong style="color: var(--text); display: flex; align-items: center; gap: 0.45rem; margin-bottom: 0.5rem; font-size: 0.92rem;">
                            <i class="fas fa-stethoscope text-primary"></i> Category Overview: ${insight.title}
                        </strong>
                        <div style="margin-bottom: 0.5rem;">
                            <strong style="color: var(--text);">What this pattern represents:</strong>
                            <p style="margin: 0.2rem 0 0; color: var(--text-secondary);">${insight.whatItIs}</p>
                        </div>
                        <div>
                            <strong style="color: var(--text);">When to consult a healthcare provider:</strong>
                            <p style="margin: 0.2rem 0 0; color: var(--text-secondary);">${insight.whenToSeeDoctor}</p>
                        </div>
                    </div>
                `;
                clinicalCorrelationNote.style.display = 'block';
            } else {
                clinicalCorrelationNote.style.display = 'none';
            }
        }

        // 5. Differential Possibilities: ALWAYS show Top 3 (all candidates, no cutoff)
        const secondaryPossibilities = differential.slice(1);

        if (differentialSection) {
            if (secondaryPossibilities.length > 0) {
                differentialSection.style.display = 'block';
                isDifferentialOpen = false;
                if (differentialContent) differentialContent.style.display = 'none';
                if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(0deg)';
                
                if (toggleDifferentialText) {
                    toggleDifferentialText.textContent = `View other possibilities considered by AI (${secondaryPossibilities.length})`;
                }

                if (differentialList) {
                    differentialList.innerHTML = '';
                    secondaryPossibilities.forEach((item, index) => {
                        const rank = index + 2; // #2, #3
                        const cleanName = formatClinicalLabel(item.label);
                        const pct = item.percentage != null ? Math.round(item.percentage) : Math.round((item.confidence || 0) * 100);

                        const card = document.createElement('div');
                        card.className = 'diff-item';
                        card.style.cssText = 'padding: 0.75rem 1rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm);';
                        card.innerHTML = `
                            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.88rem;">
                                <div>
                                    <span style="font-weight: 700; color: var(--primary); margin-right: 0.5rem;">#${rank}</span>
                                    <span style="font-weight: 500; color: var(--text);">${cleanName}</span>
                                </div>
                                <span style="font-size: 0.82rem; color: var(--text-secondary);">${pct}% similarity</span>
                            </div>
                        `;
                        differentialList.appendChild(card);
                    });
                }
            } else {
                differentialSection.style.display = 'none';
            }
        }

        // Store active result state for Health Record persistence
        currentResultData = {
            primaryRaw,
            primaryLabel,
            confLevel,
            primaryConfidence,
            primaryPct,
            differential
        };

        // Reset save button state
        if (saveRecordBtn) {
            saveRecordBtn.disabled = false;
            saveRecordBtn.innerHTML = '<i class="fas fa-bookmark text-primary"></i> <span>Save to Health Record</span>';
        }
        if (saveRecordStatus) {
            saveRecordStatus.style.display = 'none';
            saveRecordStatus.textContent = '';
        }
    }

    function showError(msg) {
        if (!errorMsg) return;

        let iconHtml = '<i class="fas fa-exclamation-circle text-danger" style="font-size: 1.25rem;"></i>';
        let actionHtml = '';
        let titleHtml = '<strong style="color: var(--text); font-size: 0.98rem;">Assessment Notice</strong>';

        const lower = (msg || '').toLowerCase();
        if (lower.includes('animal') || lower.includes('non-human')) {
            iconHtml = '<i class="fas fa-paw text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Animal / Non-Human Subject Detected</strong>';
        } else if (lower.includes('clothing') || lower.includes('apparel')) {
            iconHtml = '<i class="fas fa-tshirt text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Clothing / Apparel Detected</strong>';
        } else if (lower.includes('distant portrait') || lower.includes('full-body') || lower.includes('portrait')) {
            iconHtml = '<i class="fas fa-user text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Full-Body / Distant Portrait Detected</strong>';
        } else if (lower.includes('distinct dermatological condition') || lower.includes('clear clinical disease')) {
            iconHtml = '<i class="fas fa-shield-alt text-info" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">No Clinical Lesion Detected</strong>';
        } else if (lower.includes('everyday object') || lower.includes('object detected')) {
            iconHtml = '<i class="fas fa-cube text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Everyday Object Detected</strong>';
        } else if (lower.includes('radiographic') || lower.includes('x-ray') || lower.includes('pneumonia')) {
            iconHtml = '<i class="fas fa-x-ray text-primary" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Radiographic Scan / X-Ray Detected</strong>';
            actionHtml = `
                <div style="margin-top: 0.85rem;">
                    <a href="prediction-pneumonia.html" class="btn btn-sm btn-primary" style="display: inline-flex; align-items: center; gap: 0.45rem; text-decoration: none; padding: 0.45rem 0.9rem; font-size: 0.85rem;">
                        <i class="fas fa-lungs"></i> Open Chest X-Ray Assessment
                    </a>
                </div>
            `;
        } else if (lower.includes('document') || lower.includes('prescription') || lower.includes('handwriting')) {
            iconHtml = '<i class="fas fa-file-medical text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Document or Paper Detected</strong>';
        } else if (lower.includes('dark') || lower.includes('empty')) {
            iconHtml = '<i class="fas fa-moon text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Insufficient Lighting</strong>';
        } else if (lower.includes('overexposed')) {
            iconHtml = '<i class="fas fa-sun text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">Image Overexposed</strong>';
        } else if (lower.includes('no human skin') || lower.includes('skin patterns')) {
            iconHtml = '<i class="fas fa-user-slash text-warning" style="font-size: 1.35rem;"></i>';
            titleHtml = '<strong style="color: var(--text); font-size: 1rem;">No Human Skin Detected</strong>';
        }

        errorMsg.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 0.85rem;">
                <div style="padding-top: 0.15rem;">${iconHtml}</div>
                <div style="flex: 1;">
                    <div>${titleHtml}</div>
                    <div style="margin-top: 0.3rem; font-size: 0.88rem; color: var(--text-secondary); line-height: 1.55;">${msg}</div>
                    ${actionHtml}
                </div>
            </div>
        `;
        errorMsg.style.display = 'block';
    }
});
