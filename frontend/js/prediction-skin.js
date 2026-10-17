/**
 * SwasthAI - Skin Disease Detection UI Logic
 * Includes Cropper.js lesion isolation and Top-3 Differential Diagnosis rendering.
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    
    const cropArea = document.getElementById('cropArea');
    const cropImage = document.getElementById('cropImage');
    const analyzeCropBtn = document.getElementById('analyzeCropBtn');
    const cancelCropBtn = document.getElementById('cancelCropBtn');
    const skipCropBtn = document.getElementById('skipCropBtn');

    const processingArea = document.getElementById('processingArea');
    const resultArea = document.getElementById('resultArea');
    const errorMsg = document.getElementById('errorMsg');
    
    const previewImg = document.getElementById('previewImg');
    const resultLabel = document.getElementById('resultLabel');
    const resultConfidenceText = document.getElementById('resultConfidenceText');
    const resultBar = document.getElementById('resultBar');
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

    let cropper = null;
    let currentFile = null;
    let originalDataUrl = null;
    let currentHeatmapUrl = null;
    let currentOriginalUrl = null;
    let isDifferentialOpen = false;

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

    // --- Comprehensive Clinical Family Cross-Reference ---
    function getClinicalFamilyInsight(primaryRaw, differential) {
        const allLabels = [primaryRaw, ...(differential || []).map(d => d.label)];
        const has = (cls) => allLabels.includes(cls);

        if (has('Tinea Ringworm Candidiasis and other Fungal Infections') && has('Light Diseases and Disorders of Pigmentation')) {
            return {
                title: 'Clinical Insight: Hypopigmentation (Vitiligo vs. Pityriasis Versicolor)',
                text: 'Chalky-white depigmented macules or patches (leukoderma) are classic shared clinical hallmarks between <strong>Vitiligo (Disorders of Pigmentation)</strong> and <strong>Pityriasis (Tinea) Versicolor</strong>. Fungal pityriasis versicolor causes superficial melanocyte inhibition via azelaic acid, whereas vitiligo involves autoimmune pigment depletion. Dermatologists standardly use a <em>Wood’s lamp</em> or KOH preparation to distinguish between the two.'
            };
        }

        if (has('Urticaria Hives') || has('Exanthems and Drug Eruptions')) {
            return {
                title: 'Clinical Insight: Acute Allergic & Urticarial Reactions',
                text: 'In clinical dermatology, <strong>Urticaria (Hives)</strong> and <strong>Allergic Exanthems</strong> represent acute cutaneous hypersensitivity reactions. Wide-area body images often match generalized allergic eruptions, while close-up raised wheals match classic urticaria.'
            };
        }
        if (has('Eczema Photos') || has('Atopic Dermatitis Photos') || has('Poison Ivy Photos and other Contact Dermatitis')) {
            return {
                title: 'Clinical Insight: Eczematous Dermatitis Spectrum',
                text: '<strong>Atopic Dermatitis</strong>, <strong>Contact Dermatitis</strong>, and <strong>Eczema</strong> represent closely related inflammatory skin conditions sharing epidermal barrier compromise, scaling, and pruritus. Clinical distinction depends on contact triggers and chronicity.'
            };
        }
        if (has('Tinea Ringworm Candidiasis and other Fungal Infections') || has('Nail Fungus and other Nail Disease')) {
            return {
                title: 'Clinical Insight: Superficial Fungal & Nail Dermatophytosis',
                text: 'Fungal dermatophytes (such as <em>Trichophyton</em>) manifest as circular annular ringworm (tinea) on smooth skin or as onychomycosis in the nail plate. Both respond to targeted antimycotic management.'
            };
        }
        if (has('Actinic Keratosis Basal Cell Carcinoma and other Malignant Lesions') || has('Melanoma Skin Cancer Nevi and Moles') || has('Seborrheic Keratoses and other Benign Tumors')) {
            return {
                title: 'Clinical Insight: Pigmented & Keratinocytic Lesions',
                text: 'Differentiating benign seborrheic keratoses and melanocytic nevi from premalignant actinic keratosis or carcinoma requires formal dermatoscopic ABCDE evaluation. Annual full-body checks by a dermatologist are strongly advised.'
            };
        }
        if (has('Warts Molluscum and other Viral Infections') || has('Herpes HPV and other STDs Photos')) {
            return {
                title: 'Clinical Insight: Viral Epidermal Lesions',
                text: 'Viral skin conditions (including human papillomavirus warts, molluscum contagiosum, and herpesviridae) produce characteristic verrucous or vesicular lesions with distinct focal morphology.'
            };
        }
        if (has('Acne and Rosacea Photos')) {
            return {
                title: 'Clinical Insight: Pilosebaceous & Rosacea Conditions',
                text: 'Characterized by follicular inflammation, comedones, or facial telangiectasia. The AI evaluates both inflammatory papules/pustules and macroscopic facial vascular patterns.'
            };
        }
        if (has('Hair Loss Photos Alopecia and other Hair Diseases')) {
            return {
                title: 'Clinical Insight: Alopecia & Scalp Disorders',
                text: 'Encompasses autoimmune focal alopecia areata, androgenetic thinning, and inflammatory scalp dermatoses. Scalp trichoscopy helps confirm follicular viability.'
            };
        }
        if (has('Vasculitis Photos') || has('Systemic Disease') || has('Lupus and other Connective Tissue diseases')) {
            return {
                title: 'Clinical Insight: Autoimmune & Systemic Vascular Reactions',
                text: 'Cutaneous vascular erythema, purpura, or malar patterns can be clinical indicators of underlying systemic or connective tissue immunity.'
            };
        }
        return null;
    }

    // --- Collapsible Differential Toggle ---
    if (toggleDifferentialBtn) {
        toggleDifferentialBtn.addEventListener('click', () => {
            isDifferentialOpen = !isDifferentialOpen;
            if (isDifferentialOpen) {
                if (differentialContent) differentialContent.style.display = 'block';
                if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(180deg)';
                // Trigger mini-bar animations
                setTimeout(() => {
                    const fills = differentialList.querySelectorAll('.result-confidence-bar-fill');
                    fills.forEach(fill => {
                        const target = fill.getAttribute('data-pct');
                        fill.style.width = `${target}%`;
                    });
                }, 50);
            } else {
                if (differentialContent) differentialContent.style.display = 'none';
                if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(0deg)';
            }
        });
    }

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

    // --- Crop Actions ---

    analyzeCropBtn.addEventListener('click', () => {
        if (!cropper) {
            if (currentFile) uploadForPrediction(currentFile, originalDataUrl);
            return;
        }

        const canvas = cropper.getCroppedCanvas({
            maxWidth: 1024,
            maxHeight: 1024,
            fillColor: '#ffffff',
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high'
        });

        if (!canvas) {
            showError("Unable to extract cropped area. Please try again.");
            return;
        }

        const croppedDataUrl = canvas.toDataURL('image/jpeg', 0.95);
        canvas.toBlob((blob) => {
            if (!blob) {
                showError("Failed to process cropped image.");
                return;
            }
            uploadForPrediction(blob, croppedDataUrl);
        }, 'image/jpeg', 0.95);
    });

    skipCropBtn.addEventListener('click', () => {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        if (currentFile) {
            uploadForPrediction(currentFile, originalDataUrl);
        }
    });

    cancelCropBtn.addEventListener('click', () => {
        destroyCropper();
        cropArea.style.display = 'none';
        uploadArea.style.display = 'block';
        errorMsg.style.display = 'none';
        fileInput.value = '';
        currentFile = null;
        originalDataUrl = null;
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
        destroyCropper();
        resultArea.style.display = 'none';
        cropArea.style.display = 'none';
        processingArea.style.display = 'none';
        errorMsg.style.display = 'none';
        uploadArea.style.display = 'block';
        fileInput.value = '';
        currentFile = null;
        originalDataUrl = null;
        currentHeatmapUrl = null;
        currentOriginalUrl = null;
        if (camControlArea) camControlArea.style.display = 'none';
        resultBar.style.width = '0%';
        if (clinicalCorrelationNote) clinicalCorrelationNote.style.display = 'none';
        isDifferentialOpen = false;
        if (differentialContent) differentialContent.style.display = 'none';
        if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(0deg)';
        if (differentialSection) differentialSection.style.display = 'none';
        if (differentialList) differentialList.innerHTML = '';
    });

    function destroyCropper() {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
    }

    // --- Main Logic ---

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

        // Read file into image for cropping
        const reader = new FileReader();
        reader.onload = (e) => {
            originalDataUrl = e.target.result;
            initCropper(originalDataUrl);
        };
        reader.readAsDataURL(file);
    }

    function initCropper(imageSrc) {
        uploadArea.style.display = 'none';
        processingArea.style.display = 'none';
        resultArea.style.display = 'none';
        cropArea.style.display = 'block';

        destroyCropper();

        cropImage.src = imageSrc;

        // Initialize Cropper.js after the image loads
        cropImage.onload = () => {
            cropper = new Cropper(cropImage, {
                viewMode: 1,
                dragMode: 'move',
                autoCropArea: 0.65,
                restore: false,
                guides: true,
                center: true,
                highlight: true,
                cropBoxMovable: true,
                cropBoxResizable: true,
                toggleDragModeOnDblclick: false,
                responsive: true
            });
        };
    }

    async function uploadForPrediction(imageBlobOrFile, displayDataUrl) {
        // UI State: Processing
        cropArea.style.display = 'none';
        uploadArea.style.display = 'none';
        processingArea.style.display = 'block';
        errorMsg.style.display = 'none';
        
        const formData = new FormData();
        const filename = imageBlobOrFile.name || 'cropped_lesion.jpg';
        formData.append('file', imageBlobOrFile, filename);
        
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
            
            showResult(data, displayDataUrl || originalDataUrl);
            
        } catch (err) {
            console.error('Prediction failed:', err);
            processingArea.style.display = 'none';
            
            const lower = (err.message || '').toLowerCase();
            const isOod = lower.includes('radiographic') || lower.includes('x-ray') || 
                          lower.includes('document') || lower.includes('dark') || 
                          lower.includes('overexposed') || lower.includes('no human skin') || 
                          lower.includes('skin patterns') || lower.includes('animal') ||
                          lower.includes('non-human') || lower.includes('object') ||
                          lower.includes('clothing') || lower.includes('apparel') ||
                          lower.includes('portrait') || lower.includes('distinct dermatological condition') ||
                          lower.includes('clear clinical disease');
            if (isOod) {
                destroyCropper();
                cropArea.style.display = 'none';
                uploadArea.style.display = 'block';
            } else {
                cropArea.style.display = 'block';
            }
            showError(err.message || 'An unexpected error occurred during prediction.');
        }
    }

    function showResult(data, displayDataUrl) {
        processingArea.style.display = 'none';
        cropArea.style.display = 'none';
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
        const primaryPct = Math.round((data.confidence || 0) * 100);
        
        resultLabel.textContent = primaryLabel;
        resultConfidenceText.textContent = `Primary Assessment Confidence: ${primaryPct}%`;
        
        // Trigger primary confidence bar animation
        setTimeout(() => {
            resultBar.style.width = `${primaryPct}%`;
        }, 100);

        // Dynamic Clinical Family Insight Note
        const differential = data.differential_diagnosis || [];
        if (clinicalCorrelationNote) {
            const familyInsight = getClinicalFamilyInsight(primaryRaw, differential);
            if (familyInsight) {
                clinicalCorrelationNote.innerHTML = `
                    <div style="padding: 0.85rem 1rem; background: color-mix(in srgb, var(--primary) 10%, transparent); border-left: 3px solid var(--primary); border-radius: var(--radius-sm); font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;">
                        <strong style="color: var(--text); display: block; margin-bottom: 0.25rem;"><i class="fas fa-stethoscope text-primary"></i> ${familyInsight.title}</strong>
                        ${familyInsight.text}
                    </div>
                `;
                clinicalCorrelationNote.style.display = 'block';
            } else {
                clinicalCorrelationNote.style.display = 'none';
            }
        }

        // Filter and Render Secondary Possibilities (Only show items >= 5% probability)
        const secondaryPossibilities = differential.slice(1).filter(item => {
            const pct = item.percentage != null ? item.percentage : (item.confidence || 0) * 100;
            return Math.round(pct) >= 5;
        });

        if (differentialSection) {
            if (secondaryPossibilities.length > 0) {
                differentialSection.style.display = 'block';
                isDifferentialOpen = false;
                if (differentialContent) differentialContent.style.display = 'none';
                if (toggleDifferentialIcon) toggleDifferentialIcon.style.transform = 'rotate(0deg)';
                
                if (toggleDifferentialText) {
                    toggleDifferentialText.textContent = `View ${secondaryPossibilities.length} other ${secondaryPossibilities.length === 1 ? 'possibility' : 'possibilities'} considered by AI`;
                }

                if (differentialList) {
                    differentialList.innerHTML = '';
                    secondaryPossibilities.forEach((item, index) => {
                        const rank = index + 2; // #2, #3
                        const cleanName = formatClinicalLabel(item.label);
                        const pct = item.percentage != null ? Math.round(item.percentage) : Math.round((item.confidence || 0) * 100);

                        const card = document.createElement('div');
                        card.className = 'diff-item';
                        card.innerHTML = `
                            <div class="diff-header">
                                <div>
                                    <span class="diff-rank">#${rank}</span>
                                    <span style="font-weight: 500;">${cleanName}</span>
                                </div>
                                <span class="diff-pct">${pct}%</span>
                            </div>
                            <div class="result-confidence-bar" style="margin: 0.25rem 0 0; height: 6px; background: var(--border);">
                                <div class="result-confidence-bar-fill" style="width: 0%;" data-pct="${pct}"></div>
                            </div>
                        `;
                        differentialList.appendChild(card);
                    });
                }
            } else {
                // If primary confidence is decisive and no secondary item reaches 5%, keep UI completely clean
                differentialSection.style.display = 'none';
            }
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
