/**
 * SwasthAI — Diabetes Risk Screening page.
 *
 * A bounded 4-section wizard (3 question sections + review) collecting the
 * 14 features the production BRFSS-v2 model expects
 * (backend/app/models/prediction.py: DiabetesPredictionInput), mapped to
 * the exact snake_case field names that endpoint requires. The backend is
 * the sole authority on risk classification: this file never computes a
 * probability, never applies its own threshold, and only ever renders the
 * risk_level/is_elevated/message/disclaimer the backend actually returned.
 *
 * v2 note: the prior v1 model used 21 features across 5 question sections
 * (About You, Health History, Lifestyle, Wellbeing, Access & Background).
 * The evidence-based feature study (ml_pipeline/diabetes/reports/
 * candidate_assessments.md, model_comparison.md) found the 14-feature
 * "Expanded" set performs comparably (ROC-AUC 0.8180 vs 0.8199) while
 * dropping every sensitive/access question (income, education, healthcare
 * coverage, cost-barrier) and the two day-count recall questions. Removing
 * those emptied the "Wellbeing" section down to a single question
 * (general health) and emptied "Access & Background" entirely, so per the
 * redesign brief both sections were removed rather than kept as
 * near-empty/artificial steps — general health now lives in "About You".
 *
 * Wizard state machine: `currentStep` is always clamped to
 * [0, STEPS.length - 1] by the single gatekeeper `goToStep()` — there is no
 * other place that mutates it. isFirstStep()/isLastStep() derive the
 * Back/Next/Submit visibility every time state changes, so a stray click
 * can never push the wizard past its last section.
 */

const STEPS = [
  { key: 'about-you', title: 'About You' },
  { key: 'health-history', title: 'Health History' },
  { key: 'lifestyle', title: 'Lifestyle' },
  { key: 'review', title: 'Review' },
];
const TOTAL_STEPS = STEPS.length;

// Every field the API requires except bmi (derived from height/weight,
// handled separately since it has no single control of its own).
const FIELD_CONFIG = [
  { apiField: 'sex', step: 0, kind: 'radio', name: 'sex', questionId: 'q-sex' },
  { apiField: 'age', step: 0, kind: 'select', elId: 'dbAgeGroup' },
  { apiField: 'gen_hlth', step: 0, kind: 'select', elId: 'dbGenHlth' },
  { apiField: 'high_bp', step: 1, kind: 'radio', name: 'high_bp', questionId: 'q-high-bp' },
  { apiField: 'high_chol', step: 1, kind: 'radio', name: 'high_chol', questionId: 'q-high-chol' },
  { apiField: 'chol_check', step: 1, kind: 'radio', name: 'chol_check', questionId: 'q-chol-check' },
  { apiField: 'stroke', step: 1, kind: 'radio', name: 'stroke', questionId: 'q-stroke' },
  { apiField: 'heart_disease_or_attack', step: 1, kind: 'radio', name: 'heart_disease_or_attack', questionId: 'q-heart' },
  { apiField: 'diff_walk', step: 1, kind: 'radio', name: 'diff_walk', questionId: 'q-diff-walk' },
  { apiField: 'smoker', step: 2, kind: 'radio', name: 'smoker', questionId: 'q-smoker' },
  { apiField: 'phys_activity', step: 2, kind: 'radio', name: 'phys_activity', questionId: 'q-phys-activity' },
  { apiField: 'fruits', step: 2, kind: 'radio', name: 'fruits', questionId: 'q-fruits' },
  { apiField: 'hvy_alcohol_consump', step: 2, kind: 'radio', name: 'hvy_alcohol_consump', questionId: 'q-alcohol' },
];
// 13 entries above + bmi (derived from height/weight, no entry of its own)
// = the full 14-feature contract: sex, age, bmi, gen_hlth, high_bp,
// high_chol, chol_check, stroke, heart_disease_or_attack, diff_walk,
// smoker, phys_activity, fruits, hvy_alcohol_consump.

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

