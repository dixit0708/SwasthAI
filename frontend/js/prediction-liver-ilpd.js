/**
 * SwasthAI — Liver Disease Risk Screening (Lab-Based / ILPD) page.
 *
 * A bounded 2-section wizard (1 question section + review) collecting the
 * 10 fields the production liver-ilpd-logistic-v1 model expects
 * (backend/app/models/prediction.py: LiverIlpdPredictionInput), mapped to
 * the exact field names that endpoint requires. The backend is the sole
 * authority on risk classification: this file never computes a
 * probability, never applies its own threshold, and only ever renders the
 * risk_level/is_elevated/message/disclaimer the backend actually returned.
 *
 * INDEPENDENT of prediction-liver.js: a second, separate model trained on
 * the canonical UCI ILPD dataset. This is the "I have my lab report"
 * counterpart to the lab-free NHANES model — requires an actual Liver
 * Function Test (LFT) panel, not something answerable from memory.
 */

const STEPS = [
  { key: 'lab-results', title: 'Lab Results' },
  { key: 'review', title: 'Review' },
];
const TOTAL_STEPS = STEPS.length;

const FIELD_CONFIG = [
  { apiField: 'gender', step: 0, kind: 'radio', name: 'gender', questionId: 'q-liGender' },
  { apiField: 'age', step: 0, kind: 'input', elId: 'liAge', min: 1, max: 120, unit: '', isInt: true },
  { apiField: 'total_bilirubin', step: 0, kind: 'input', elId: 'liTotalBilirubin', min: 0.1, max: 100, unit: 'mg/dL', isFloat: true },
  { apiField: 'direct_bilirubin', step: 0, kind: 'input', elId: 'liDirectBilirubin', min: 0.05, max: 30, unit: 'mg/dL', isFloat: true },
  { apiField: 'alkaline_phosphatase', step: 0, kind: 'input', elId: 'liAlkPhos', min: 20, max: 3000, unit: 'U/L', isFloat: true },
  { apiField: 'alt_sgpt', step: 0, kind: 'input', elId: 'liAlt', min: 5, max: 3000, unit: 'U/L', isFloat: true },
  { apiField: 'ast_sgot', step: 0, kind: 'input', elId: 'liAst', min: 5, max: 6000, unit: 'U/L', isFloat: true },
  { apiField: 'total_proteins', step: 0, kind: 'input', elId: 'liTotalProteins', min: 2, max: 12, unit: 'g/dL', isFloat: true },
  { apiField: 'albumin', step: 0, kind: 'input', elId: 'liAlbumin', min: 0.5, max: 7, unit: 'g/dL', isFloat: true },
  { apiField: 'albumin_globulin_ratio', step: 0, kind: 'input', elId: 'liAgRatio', min: 0.1, max: 4, unit: '', isFloat: true },
];
// 10 entries above = the full LiverIlpdPredictionInput contract: age,
// gender, total_bilirubin, direct_bilirubin, alkaline_phosphatase,
// alt_sgpt, ast_sgot, total_proteins, albumin, albumin_globulin_ratio.

let currentStep = null; // null until the assessment actually starts
let isTransitioning = false;

function isFirstStep() {
  return currentStep === 0;
}

function isLastStep() {
  return currentStep === TOTAL_STEPS - 1;
}

function clampStep(next) {
  return Math.max(0, Math.min(TOTAL_STEPS - 1, next));
}

