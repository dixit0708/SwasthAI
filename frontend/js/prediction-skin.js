/**
 * SwasthAI - Skin Disease Detection UI Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    
    const processingArea = document.getElementById('processingArea');
    const resultArea = document.getElementById('resultArea');
    const errorMsg = document.getElementById('errorMsg');
    
    const previewImg = document.getElementById('previewImg');
    const resultLabel = document.getElementById('resultLabel');
    const resultConfidenceText = document.getElementById('resultConfidenceText');
    const resultBar = document.getElementById('resultBar');
    const resetBtn = document.getElementById('resetBtn');

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

    // Reset UI
    resetBtn.addEventListener('click', () => {
        resultArea.style.display = 'none';
        errorMsg.style.display = 'none';
        uploadArea.style.display = 'block';
        fileInput.value = ''; // clear selection
        resultArea.classList.remove('result-skin');
    });

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

        // Display preview
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
        };
        reader.readAsDataURL(file);

        // Upload and Predict
        uploadForPrediction(file);
    }

    async function uploadForPrediction(file) {
        // UI State: Processing
        uploadArea.style.display = 'none';
        processingArea.style.display = 'block';
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // SWASTHAI_API_BASE is globally available from auth.js
            const token = localStorage.getItem(SWASTHAI_TOKEN_KEY); 
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;
            
            const response = await fetch(`${SWASTHAI_API_BASE}/predict/skin`, {
                method: 'POST',
                headers: headers,
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || `Server error: ${response.status}`);
            }
            
            showResult(data);
            
        } catch (err) {
            console.error('Prediction failed:', err);
            processingArea.style.display = 'none';
            uploadArea.style.display = 'block';
            showError(err.message || 'An unexpected error occurred during prediction.');
        }
    }

    function showResult(data) {
        // expected: { label: "Acne and Rosacea Photos", confidence: 0.95 }
        processingArea.style.display = 'none';
        resultArea.style.display = 'block';
        resultArea.classList.add('result-skin');
        
        let label = data.label || "Unknown Condition";
        // Clean up the label format for display
        label = label.replace(/ Photos/ig, '')
                     .replace(/ and other.*$/ig, '')
                     .replace(/ /g, ' ')
                     .trim();
        
        const confPct = Math.round(data.confidence * 100);
        
        resultLabel.textContent = label;
        resultConfidenceText.textContent = `AI Confidence: ${confPct}%`;
        
        // Trigger animation for the bar
        setTimeout(() => {
            resultBar.style.width = `${confPct}%`;
        }, 100);
    }

    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.style.display = 'block';
    }
});