function dbPrefersReducedMotion() {
  return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function computeBmi(heightCm, weightKg) {
  const heightM = heightCm / 100;
  return Math.round((weightKg / (heightM * heightM)) * 10) / 10;
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
  if (cfg.kind === 'select') {
    const select = document.getElementById(cfg.elId);
    const option = select.options[select.selectedIndex];
    return option && option.value !== '' ? option.textContent.trim() : '';
  }
  const value = document.getElementById(cfg.elId).value;
  return value === '' ? '' : `${value} ${cfg.unit}`;
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
  // The element/group to visually mark invalid and to focus.
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

  if (cfg.kind === 'select') {
    const el = document.getElementById(cfg.elId);
    if (el.value === '') {
      setFieldError(cfg, 'Please select an option to continue.');
      return false;
    }
    clearFieldError(cfg);
    return true;
  }

  // number
  const el = document.getElementById(cfg.elId);
  const raw = el.value.trim();
  if (raw === '') {
    setFieldError(cfg, 'Please enter a value to continue.');
    return false;
  }
  const num = Number(raw);
  if (!Number.isInteger(num) || num < cfg.min || num > cfg.max) {
    setFieldError(cfg, `Enter a whole number between ${cfg.min} and ${cfg.max}.`);
    return false;
  }
  clearFieldError(cfg);
  return true;
}

function validateBmiInputs() {
  const heightEl = document.getElementById('dbHeight');
  const weightEl = document.getElementById('dbWeight');
  const heightError = document.getElementById('heightError');
  const weightError = document.getElementById('weightError');
  const bmiError = document.getElementById('bmiError');
  let valid = true;

  const heightVal = Number(heightEl.value);
  if (heightEl.value.trim() === '' || !Number.isFinite(heightVal) || heightVal < 50 || heightVal > 250) {
    heightEl.classList.add('is-invalid');
    heightError.textContent = 'Please enter a valid height (50-250 cm).';
    heightError.hidden = false;
    valid = false;
  } else {
    heightEl.classList.remove('is-invalid');
    heightError.hidden = true;
  }

  const weightVal = Number(weightEl.value);
  if (weightEl.value.trim() === '' || !Number.isFinite(weightVal) || weightVal < 10 || weightVal > 300) {
    weightEl.classList.add('is-invalid');
    weightError.textContent = 'Please enter a valid weight (10-300 kg).';
    weightError.hidden = false;
    valid = false;
  } else {
    weightEl.classList.remove('is-invalid');
    weightError.hidden = true;
  }

  if (!valid) {
    bmiError.hidden = true;
    return false;
  }

  const bmi = computeBmi(heightVal, weightVal);
  if (!Number.isFinite(bmi) || bmi < 10 || bmi > 100) {
    bmiError.textContent = 'Please check your height and weight — the resulting BMI is outside the range this assessment supports.';
    bmiError.hidden = false;
    return false;
  }
  bmiError.hidden = true;
  return true;
}

function updateBmiPreview() {
  const heightVal = Number(document.getElementById('dbHeight').value);
  const weightVal = Number(document.getElementById('dbWeight').value);
  const valueEl = document.getElementById('dbBmiValue');
  const next = (Number.isFinite(heightVal) && heightVal > 0 && Number.isFinite(weightVal) && weightVal > 0)
    ? String(computeBmi(heightVal, weightVal))
    : '—';
  if (valueEl.textContent === next) return;
  valueEl.style.opacity = '0';
  window.setTimeout(() => {
    valueEl.textContent = next;
    valueEl.style.opacity = '1';
  }, dbPrefersReducedMotion() ? 0 : 120);
}

function validateStep(step) {
  let valid = true;
  let firstInvalid = null;

  if (step === 0 && !validateBmiInputs()) {
    valid = false;
    firstInvalid = document.getElementById('dbHeight');
  }

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

  if (dbPrefersReducedMotion()) {
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

/** The single gatekeeper for wizard navigation — every step change goes
 * through here, and `next` is always clamped, so currentStep can never
 * leave [0, TOTAL_STEPS - 1] regardless of how many times this is called. */
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
  if (isTransitioning || isLastStep()) return; // defensive: last step has no Next
  if (!validateStep(currentStep)) return;
  if (currentStep === TOTAL_STEPS - 2) renderReview(); // entering the review step next
  goToStep(currentStep + 1);
}

function goToPreviousStep() {
  if (isTransitioning || isFirstStep()) return; // defensive: first step has no Back
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

    if (step === 0) {
      const heightVal = document.getElementById('dbHeight').value;
      const weightVal = document.getElementById('dbWeight').value;
      section.appendChild(reviewRow('Height', `${heightVal} cm`));
      section.appendChild(reviewRow('Weight', `${weightVal} kg`));
      section.appendChild(reviewRow('BMI', String(computeBmi(Number(heightVal), Number(weightVal)))));
    }

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
    payload[cfg.apiField] = Number(getFieldValue(cfg));
  });
  const heightVal = Number(document.getElementById('dbHeight').value);
  const weightVal = Number(document.getElementById('dbWeight').value);
  payload.bmi = computeBmi(heightVal, weightVal);
  return payload;
}

function getAuthToken() {
  return typeof swasthaiGetToken === 'function' ? swasthaiGetToken() : null;
}

function showError(message, { retryable = false } = {}) {
  const alertBox = document.getElementById('diabetesFormAlert');
  const alertText = document.getElementById('diabetesFormAlertText');
  const retryBtn = document.getElementById('dbRetryBtn');
  alertText.textContent = message;
  retryBtn.hidden = !retryable;
  alertBox.hidden = false;
}

function clearFormAlert() {
  document.getElementById('diabetesFormAlert').hidden = true;
}

function messageForError(err) {
  if (err && err.status === 401) {
    return { message: 'Your session has expired. Please sign in again.', retryable: false };
  }
  if (err && err.status === 422) {
    return { message: 'Some of the information could not be validated. Please review your answers and try again.', retryable: false };
  }
  if (err && err.status === 503) {
    return { message: 'The diabetes risk model is not available right now. Please try again later.', retryable: true };
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
  document.getElementById('dbResultPanel').scrollIntoView({ behavior: dbPrefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
}

function setLoadingState(isLoading) {
  const submitBtn = document.getElementById('dbSubmitBtn');
  const backBtn = document.getElementById('dbBackBtn');
  submitBtn.disabled = isLoading;
  backBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? 'Analyzing your responses...' : 'Assess My Risk';
}

async function submitDiabetesPrediction(payload) {
  return SwasthAPI.predictions.diabetes(payload);
}

let lastPayload = null;

async function handleSubmit(event) {
  event.preventDefault();
  if (isTransitioning) return;
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

  setLoadingState(true);
  try {
    lastPayload = mapFormToApiPayload();
    const result = await submitDiabetesPrediction(lastPayload);
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
  }
}

async function retrySubmission() {
  if (!lastPayload) return;
  clearFormAlert();
  setLoadingState(true);
  try {
    const result = await submitDiabetesPrediction(lastPayload);
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
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('diabetesForm');
  if (!form) return;

  document.getElementById('dbBeginBtn').addEventListener('click', () => {
    document.getElementById('dbWelcome').hidden = true;
    document.getElementById('dbAssessment').hidden = false;
    goToStep(0);
  });

  document.getElementById('dbHeight').addEventListener('input', updateBmiPreview);
  document.getElementById('dbWeight').addEventListener('input', updateBmiPreview);

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
