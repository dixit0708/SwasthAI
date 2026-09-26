/**
 * prediction-heart.js
 * Heart Disease Risk Screening — form controller + API integration
 *
 * Flow: welcome -> multi-step assessment form -> SwasthAPI.predictions.heart()
 *       -> POST /api/v1/predict/heart (with JWT) -> result panel
 *
 * All 24 API keys must exactly match HeartPredictionInput in
 * backend/app/models/prediction.py. The payload uses snake_case keys.
 * The Bearer token is attached automatically by SwasthAPI (auth.js).
 */

'use strict';

/* ─── Step metadata ──────────────────────────────────────────────────────── */
const STEPS = [
    { label: 'About You',                total: 5 },
    { label: 'Recent Health',            total: 5 },
    { label: 'Medical History',          total: 5 },
    { label: 'Lifestyle & Activities',   total: 5 },
    { label: 'Other Factors',            total: 5 },
];
const TOTAL_STEPS = STEPS.length;

/* ─── State ──────────────────────────────────────────────────────────────── */
let currentStep = 0;
let isClinical = false;

/* ─── Element references ─────────────────────────────────────────────────── */
const page          = document.getElementById('hdPage');
const welcomePanel  = document.getElementById('hdWelcome');
const assessPanel   = document.getElementById('hdAssessment');
const resultPanel   = document.getElementById('hdResultPanel');

const beginBtn      = document.getElementById('hdBeginBtn');
const backToWelcome = document.getElementById('hdBackToWelcome');
const backBtn       = document.getElementById('hdBackBtn');
const nextBtn       = document.getElementById('hdNextBtn');
const submitBtn     = document.getElementById('hdSubmitBtn');
const retryBtn      = document.getElementById('hdRetryBtn');
const reassessBtn   = document.getElementById('hdReassessBtn');

const form          = document.getElementById('heartForm');
const progressLabel = document.getElementById('hdProgressLabel');
const progressFill  = document.getElementById('hdProgressFill');
const formAlert     = document.getElementById('hdFormAlert');
const formAlertText = document.getElementById('hdFormAlertText');

const heightInput   = document.getElementById('hdHeight');
const weightInput   = document.getElementById('hdWeight');
const bmiDisplay    = document.getElementById('hdBmiValue');

const clinHeightInput = document.getElementById('clinHeight');
const clinWeightInput = document.getElementById('clinWeight');
const clinBmiDisplay  = document.getElementById('clinBmiValue');

/* ─── Startup: enforce known-good initial state ───────────────────────────
   The HTML sets hidden on steps 1–4 and on the alert, but any CSS rule with
   a display: value can silently override the native [hidden] → display:none.
   Setting .hidden = true here is an extra safety net that runs after all
   stylesheets are parsed, guaranteeing the DOM is correct before any user
   interaction. The CSS also has a .hd-alert[hidden] { display:none !important }
   guard, so both layers agree. ─────────────────────────────────────────── */
formAlert.hidden = true;
retryBtn.hidden  = true;
// Ensure only step 0 is visible on first render
document.querySelectorAll('.hd-step').forEach((el, i) => { el.hidden = (i !== 0); });