function liPrefersReducedMotion() {
  return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// ---------------------------------------------------------------------------
// Field access helpers
// ---------------------------------------------------------------------------

function getFieldValue(cfg) {
  if (cfg.kind === 'radio') {
    const checked = document.querySelector(`input[name="${cfg.name}"]:checked`);
    return checked ? checked.value : '';
  }
  return document.getElementById(cfg.elId).value;
}

function getFieldDisplayValue(cfg) {
  if (cfg.kind === 'radio') {
    const checked = document.querySelector(`input[name="${cfg.name}"]:checked`);
    if (!checked) return '';
    return checked.closest('label').textContent.trim();
  }
  const value = document.getElementById(cfg.elId).value;
  if (value === '') return '';
  return cfg.unit ? `${value} ${cfg.unit}` : value;
}

function getFieldQuestionText(cfg) {
  if (cfg.kind === 'radio') {
    return document.getElementById(cfg.questionId).textContent.trim();
  }
  return document.querySelector(`label[for="${cfg.elId}"]`).textContent.trim();
}

function getFieldErrorEl(cfg) {
  return document.getElementById(`${cfg.apiField}Error`);
}

function getFieldInvalidTarget(cfg) {
  if (cfg.kind === 'radio') return document.querySelector(`input[name="${cfg.name}"]`);
  return document.getElementById(cfg.elId);
}

function setFieldError(cfg, message) {
  const errorEl = getFieldErrorEl(cfg);
  errorEl.textContent = message;
  errorEl.hidden = false;
  if (cfg.kind === 'radio') {
    errorEl.closest('.db-field').classList.add('is-invalid');
  } else {
    document.getElementById(cfg.elId).classList.add('is-invalid');
  }
}

function clearFieldError(cfg) {
  const errorEl = getFieldErrorEl(cfg);
  errorEl.hidden = true;
  if (cfg.kind === 'radio') {
    errorEl.closest('.db-field').classList.remove('is-invalid');
  } else {
    document.getElementById(cfg.elId).classList.remove('is-invalid');
  }
}

function validateField(cfg) {
  if (cfg.kind === 'radio') {
    if (!document.querySelector(`input[name="${cfg.name}"]:checked`)) {
      setFieldError(cfg, 'Please answer this question to continue.');
      return false;
    }
    clearFieldError(cfg);
    return true;
  }

  // Numeric field: required, must be a finite number, no obviously
  // invalid negative lab values, within this field's clinical bounds.
  // An empty string is never silently treated as 0 — it is a validation
  // failure, same as any other missing value.
  const el = document.getElementById(cfg.elId);
  const raw = el.value.trim();
  if (raw === '') {
    setFieldError(cfg, 'Please enter a value to continue.');
    return false;
  }
  const num = Number(raw);
  if (!Number.isFinite(num)) {
    setFieldError(cfg, 'Please enter a valid number.');
    return false;
  }
  if (num < 0) {
    setFieldError(cfg, 'This value cannot be negative.');
    return false;
  }
  if (num < cfg.min || num > cfg.max) {
    setFieldError(cfg, `Enter a valid number between ${cfg.min} and ${cfg.max}.`);
    return false;
  }
  clearFieldError(cfg);
  return true;
}

function validateStep(step) {
  let valid = true;
  let firstInvalid = null;

  FIELD_CONFIG.filter((cfg) => cfg.step === step).forEach((cfg) => {
    if (!validateField(cfg)) {
      valid = false;
      if (!firstInvalid) firstInvalid = getFieldInvalidTarget(cfg);
    }
  });

  if (!valid && firstInvalid) {
    firstInvalid.focus({ preventScroll: false });
  }
  return valid;
}

// ---------------------------------------------------------------------------
// Wizard rendering — every render derives purely from `currentStep`.
// ---------------------------------------------------------------------------

function renderProgress() {
  const stepNumber = currentStep + 1;
  document.getElementById('dbProgressFill').style.transform = `scaleX(${stepNumber / TOTAL_STEPS})`;
  document.getElementById('dbProgressLabel').textContent =
    `Section ${stepNumber} of ${TOTAL_STEPS} · ${STEPS[currentStep].title}`;
}

function renderNavControls() {
  document.getElementById('dbBackBtn').hidden = isFirstStep();
  document.getElementById('dbNextBtn').hidden = isLastStep();
  document.getElementById('dbSubmitBtn').hidden = !isLastStep();
}

function focusStepHeading(step) {
  const heading = document.querySelector(`.db-step[data-step="${step}"] .db-step__legend`);
  if (!heading) return;
  heading.setAttribute('tabindex', '-1');
  heading.focus({ preventScroll: false });
}

function transitionSteps(fromStep, toStep) {
  const fromEl = document.querySelector(`.db-step[data-step="${fromStep}"]`);
  const toEl = document.querySelector(`.db-step[data-step="${toStep}"]`);
  if (fromEl === toEl) return;

  if (liPrefersReducedMotion()) {
    if (fromEl) fromEl.hidden = true;
    if (toEl) toEl.hidden = false;
    focusStepHeading(toStep);
    return;
  }

  isTransitioning = true;
  if (fromEl) fromEl.classList.add('db-step--leaving');
  window.setTimeout(() => {
    if (fromEl) {
      fromEl.hidden = true;
      fromEl.classList.remove('db-step--leaving');
    }
    if (toEl) {
      toEl.hidden = false;
      toEl.classList.add('db-step--entering');
      requestAnimationFrame(() => toEl.classList.remove('db-step--entering'));
    }
    focusStepHeading(toStep);
    isTransitioning = false;
  }, 180);
}

function goToStep(next) {
  if (isTransitioning) return;
  const clamped = clampStep(next);

  if (currentStep === null) {
    currentStep = clamped;
    renderProgress();
    renderNavControls();
    return;
  }

  if (clamped === currentStep) return;

  const previous = currentStep;
  currentStep = clamped;
  renderProgress();
  renderNavControls();
  transitionSteps(previous, clamped);
}

function goToNextStep() {
  if (isTransitioning || isLastStep()) return;
  if (!validateStep(currentStep)) return;
  if (currentStep === TOTAL_STEPS - 2) renderReview();
  goToStep(currentStep + 1);
}

function goToPreviousStep() {
  if (isTransitioning || isFirstStep()) return;
  goToStep(currentStep - 1);
}

// ---------------------------------------------------------------------------
// Review
// ---------------------------------------------------------------------------

function renderReview() {
  const list = document.getElementById('dbReviewList');
  list.innerHTML = '';

  for (let step = 0; step < TOTAL_STEPS - 1; step += 1) {
    const section = document.createElement('div');
    section.className = 'db-review__section';

    const head = document.createElement('div');
    head.className = 'db-review__head';
    const title = document.createElement('span');
    title.className = 'db-review__title';
    title.textContent = STEPS[step].title;
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'db-review__edit';
    editBtn.textContent = 'Edit';
    editBtn.setAttribute('aria-label', `Edit answers in ${STEPS[step].title}`);
    editBtn.addEventListener('click', () => goToStep(step));
    head.appendChild(title);
    head.appendChild(editBtn);
    section.appendChild(head);

    FIELD_CONFIG.filter((cfg) => cfg.step === step).forEach((cfg) => {
      section.appendChild(reviewRow(getFieldQuestionText(cfg), getFieldDisplayValue(cfg)));
    });

    list.appendChild(section);
  }
}

function reviewRow(question, answer) {
  const row = document.createElement('div');
  row.className = 'db-review__row';
  const q = document.createElement('span');
  q.className = 'db-review__q';
  q.textContent = question;
  const a = document.createElement('span');
  a.className = 'db-review__a';
  a.textContent = answer;
  row.appendChild(q);
  row.appendChild(a);
  return row;
}

// ---------------------------------------------------------------------------
// Submission
// ---------------------------------------------------------------------------

function mapFormToApiPayload() {
  const payload = {};
  FIELD_CONFIG.forEach((cfg) => {
    const raw = getFieldValue(cfg);
    if (cfg.kind === 'radio') {
      payload[cfg.apiField] = raw;
    } else {
      payload[cfg.apiField] = cfg.isInt ? Math.trunc(Number(raw)) : Number(raw);
    }
  });
  return payload;
}

function getAuthToken() {
  return typeof swasthaiGetToken === 'function' ? swasthaiGetToken() : null;
}

function showError(message, { retryable = false } = {}) {
  const alertBox = document.getElementById('liverIlpdFormAlert');
  const alertText = document.getElementById('liverIlpdFormAlertText');
  const retryBtn = document.getElementById('dbRetryBtn');
  alertText.textContent = message;
  retryBtn.hidden = !retryable;
  alertBox.hidden = false;
}

function clearFormAlert() {
  document.getElementById('liverIlpdFormAlert').hidden = true;
}

function messageForError(err) {
  if (err && err.status === 401) {
    return { message: 'Your session has expired. Please sign in again.', retryable: false };
  }
  if (err && err.status === 422) {
    return { message: 'Some of the information could not be validated. Please review your answers and try again.', retryable: false };
  }
  if (err && err.status === 503) {
    return { message: 'The liver risk model is not available right now. Please try again later.', retryable: true };
  }
  if (err && err.status >= 500) {
    return { message: "We couldn't complete your assessment right now. Please try again.", retryable: true };
  }
  if (err && err.message === 'Could not reach the SwasthAI server. Please try again.') {
    return { message: "We couldn't connect to SwasthAI. Please check your connection and try again.", retryable: true };
  }
  return { message: 'We received an unexpected response. Please try again.', retryable: true };
}

function isValidPredictionResponse(result) {
  return (
    result &&
    (result.risk_level === 'screening_negative' || result.risk_level === 'screening_elevated') &&
    typeof result.risk_probability === 'number' &&
    result.risk_probability >= 0 &&
    result.risk_probability <= 1 &&
    typeof result.is_elevated === 'boolean' &&
    typeof result.message === 'string' &&
    typeof result.disclaimer === 'string'
  );
}

const RESULT_MARK_NEGATIVE = `
  <svg viewBox="0 0 96 96" width="80" height="80" fill="none">
    <circle cx="48" cy="48" r="40" stroke="var(--border)" stroke-width="2"/>
    <circle class="db-result-ring" cx="48" cy="48" r="40" stroke="var(--success)" stroke-width="3" stroke-linecap="round" fill="none" transform="rotate(-90 48 48)"/>
    <path class="db-result-check" d="M32 49 L44 61 L66 37" stroke="var(--success)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </svg>`;

const RESULT_MARK_ELEVATED = `
  <svg viewBox="0 0 96 96" width="80" height="80" fill="none">
    <circle cx="48" cy="48" r="40" stroke="var(--border)" stroke-width="2"/>
    <circle class="db-result-ring" cx="48" cy="48" r="40" stroke="var(--warning)" stroke-width="3" stroke-linecap="round" fill="none" transform="rotate(-90 48 48)"/>
    <circle class="db-result-dot" cx="48" cy="48" r="6" fill="var(--warning)"/>
  </svg>`;

function renderScreeningResult(result) {
  const elevated = result.is_elevated;

  document.getElementById('dbResultMark').innerHTML = elevated ? RESULT_MARK_ELEVATED : RESULT_MARK_NEGATIVE;

  const titleEl = document.getElementById('resultRiskLevel');
  titleEl.textContent = elevated ? 'Elevated Estimated Risk' : 'No Elevated Risk Identified';
  titleEl.className = `db-result__title ${elevated ? 'db-result__title--elevated' : 'db-result__title--negative'}`;

  const percentage = Math.round(result.risk_probability * 100);
  document.getElementById('resultProbability').textContent = `Estimated screening risk score: ${percentage}%`;
  document.getElementById('resultMessage').textContent = result.message;
  document.getElementById('resultDisclaimer').textContent = result.disclaimer;

  document.getElementById('dbAssessment').hidden = true;
  document.getElementById('dbResultPanel').hidden = false;
  document.getElementById('dbResultPanel').scrollIntoView({ behavior: liPrefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
}

function setLoadingState(isLoading) {
  const submitBtn = document.getElementById('dbSubmitBtn');
  const backBtn = document.getElementById('dbBackBtn');
  submitBtn.disabled = isLoading;
  backBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? 'Analyzing your results...' : 'Assess My Risk';
}

async function submitPrediction(payload) {
  return SwasthAPI.predictions.liverIlpd(payload);
}

let lastPayload = null;
let isSubmitting = false;

async function handleSubmit(event) {
  event.preventDefault();
  if (isTransitioning || isSubmitting) return;
  clearFormAlert();

  if (!getAuthToken()) {
    showError('Your session has expired. Please sign in again.');
    return;
  }

  for (let step = 0; step < TOTAL_STEPS - 1; step += 1) {
    if (!validateStep(step)) {
      showError('Some of your answers need to be corrected before this can be submitted.');
      goToStep(step);
      return;
    }
  }

  isSubmitting = true;
  setLoadingState(true);
  try {
    lastPayload = mapFormToApiPayload();
    const result = await submitPrediction(lastPayload);
    if (!isValidPredictionResponse(result)) {
      const { message, retryable } = messageForError(null);
      showError(message, { retryable });
      return;
    }
    renderScreeningResult(result);
  } catch (err) {
    const { message, retryable } = messageForError(err);
    showError(message, { retryable });
  } finally {
    setLoadingState(false);
    isSubmitting = false;
  }
}

async function retrySubmission() {
  if (!lastPayload || isSubmitting) return;
  clearFormAlert();
  isSubmitting = true;
  setLoadingState(true);
  try {
    const result = await submitPrediction(lastPayload);
    if (!isValidPredictionResponse(result)) {
      const { message, retryable } = messageForError(null);
      showError(message, { retryable });
      return;
    }
    renderScreeningResult(result);
  } catch (err) {
    const { message, retryable } = messageForError(err);
    showError(message, { retryable });
  } finally {
    setLoadingState(false);
    isSubmitting = false;
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('liverIlpdForm');
  if (!form) return;

  document.getElementById('dbBeginBtn').addEventListener('click', () => {
    document.getElementById('dbWelcome').hidden = true;
    document.getElementById('dbAssessment').hidden = false;
    goToStep(0);
  });

  document.getElementById('dbNextBtn').addEventListener('click', goToNextStep);
  document.getElementById('dbBackBtn').addEventListener('click', goToPreviousStep);
  document.getElementById('dbRetryBtn').addEventListener('click', retrySubmission);

  document.getElementById('dbReviewAgainBtn').addEventListener('click', () => {
    document.getElementById('dbResultPanel').hidden = true;
    document.getElementById('dbAssessment').hidden = false;
    renderReview();
    goToStep(TOTAL_STEPS - 1);
  });

  form.addEventListener('submit', handleSubmit);
});