/* ─── Phase helpers ──────────────────────────────────────────────────────── */
function showPanel(panel) {
    [welcomePanel, assessPanel, resultPanel].forEach(p => {
        p.hidden = (p !== panel);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ─── BMI live calculator ────────────────────────────────────────────────── */
function recalcBmi() {
    const h = parseFloat(heightInput.value);
    const w = parseFloat(weightInput.value);
    if (h > 0 && w > 0) {
        const bmi = w / ((h / 100) ** 2);
        bmiDisplay.textContent = bmi.toFixed(1);
        bmiDisplay.dataset.value = bmi.toFixed(2);
    } else {
        bmiDisplay.textContent = '—';
        delete bmiDisplay.dataset.value;
    }
}
heightInput.addEventListener('input', recalcBmi);
weightInput.addEventListener('input', recalcBmi);

function recalcClinBmi() {
    const h = parseFloat(clinHeightInput.value);
    const w = parseFloat(clinWeightInput.value);
    if (h > 0 && w > 0) {
        const bmi = w / ((h / 100) ** 2);
        clinBmiDisplay.textContent = bmi.toFixed(1);
        clinBmiDisplay.dataset.value = bmi.toFixed(2);
    } else {
        clinBmiDisplay.textContent = '—';
        delete clinBmiDisplay.dataset.value;
    }
}
if (clinHeightInput && clinWeightInput) {
    clinHeightInput.addEventListener('input', recalcClinBmi);
    clinWeightInput.addEventListener('input', recalcClinBmi);
}

/* ─── Progress bar ───────────────────────────────────────────────────────── */
function updateProgress(step) {
    // Clamp to valid range so STEPS[step] never throws even if called with an
    // out-of-bounds index (e.g. TOTAL_STEPS when the last step submits).
    const safeStep = Math.max(0, Math.min(step, TOTAL_STEPS - 1));
    const pct = Math.round(((safeStep + 1) / TOTAL_STEPS) * 100);
    progressFill.style.width = pct + '%';
    progressLabel.textContent =
        `Section ${safeStep + 1} of ${TOTAL_STEPS} · ${STEPS[safeStep].label}`;
}

/* ─── Step visibility ────────────────────────────────────────────────────── */
function showStep(index) {
    // Guard: ignore any index outside [0, TOTAL_STEPS - 1].
    // The submit button path should call submitAssessment() directly, not
    // showStep(TOTAL_STEPS), so this is purely a safety net.
    if (index < 0 || index >= TOTAL_STEPS) {
        console.warn(`[showStep] index ${index} is out of bounds (0–${TOTAL_STEPS - 1}); ignoring.`);
        return;
    }

    document.querySelectorAll('.hd-step').forEach((el, i) => {
        el.hidden = (i !== index);
    });
    currentStep = index;
    updateProgress(index);

    backBtn.hidden   = (index === 0);
    nextBtn.hidden   = (index === TOTAL_STEPS - 1);
    submitBtn.hidden = (index !== TOTAL_STEPS - 1);

    hideAlert();
}

/* ─── Alert helpers ──────────────────────────────────────────────────────── */
function showAlert(msg, withRetry = false) {
    formAlertText.textContent = msg;
    formAlert.hidden = false;
    retryBtn.hidden  = !withRetry;
    formAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function hideAlert() {
    formAlert.hidden = true;
    retryBtn.hidden  = true;
}

/* ─── Field-level error helpers ──────────────────────────────────────────── */
function fieldError(id, msg) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.hidden = !msg;
}
function clearFieldErrors() {
    document.querySelectorAll('.hd-field-error').forEach(el => {
        el.hidden = true;
        el.textContent = '';
    });
}

/* ─── Per-step validation ────────────────────────────────────────────────── */
function validateStep(index) {
    clearFieldErrors();
    let valid = true;

    function requireRadio(name, errorId) {
        const checked = form.querySelector(`input[name="${name}"]:checked`);
        if (!checked) {
            fieldError(errorId, 'Please select an option.');
            valid = false;
        }
    }
    function requireSelect(id, errorId) {
        const el = document.getElementById(id);
        if (!el || !el.value) {
            fieldError(errorId, 'Please select an option.');
            valid = false;
        }
    }
    function requireNumber(id, errorId, min, max, label) {
        const el = document.getElementById(id);
        const val = parseFloat(el?.value);
        if (isNaN(val) || val < min || val > max) {
            fieldError(errorId, `Please enter a valid ${label} (${min}–${max}).`);
            valid = false;
        }
    }

    if (index === 0) {
        requireRadio('sex', 'sexError');
        requireSelect('hdAgeCategory', 'ageCategoryError');
        // BMI
        const h = parseFloat(heightInput.value);
        const w = parseFloat(weightInput.value);
        if (isNaN(h) || h < 50 || h > 250 || isNaN(w) || w < 10 || w > 300) {
            fieldError('bmiError', 'Please enter valid height (50–250 cm) and weight (10–300 kg).');
            valid = false;
        } else if (!bmiDisplay.dataset.value) {
            fieldError('bmiError', 'BMI could not be calculated — check your height and weight.');
            valid = false;
        }
        requireNumber('hdSleepHours', 'sleepHoursError', 1, 24, 'sleep hours');
    }
    if (index === 1) {
        requireNumber('hdPhysicalHealthDays', 'physicalHealthDaysError', 0, 30, 'number of days');
        requireNumber('hdMentalHealthDays', 'mentalHealthDaysError', 0, 30, 'number of days');
        requireSelect('hdLastCheckup', 'lastCheckupError');
    }
    if (index === 2) {
        requireRadio('had_stroke',              'hadStrokeError');
        requireRadio('had_asthma',              'hadAsthmaError');
        requireRadio('had_copd',                'hadCopdError');
        requireRadio('had_depressive_disorder', 'hadDepressiveDisorderError');
        requireRadio('had_kidney_disease',      'hadKidneyDiseaseError');
        requireRadio('had_arthritis',           'hadArthritisError');
        requireSelect('hdDiabetes',             'hadDiabetesError');
    }
    if (index === 3) {
        requireRadio('physical_activities',     'physicalActivitiesError');
        requireSelect('hdSmokerStatus',         'smokerStatusError');
        requireRadio('alcohol_drinkers',        'alcoholDrinkersError');
        requireRadio('difficulty_walking',      'difficultyWalkingError');
        requireRadio('difficulty_concentrating','difficultyConcentratingError');
        requireRadio('difficulty_errands',      'difficultyErrandsError');
    }
    if (index === 4) {
        requireRadio('chest_scan',          'chestScanError');
        requireRadio('high_risk_last_year', 'highRiskLastYearError');
        requireSelect('hdRemovedTeeth',     'removedTeethError');
    }

    if (!valid) {
        // Scroll to first visible error
        const firstErr = document.querySelector('.hd-field-error:not([hidden])');
        if (firstErr) firstErr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    return valid;
}

/* ─── Collect payload ────────────────────────────────────────────────────── */
function buildPayload() {
    if (isClinical) {
        return {
            age: parseFloat(document.getElementById('clinAge').value),
            systolic_bp: parseFloat(document.getElementById('clinSysBp').value),
            diastolic_bp: parseFloat(document.getElementById('clinDiaBp').value),
            total_cholesterol: parseFloat(document.getElementById('clinTotChol').value),
            hdl_cholesterol: parseFloat(document.getElementById('clinHdl').value),
            fasting_glucose: parseFloat(document.getElementById('clinGlu').value),
            pulse: parseFloat(document.getElementById('clinPulse').value),
            bmi: parseFloat(clinBmiDisplay.dataset.value)
        };
    }

    const radio = name => form.querySelector(`input[name="${name}"]:checked`)?.value;
    const sel   = id   => document.getElementById(id)?.value;

    return {
        sex:                      radio('sex'),
        age_category:             sel('hdAgeCategory'),
        bmi:                      parseFloat(bmiDisplay.dataset.value),
        physical_health_days:     parseFloat(document.getElementById('hdPhysicalHealthDays').value),
        mental_health_days:       parseFloat(document.getElementById('hdMentalHealthDays').value),
        sleep_hours:              parseFloat(document.getElementById('hdSleepHours').value),
        physical_activities:      radio('physical_activities'),
        had_stroke:               radio('had_stroke'),
        had_asthma:               radio('had_asthma'),
        had_copd:                 radio('had_copd'),
        had_depressive_disorder:  radio('had_depressive_disorder'),
        had_kidney_disease:       radio('had_kidney_disease'),
        had_arthritis:            radio('had_arthritis'),
        had_diabetes:             sel('hdDiabetes'),
        difficulty_walking:       radio('difficulty_walking'),
        difficulty_concentrating: radio('difficulty_concentrating'),
        difficulty_errands:       radio('difficulty_errands'),
        smoker_status:            sel('hdSmokerStatus'),
        alcohol_drinkers:         radio('alcohol_drinkers'),
        chest_scan:               radio('chest_scan'),
        high_risk_last_year:      radio('high_risk_last_year'),
        removed_teeth:            sel('hdRemovedTeeth'),
        last_checkup_time:        sel('hdLastCheckup'),
    };
}

/* ─── Result rendering ───────────────────────────────────────────────────── */
function renderResult(data) {
    const { risk_probability, risk_level, message, disclaimer } = data;
    const pct = Math.round(risk_probability * 100);
    const isElevated = risk_level === 'screening_elevated';

    // Title & mark
    const titleEl = document.getElementById('hdResultTitle');
    const markEl  = document.getElementById('hdResultMark');
    titleEl.textContent = isElevated ? 'Elevated Risk Indicated' : 'No Elevated Risk Indicated';
    titleEl.className = 'hd-result__title ' + (isElevated ? 'hd-result__title--elevated' : 'hd-result__title--clear');
    markEl.innerHTML = isElevated
        ? '<i class="fas fa-triangle-exclamation" aria-hidden="true"></i>'
        : '<i class="fas fa-circle-check" aria-hidden="true"></i>';
    markEl.className = 'hd-result__mark ' + (isElevated ? 'hd-result__mark--elevated' : 'hd-result__mark--clear');

    // Gauge arc animation
    // Arc total length ≈ 157px (half-circle path), 0% = offset 157, 100% = offset 0
    const gaugeArc = document.getElementById('hdGaugeArc');
    const gaugePct = document.getElementById('hdGaugePct');
    if (gaugeArc) {
        const arcLen = 157;
        const offset = arcLen - (pct / 100) * arcLen;
        gaugeArc.style.strokeDashoffset = offset;
        gaugeArc.style.stroke = isElevated ? 'var(--error)' : 'var(--success)';
    }
    // Animated counter
    if (gaugePct) {
        let counter = 0;
        const target = pct;
        const step   = Math.max(1, Math.floor(target / 40));
        const timer  = setInterval(() => {
            counter = Math.min(counter + step, target);
            gaugePct.textContent = counter + '%';
            if (counter >= target) clearInterval(timer);
        }, 25);
    }

    document.getElementById('hdResultProbability').textContent =
        `Risk score: ${(risk_probability * 100).toFixed(1)}%`;
    document.getElementById('hdResultMessage').textContent    = message;
    document.getElementById('hdResultDisclaimer').textContent = disclaimer;

    showPanel(resultPanel);
}

/* ─── API call ───────────────────────────────────────────────────────────── */
async function submitAssessment() {
    const payload = buildPayload();

    // Disable submit while in-flight
    submitBtn.disabled = true;
    submitBtn.textContent = 'Calculating…';
    hideAlert();

    try {
        // SwasthAPI.predictions.heart() (auth.js) attaches the Bearer token
        // automatically and calls swasthaiLogout() on 401.
        let data;
        if (isClinical) {
            data = await SwasthAPI.predictions.heartClinical(payload);
        } else {
            data = await SwasthAPI.predictions.heart(payload);
        }
        renderResult(data);

    } catch (err) {
        const isNetwork = err instanceof TypeError;
        let message;
        if (err.status === 401) {
            // Session expired — swasthaiAuthedRequest already called logout()
            message = 'Your session has expired. Please log in again.';
        } else if (err.status === 503) {
            message = 'The heart risk model is temporarily unavailable. Please try again in a moment.';
        } else if (isNetwork) {
            message = 'Could not reach the server. Please check that the backend is running and try again.';
        } else {
            message = err.message || 'An unexpected error occurred. Please try again.';
        }
        showAlert(message, /* withRetry */ err.status !== 401);
        console.error('[heart prediction]', err);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Assess My Risk';
    }
}

/* ─── Event listeners ────────────────────────────────────────────────────── */
document.querySelectorAll('input[name="pathway"]').forEach(el => {
    el.addEventListener('change', (e) => {
        document.getElementById('gatewayScreen').style.display = 'none';
        isClinical = (e.target.value === 'clinical');
        if (isClinical) {
            document.querySelectorAll('.hd-step').forEach(s => s.hidden = true);
            document.getElementById('clinicalTrack').style.display = 'block';
            document.getElementById('hdProgress').hidden = true;
            backBtn.hidden = true;
            nextBtn.hidden = true;
            submitBtn.hidden = false;
            hideAlert();
        } else {
            document.getElementById('clinicalTrack').style.display = 'none';
            document.getElementById('hdProgress').hidden = false;
            showStep(0);
        }
    });
});

beginBtn.addEventListener('click', () => {
    showPanel(assessPanel);
    
    // Gateway screen initialization
    document.getElementById('gatewayScreen').style.display = 'block';
    document.getElementById('clinicalTrack').style.display = 'none';
    document.querySelectorAll('.hd-step').forEach(s => s.hidden = true);
    
    document.getElementById('hdProgress').hidden = true;
    backBtn.hidden = true;
    nextBtn.hidden = true;
    submitBtn.hidden = true;
    
    // Clear selection
    document.querySelectorAll('input[name="pathway"]').forEach(el => el.checked = false);
});

backToWelcome.addEventListener('click', () => {
    showPanel(welcomePanel);
});

nextBtn.addEventListener('click', () => {
    if (!validateStep(currentStep)) return;
    showStep(currentStep + 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

backBtn.addEventListener('click', () => {
    showStep(currentStep - 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

function validateClinical() {
    clearFieldErrors();
    let valid = true;
    function requireNumber(id, errorId, min, max, label) {
        const el = document.getElementById(id);
        const val = parseFloat(el?.value);
        if (isNaN(val) || val < min || val > max) {
            fieldError(errorId, `Please enter a valid ${label} (${min}–${max}).`);
            valid = false;
        }
    }
    requireNumber('clinAge', 'clinAgeError', 18, 120, 'age');
    requireNumber('clinSysBp', 'clinSysBpError', 60, 250, 'systolic BP');
    requireNumber('clinDiaBp', 'clinDiaBpError', 30, 150, 'diastolic BP');
    requireNumber('clinTotChol', 'clinTotCholError', 50, 600, 'total cholesterol');
    requireNumber('clinHdl', 'clinHdlError', 10, 200, 'HDL cholesterol');
    requireNumber('clinGlu', 'clinGluError', 40, 500, 'fasting glucose');
    requireNumber('clinPulse', 'clinPulseError', 30, 200, 'pulse');
    const h = parseFloat(clinHeightInput?.value);
    const w = parseFloat(clinWeightInput?.value);
    if (isNaN(h) || h < 50 || h > 250 || isNaN(w) || w < 10 || w > 300) {
        fieldError('clinBmiError', 'Please enter valid height (50–250 cm) and weight (10–300 kg).');
        valid = false;
    } else if (!clinBmiDisplay?.dataset.value) {
        fieldError('clinBmiError', 'BMI could not be calculated — check your height and weight.');
        valid = false;
    }
    if (!valid) {
        const firstErr = document.querySelector('.hd-field-error:not([hidden])');
        if (firstErr) firstErr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    return valid;
}

// Submit button: direct click listener — no reliance on form submit event.
// The button is type="button" in the HTML so the browser never triggers its
// own form submission machinery; this click handler is the only path.
submitBtn.addEventListener('click', async () => {
    if (isClinical) {
        if (!validateClinical()) return;
    } else {
        if (!validateStep(currentStep)) return;
    }
    console.log('[heart] Assess My Risk clicked — sending payload');
    await submitAssessment();
});

// Prevent any accidental native form submit (e.g. Enter key in a text input).
form.addEventListener('submit', (e) => {
    e.preventDefault();
});

retryBtn.addEventListener('click', async () => {
    await submitAssessment();
});

reassessBtn.addEventListener('click', () => {
    form.reset();
    bmiDisplay.textContent = '—';
    delete bmiDisplay.dataset.value;
    clearFieldErrors();
    hideAlert();
    isClinical = false;
    
    showPanel(assessPanel);
    
    // Gateway screen initialization
    document.getElementById('gatewayScreen').style.display = 'block';
    document.getElementById('clinicalTrack').style.display = 'none';
    document.querySelectorAll('.hd-step').forEach(s => s.hidden = true);
    
    document.getElementById('hdProgress').hidden = true;
    backBtn.hidden = true;
    nextBtn.hidden = true;
    submitBtn.hidden = true;
    
    // Clear selection
    document.querySelectorAll('input[name="pathway"]').forEach(el => el.checked = false);
});