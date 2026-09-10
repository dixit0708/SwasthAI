/**
 * Diabetes Risk Screening — end-to-end QA suite (BRFSS-v2, 14-feature).
 *
 * v2 note: the prior 21-feature v1 model used 6 sections (About You, Health
 * History, Lifestyle, Wellbeing, Access & Background, Review). The v2
 * feature-selection study found the 14-feature "Expanded" set performs
 * comparably while dropping every sensitive/access question (income,
 * education, healthcare coverage, cost-barrier) and the two day-count
 * recall questions (mental/physical health days) and vegetables. Removing
 * those emptied "Wellbeing" down to one question (general health, now in
 * "About You") and emptied "Access & Background" entirely, so both were
 * removed rather than kept as near-empty/artificial steps. The wizard is
 * now 4 sections: About You, Health History, Lifestyle, Review.
 *
 * Prerequisites (not started by this suite):
 *   Backend:  cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
 *   Frontend: cd frontend && python -m http.server 5500 --bind 127.0.0.1
 * Run: npx playwright test
 *
 * Test-account setup uses the REAL backend (POST /api/v1/auth/register) via
 * Playwright's request context — not mocked, the exact endpoint
 * register.html's own form calls. One test drives the real register.html
 * UI end-to-end; the rest inject the resulting real session into
 * localStorage before navigating, to avoid re-typing registration ~20 times.
 */
const { test, expect } = require('@playwright/test');

const BACKEND_URL = 'http://127.0.0.1:8000';
const TEST_PASSWORD = 'correct-horse-battery-staple';
const TOTAL_STEPS = 4; // About You, Health History, Lifestyle, Review

function uniqueEmail() {
  return `pw-diabetes-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`;
}

async function registerRealUser(requestContext, name = 'Playwright QA') {
  const email = uniqueEmail();
  const res = await requestContext.post(`${BACKEND_URL}/api/v1/auth/register`, {
    data: { name, email, password: TEST_PASSWORD },
  });
  expect(res.ok(), 'real backend registration must succeed').toBeTruthy();
  return res.json();
}

async function loginAsNewUser(page) {
  const session = await registerRealUser(page.request);
  await page.addInitScript((s) => {
    localStorage.setItem('swasthai_token', s.access_token);
    localStorage.setItem('swasthai_user', JSON.stringify(s.user));
  }, session);
  return session;
}

const LOWER_RISK_PROFILE = {
  sex: 'Female', age: '30-34', heightCm: '170', weightKg: '64', genHlth: 'Excellent',
  highBp: 'No', highChol: 'No', cholCheck: 'Yes',
  stroke: 'No', heartDisease: 'No', diffWalk: 'No',
  smoker: 'No', physActivity: 'Yes', fruits: 'Yes', hvyAlcohol: 'No',
};

// Mirrors a profile independently verified against the live v2 backend
// artifact so this test does not rely on luck to reach the elevated branch.
const HIGHER_RISK_PROFILE = {
  sex: 'Male', age: '65-69', heightCm: '175', weightKg: '116', genHlth: 'Fair',
  highBp: 'Yes', highChol: 'Yes', cholCheck: 'Yes',
  stroke: 'No', heartDisease: 'Yes', diffWalk: 'Yes',
  smoker: 'Yes', physActivity: 'No', fruits: 'No', hvyAlcohol: 'No',
};

function stepScope(page, step) {
  return page.locator(`.db-step[data-step="${step}"]`);
}

async function answerYesNo(scope, questionRegex, label) {
  await scope.getByRole('radiogroup', { name: questionRegex }).getByRole('radio', { name: label, exact: true }).check();
}

async function fillStep0(page, profile) {
  const scope = stepScope(page, 0);
  await scope.getByRole('radiogroup', { name: /identify your sex/i }).getByRole('radio', { name: profile.sex, exact: true }).check();
  await scope.getByLabel(/age range/i).selectOption({ label: profile.age });
  await scope.getByLabel('Height').fill(profile.heightCm);
  await scope.getByLabel('Weight').fill(profile.weightKg);
  await scope.getByLabel(/would you say your health is/i).selectOption({ label: profile.genHlth });
}

async function fillStep1(page, profile) {
  const scope = stepScope(page, 1);
  await answerYesNo(scope, /high blood pressure/i, profile.highBp);
  await answerYesNo(scope, /high cholesterol/i, profile.highChol);
  await answerYesNo(scope, /cholesterol checked/i, profile.cholCheck);
  await answerYesNo(scope, /had a stroke/i, profile.stroke);
  await answerYesNo(scope, /coronary heart disease/i, profile.heartDisease);
  await answerYesNo(scope, /difficulty walking/i, profile.diffWalk);
}

async function fillStep2(page, profile) {
  const scope = stepScope(page, 2);
  await answerYesNo(scope, /100 cigarettes/i, profile.smoker);
  await answerYesNo(scope, /physical activity or exercise/i, profile.physActivity);
  await answerYesNo(scope, /fruit one or more/i, profile.fruits);
  await answerYesNo(scope, /heavy drinker/i, profile.hvyAlcohol);
}

const STEP_FILLERS = [fillStep0, fillStep1, fillStep2];

async function goToDiabetesPage(page) {
  await page.goto('/prediction-diabetes.html');
  await expect(page.getByRole('heading', { name: 'Diabetes Risk Screening' })).toBeVisible();
}

async function beginAssessment(page) {
  await page.getByRole('button', { name: 'Begin Assessment' }).click();
  await expect(page.getByText(/Section 1 of 4/)).toBeVisible();
}

/** Fills sections 0-2 via the real controls, clicking Next after each,
 * landing on Review (section 4 of 4). */
async function runWizardToReview(page, profile) {
  for (let step = 0; step < 3; step += 1) {
    await expect(page.getByText(`Section ${step + 1} of ${TOTAL_STEPS}`)).toBeVisible();
    await STEP_FILLERS[step](page, profile);
    await page.getByRole('button', { name: 'Next' }).click();
  }
  await expect(page.getByText(`Section ${TOTAL_STEPS} of ${TOTAL_STEPS}`)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Review your answers' })).toBeVisible();
}

// ---------------------------------------------------------------------------
// Authentication
// ---------------------------------------------------------------------------

test.describe('Authentication', () => {
  test('logged-out user cannot reach the diabetes assessment', async ({ page }) => {
    await page.goto('/prediction-diabetes.html');
    await page.waitForURL(/login\.html/);
    expect(page.url()).toContain('login.html');
    await expect(page.locator('#diabetesForm')).toHaveCount(0);
  });

  test('a real registration + login reaches the diabetes page with a valid session', async ({ page }) => {
    const email = uniqueEmail();
    await page.goto('/register.html');
    await page.locator('#regName').fill('Playwright QA');
    await page.locator('#regEmail').fill(email);
    await page.locator('#regPassword').fill(TEST_PASSWORD);
    await page.locator('#regConfirm').fill(TEST_PASSWORD);
    await page.locator('#registerForm').getByRole('checkbox').check();
    await page.locator('#registerForm').getByRole('button', { name: 'Create Account' }).click();
    await page.waitForURL(/dashboard\.html/);

    const token = await page.evaluate(() => localStorage.getItem('swasthai_token'));
    expect(token).toBeTruthy();

    await goToDiabetesPage(page);
    expect(page.url()).not.toContain('login.html');
  });
});

// ---------------------------------------------------------------------------
// Page load
// ---------------------------------------------------------------------------

test.describe('Page load', () => {
  test('loads with no console errors and welcome screen present', async ({ page }) => {
    const consoleErrors = [];
    const pageErrors = [];
    const failedRequests = [];
    page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('pageerror', (err) => pageErrors.push(String(err)));
    page.on('requestfailed', (req) => failedRequests.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText}`));

    await loginAsNewUser(page);
    await goToDiabetesPage(page);

    await expect(page.getByText(/three minutes/i)).toBeVisible();
    await expect(page.getByText(/14 questions/i)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Begin Assessment' })).toBeVisible();

    const brokenImages = await page.evaluate(() =>
      Array.from(document.images).filter((img) => !img.complete || img.naturalWidth === 0).map((img) => img.src)
    );
    expect(brokenImages, 'no broken images').toEqual([]);

    const criticalConsoleErrors = consoleErrors.filter((e) => !/favicon/i.test(e));
    expect(criticalConsoleErrors, `console errors: ${criticalConsoleErrors.join(' | ')}`).toEqual([]);
    expect(pageErrors, `uncaught page errors: ${pageErrors.join(' | ')}`).toEqual([]);
    expect(failedRequests, `failed requests: ${failedRequests.join(' | ')}`).toEqual([]);
  });

  test('first step: Back hidden, Next visible, progress correct', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    await expect(page.getByRole('button', { name: 'Back' })).toBeHidden();
    await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Assess My Risk' })).toBeHidden();
    await expect(page.getByText('Section 1 of 4 · About You')).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Field coverage
// ---------------------------------------------------------------------------

test.describe('Field coverage', () => {
  test('all 14 model inputs are represented across the 3 question sections', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    const perStep = [
      { radios: 1, selects: 2, numbers: 2 }, // step0: sex, age, gen_hlth, height, weight (bmi derived)
      { radios: 6, selects: 0, numbers: 0 }, // step1
      { radios: 4, selects: 0, numbers: 0 }, // step2
    ];
    let total = 0;
    for (let step = 0; step < 3; step += 1) {
      const scope = stepScope(page, step);
      // Plain CSS locator, not getByRole: hidden (inactive) steps are
      // excluded from the accessibility tree, so a role query would
      // undercount every step except the currently visible one.
      const radiogroups = await scope.locator('[role="radiogroup"]').count();
      const selects = await scope.locator('select').count();
      const numbers = await scope.locator('input[type="number"]').count();
      expect(radiogroups, `step ${step} radiogroups`).toBe(perStep[step].radios);
      expect(selects, `step ${step} selects`).toBe(perStep[step].selects);
      expect(numbers, `step ${step} numbers`).toBe(perStep[step].numbers);
      total += radiogroups + selects;
    }
    // sex+age+gen_hlth + 6 + 4 + bmi(from height/weight) = 14
    expect(total + 1 /* bmi */).toBe(14);
  });
});

// ---------------------------------------------------------------------------
// Wizard navigation, bounded state, and the boundary attack
// ---------------------------------------------------------------------------

test.describe('Wizard navigation and bounded state', () => {
  test('cannot advance with empty required fields; Back/Next move correctly', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.getByText('Section 1 of 4')).toBeVisible(); // still on step 0
    await expect(page.locator('#sexError')).toBeVisible();

    await fillStep0(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.getByText('Section 2 of 4')).toBeVisible();

    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.getByText('Section 1 of 4')).toBeVisible();
    await expect(stepScope(page, 0).getByRole('radio', { name: 'Female', exact: true })).toBeChecked();

    await page.getByRole('button', { name: 'Next' }).click();
    await fillStep1(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.getByText('Section 3 of 4')).toBeVisible();
  });

  test('BOUNDARY ATTACK — 50 rapid Next clicks at the final step never exceed it, never break progress', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await runWizardToReview(page, LOWER_RISK_PROFILE);

    // At review: Next must not exist as a clickable path at all. Fire 50
    // raw click events straight at the DOM node if it's still present,
    // bypassing Playwright's own actionability wait, to prove the app's
    // OWN state guards hold even under a maximally hostile attack.
    await page.evaluate(() => {
      const btn = document.getElementById('dbNextBtn');
      for (let i = 0; i < 50; i += 1) btn.click();
    });

    // Still on review — never advanced past the last section, never wrapped
    // into a broken "Section 5 of 4" / "undefined" state, Submit still there.
    await expect(page.getByText('Section 4 of 4 · Review')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Review your answers' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Assess My Risk' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Next' })).toBeHidden();

    const progressText = await page.locator('#dbProgressLabel').innerText();
    expect(progressText).not.toMatch(/undefined/i);
    expect(progressText).not.toMatch(/Section [5-9]/);
    expect(progressText).not.toMatch(/Section \d\d/);

    const fillTransform = await page.locator('#dbProgressFill').evaluate((el) => getComputedStyle(el).transform);
    expect(fillTransform).not.toBe('none'); // still a valid, sane transform, not blown out
  });

  test('BOUNDARY ATTACK — 10 rapid Next clicks mid-wizard advance at most one section per validated click', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await fillStep0(page, LOWER_RISK_PROFILE);

    await page.evaluate(() => {
      const btn = document.getElementById('dbNextBtn');
      for (let i = 0; i < 10; i += 1) btn.click();
    });

    // Section 1 (Health History) is unanswered, so validation must have
    // blocked every one of the 10 clicks from advancing past it.
    await expect(page.getByText('Section 2 of 4')).toBeVisible();
    await expect(page.locator('#high_bpError')).toBeVisible();
  });

  test('BACK BOUNDARY — repeated Back clicks on the first step never go negative', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    await page.evaluate(() => {
      // Back is hidden but not necessarily absent — attack the raw node.
      const btn = document.getElementById('dbBackBtn');
      for (let i = 0; i < 20; i += 1) btn.click();
    });

    await expect(page.getByText('Section 1 of 4 · About You')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Back' })).toBeHidden();
  });

  test('double-click and Enter-key repeats on Next do not skip sections', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await fillStep0(page, LOWER_RISK_PROFILE);

    await page.getByRole('button', { name: 'Next' }).dblclick();
    // Unanswered step 1 must still block — double-click must not have
    // fired two successful advances (which would have skipped to step 2).
    await expect(page.getByText('Section 2 of 4')).toBeVisible();

    await fillStep1(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).focus();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    // Step 2 unanswered — repeated Enter must not skip past it either.
    await expect(page.getByText('Section 3 of 4')).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Categorical fields
// ---------------------------------------------------------------------------

test.describe('Categorical fields', () => {
  test('every option is selectable and produces a valid, distinct value', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    const ageOptions = await stepScope(page, 0).getByLabel(/age range/i).locator('option').allTextContents();
    expect(ageOptions.filter((t) => t !== 'Select your age range')).toHaveLength(13);
    expect(ageOptions.some((t) => /18-24/.test(t))).toBeTruthy();
    expect(ageOptions.some((t) => /80 or older/.test(t))).toBeTruthy();

    const sexGroup = stepScope(page, 0).getByRole('radiogroup', { name: /identify your sex/i });
    await sexGroup.getByRole('radio', { name: 'Female', exact: true }).check();
    await expect(sexGroup.getByRole('radio', { name: 'Female', exact: true })).toBeChecked();
    await sexGroup.getByRole('radio', { name: 'Male', exact: true }).check();
    await expect(sexGroup.getByRole('radio', { name: 'Male', exact: true })).toBeChecked();
    await expect(sexGroup.getByRole('radio', { name: 'Female', exact: true })).not.toBeChecked();

    const genHlthOptions = await stepScope(page, 0).getByLabel(/would you say your health is/i).locator('option').allTextContents();
    expect(genHlthOptions.filter((t) => t !== 'Select an option')).toEqual(['Excellent', 'Very good', 'Good', 'Fair', 'Poor']);

    await page.getByRole('button', { name: 'Next' }).click(); // will be blocked (height/weight missing) — fine, just checking step0 selects above without navigating
    await fillStep0(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.getByText('Section 2 of 4')).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// BMI calculation
// ---------------------------------------------------------------------------

test.describe('BMI calculation', () => {
  test('computes BMI correctly and sends it as a number, never a string', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    await stepScope(page, 0).getByLabel('Height').fill('170');
    await stepScope(page, 0).getByLabel('Weight').fill('64');
    await expect(page.locator('#dbBmiValue')).toHaveText('22.1');

    await stepScope(page, 0).getByLabel('Height').fill('160');
    await stepScope(page, 0).getByLabel('Weight').fill('55');
    await expect(page.locator('#dbBmiValue')).toHaveText('21.5'); // 55/1.6^2 = 21.484 -> 21.5

    let capturedBody = null;
    await page.route('**/api/v1/predict/diabetes', async (route) => {
      capturedBody = route.request().postDataJSON();
      await route.continue();
    });

    await runWizardToReview(page, { ...LOWER_RISK_PROFILE, heightCm: '160', weightKg: '55' });
    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.getByRole('heading', { name: /Elevated Estimated Risk|No Elevated Risk Identified/ })).toBeVisible();

    expect(capturedBody).not.toBeNull();
    expect(capturedBody.bmi).toBe(21.5);
    expect(typeof capturedBody.bmi).toBe('number');
  });
});

// ---------------------------------------------------------------------------
// Review and edit
// ---------------------------------------------------------------------------

test.describe('Review and edit', () => {
  test('review shows human-readable answers grouped by section, and editing updates them correctly', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await runWizardToReview(page, LOWER_RISK_PROFILE);

    const reviewList = page.locator('#dbReviewList');
    await expect(reviewList).not.toContainText('high_bp');
    await expect(reviewList).not.toContainText('gen_hlth');
    await expect(reviewList.getByText('About You')).toBeVisible();
    await expect(reviewList.getByText('Health History')).toBeVisible();

    const cholCheckSection = reviewList.locator('.db-review__section').filter({ hasText: 'Health History' });
    const cholCheckRow = cholCheckSection.locator('.db-review__row').filter({ hasText: /cholesterol checked/i });
    await expect(cholCheckRow.getByText('Yes', { exact: true })).toBeVisible();

    await cholCheckSection.getByRole('button', { name: /Edit/i }).click();
    await expect(page.getByText('Section 2 of 4')).toBeVisible();
    await stepScope(page, 1).getByRole('radiogroup', { name: /cholesterol checked/i }).getByRole('radio', { name: 'No' }).check();

    await page.getByRole('button', { name: 'Next' }).click();
    await fillStep2(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();

    const updatedSection = page.locator('#dbReviewList .db-review__section').filter({ hasText: 'Health History' });
    const updatedRow = updatedSection.locator('.db-review__row').filter({ hasText: /cholesterol checked/i });
    await expect(updatedRow.getByText('No', { exact: true })).toBeVisible();
    await expect(updatedRow.getByText('Yes', { exact: true })).toHaveCount(0);
    await expect(updatedSection.locator('.db-review__row').filter({ hasText: /cholesterol checked/i })).toHaveCount(1);
  });
});

// ---------------------------------------------------------------------------
// Real API submission, headers, response, dedup
// ---------------------------------------------------------------------------

test.describe('Real API submission', () => {
  test('submits exactly the 14 expected fields with a real bearer token, gets a valid real response', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    let request = null;
    page.on('request', (req) => {
      if (req.url().includes('/api/v1/predict/diabetes') && req.method() === 'POST') request = req;
    });

    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.getByRole('heading', { name: 'No Elevated Risk Identified' })).toBeVisible();

    expect(request).not.toBeNull();
    expect(request.method()).toBe('POST');
    expect(new URL(request.url()).pathname).toBe('/api/v1/predict/diabetes');

    const headers = request.headers();
    expect(headers['content-type']).toContain('application/json');
    expect(headers.authorization).toMatch(/^Bearer .+/);
    expect(headers.authorization.length).toBeGreaterThan(10);

    const body = request.postDataJSON();
    const expectedFields = [
      'sex', 'age', 'bmi', 'high_bp', 'high_chol', 'chol_check',
      'heart_disease_or_attack', 'phys_activity', 'fruits',
      'hvy_alcohol_consump', 'stroke', 'gen_hlth', 'diff_walk', 'smoker',
    ];
    expect(Object.keys(body).sort()).toEqual(expectedFields.sort());
    expect(body).not.toHaveProperty('user_id');
    expect(body).not.toHaveProperty('threshold');
    expect(body).not.toHaveProperty('token');
    expect(body).not.toHaveProperty('model_version');
    expect(body).not.toHaveProperty('Pregnancies'); // Pima dataset field — never applicable here
    expect(body).not.toHaveProperty('family_history'); // explicitly excluded from v2, see reports/v2_final_recommendation.md
    // v1-only fields that were removed for v2 must never be sent.
    ['veggies', 'any_healthcare', 'no_docbc_cost', 'ment_hlth', 'phys_hlth', 'education', 'income'].forEach((removed) => {
      expect(body).not.toHaveProperty(removed);
    });
    expect(JSON.stringify(body)).not.toMatch(/Bearer/);
  });

  test('rejects rapid repeated submit clicks — only one request is sent', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    let requestCount = 0;
    page.on('request', (req) => {
      if (req.url().includes('/api/v1/predict/diabetes') && req.method() === 'POST') requestCount += 1;
    });

    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.evaluate(() => {
      const btn = document.getElementById('dbSubmitBtn');
      btn.click();
      btn.click();
      btn.click();
    });
    await expect(page.getByRole('heading', { name: 'No Elevated Risk Identified' })).toBeVisible();
    expect(requestCount).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Result states
// ---------------------------------------------------------------------------

test.describe('Result states', () => {
  test('screening_negative renders calm, screening-oriented, non-diagnostic UI', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();

    await expect(page.getByRole('heading', { name: 'No Elevated Risk Identified' })).toBeVisible();
    await expect(page.locator('#resultMessage')).not.toBeEmpty();
    await expect(page.locator('#resultDisclaimer')).toContainText('not a medical diagnosis');

    const bodyText = await page.locator('#dbResultPanel').innerText();
    expect(bodyText).not.toMatch(/you don't have diabetes/i);
    expect(bodyText).not.toMatch(/diabetes-free/i);
    expect(bodyText).not.toMatch(/zero risk/i);
    expect(bodyText).not.toMatch(/you have diabetes/i);
    expect(bodyText).not.toMatch(/diagnosis confirmed/i);

    await page.getByRole('button', { name: 'Review My Answers' }).click();
    await expect(page.getByRole('heading', { name: 'Review your answers' })).toBeVisible();

    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.getByRole('heading', { name: 'No Elevated Risk Identified' })).toBeVisible();
    await page.getByRole('link', { name: 'Return to Dashboard' }).click();
    await page.waitForURL(/dashboard\.html/);
  });

  test('screening_elevated renders calm (non-alarmist), non-diagnostic UI', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await runWizardToReview(page, HIGHER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();

    await expect(page.getByRole('heading', { name: 'Elevated Estimated Risk' })).toBeVisible();
    await expect(page.locator('#resultMessage')).not.toBeEmpty();
    await expect(page.locator('#resultDisclaimer')).toContainText('not a medical diagnosis');

    const bodyText = await page.locator('#dbResultPanel').innerText();
    expect(bodyText).not.toMatch(/you have diabetes/i);
    expect(bodyText).not.toMatch(/diagnosis confirmed/i);
    expect(bodyText).not.toMatch(/you will develop diabetes/i);
    expect(bodyText.toUpperCase()).not.toContain('EMERGENCY');

    await page.getByRole('button', { name: 'Review My Answers' }).click();
    await expect(page.getByRole('heading', { name: 'Review your answers' })).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// No frontend threshold logic (static check)
// ---------------------------------------------------------------------------

test.describe('No frontend threshold logic', () => {
  test('the diabetes JS never compares risk_probability against a hardcoded cutoff', async () => {
    const fs = require('fs');
    const src = fs.readFileSync(require.resolve('../../frontend/js/prediction-diabetes.js'), 'utf8');
    const forbidden = [
      /risk_probability\s*[<>]=?\s*0\.1\b/,
      /risk_probability\s*[<>]=?\s*0\.5\b/,
      /probability\s*[<>]=?\s*0\.1\b/,
      /probability\s*[<>]=?\s*0\.5\b/,
    ];
    forbidden.forEach((re) => expect(src).not.toMatch(re));
    expect(src).toContain('result.is_elevated');
  });
});

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

test.describe('Error handling', () => {
  test('401 triggers the existing session-expired/logout behavior', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await page.route('**/api/v1/predict/diabetes', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Invalid or expired token' }) })
    );
    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await page.waitForURL(/login\.html/);
  });

  test('422 shows a validation message, not raw backend detail', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await page.route('**/api/v1/predict/diabetes', (route) =>
      route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: [{ msg: 'value is not a valid integer', loc: ['body', 'sex'] }] }) })
    );
    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.locator('#diabetesFormAlertText')).toContainText(/review your answers/i);
    await expect(page.locator('#diabetesFormAlertText')).not.toContainText('loc');
  });

  test('500 shows a generic message with a retry option, never internal details', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    let attempts = 0;
    await page.route('**/api/v1/predict/diabetes', (route) => {
      attempts += 1;
      if (attempts === 1) {
        return route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Traceback: File "app/main.py", line 42 — MongoServerError: auth failed at mongodb+srv://...' }),
        });
      }
      return route.continue();
    });
    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();

    await expect(page.locator('#diabetesFormAlertText')).toContainText("couldn't complete your assessment");
    const alertText = await page.locator('#diabetesFormAlertText').innerText();
    expect(alertText).not.toContain('Traceback');
    expect(alertText).not.toContain('mongodb');

    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('heading', { name: /Elevated Estimated Risk|No Elevated Risk Identified/ })).toBeVisible();
  });

  test('network failure shows a connection error with a retry option', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await page.route('**/api/v1/predict/diabetes', (route) => route.abort('failed'));
    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.locator('#diabetesFormAlertText')).toContainText(/connect/i);
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
  });

  test('a malformed response is treated as unexpected, not rendered as a result', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await page.route('**/api/v1/predict/diabetes', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ risk_level: 'nonsense' }) })
    );
    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.locator('#diabetesFormAlertText')).toContainText(/unexpected response/i);
    await expect(page.locator('#dbResultPanel')).toBeHidden();
  });

  test('a script tag in the backend message is rendered as inert text, not executed', async ({ page }) => {
    let dialogFired = false;
    page.on('dialog', async (dialog) => { dialogFired = true; await dialog.dismiss(); });

    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);
    await page.route('**/api/v1/predict/diabetes', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          risk_level: 'screening_negative',
          risk_probability: 0.05,
          threshold: 0.1,
          is_elevated: false,
          message: "<script>alert('xss')</script><img src=x onerror=\"alert('xss2')\">",
          model_version: 'test',
          disclaimer: 'test disclaimer',
        }),
      })
    );
    await runWizardToReview(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.getByRole('heading', { name: 'No Elevated Risk Identified' })).toBeVisible();

    expect(dialogFired).toBe(false);
    const messageHtml = await page.locator('#resultMessage').innerHTML();
    expect(messageHtml).not.toContain('<script>');
    expect(messageHtml).not.toContain('<img');
  });
});

// ---------------------------------------------------------------------------
// Accessibility (desktop only — not viewport-dependent)
// ---------------------------------------------------------------------------

test.describe('Accessibility', () => {
  test('labels, focus management, radiogroups, and keyboard-only progression', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop', 'keyboard/focus behavior is not viewport-dependent');

    await loginAsNewUser(page);
    await goToDiabetesPage(page);
    await beginAssessment(page);

    const step0Controls = stepScope(page, 0).locator('select, input[type="number"]');
    const count = await step0Controls.count();
    for (let i = 0; i < count; i += 1) {
      const id = await step0Controls.nth(i).getAttribute('id');
      await expect(page.locator(`label[for="${id}"]`)).toHaveCount(1);
    }

    await expect(stepScope(page, 0).getByRole('radiogroup', { name: /identify your sex/i })).toHaveCount(1);

    await fillStep0(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
    const focusedText = await page.evaluate(() => document.activeElement?.textContent);
    expect(focusedTag).toBe('LEGEND');
    expect(focusedText).toContain('Health History');

    await expect(page.locator('#dbProgressLabel[aria-live="polite"]')).toHaveCount(1);

    // Keyboard-only radio selection: Tab to the first radio, arrow to the
    // second option, and confirm it becomes checked without a mouse.
    await page.keyboard.press('Tab'); // into the first radio of the group
    await page.keyboard.press('ArrowRight');
    const checkedName = await page.evaluate(() => document.querySelector('input[name="high_bp"]:checked')?.value);
    expect(['0', '1']).toContain(checkedName);
  });
});

// ---------------------------------------------------------------------------
// Responsive layout
// ---------------------------------------------------------------------------

test.describe('Responsive layout', () => {
  test('no horizontal scroll and controls remain usable through a full journey', async ({ page }) => {
    await loginAsNewUser(page);
    await goToDiabetesPage(page);

    const noHorizontalScroll = async () => {
      const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
    };

    await noHorizontalScroll();
    await page.screenshot({ path: `test-results/screenshots/${test.info().project.name}-welcome.png` });

    await beginAssessment(page);
    await noHorizontalScroll();
    await page.screenshot({ path: `test-results/screenshots/${test.info().project.name}-step1.png` });

    await fillStep0(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();
    await fillStep1(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();
    await noHorizontalScroll();
    await page.screenshot({ path: `test-results/screenshots/${test.info().project.name}-step3.png` });

    await fillStep2(page, LOWER_RISK_PROFILE);
    await page.getByRole('button', { name: 'Next' }).click();

    await expect(page.getByRole('heading', { name: 'Review your answers' })).toBeVisible();
    await noHorizontalScroll();
    await page.screenshot({ path: `test-results/screenshots/${test.info().project.name}-review.png`, fullPage: true });

    await page.getByRole('button', { name: 'Assess My Risk' }).click();
    await expect(page.getByRole('heading', { name: 'No Elevated Risk Identified' })).toBeVisible();
    await noHorizontalScroll();
    await page.screenshot({ path: `test-results/screenshots/${test.info().project.name}-result.png` });

    const dashboardLink = page.getByRole('link', { name: 'Return to Dashboard' });
    const box = await dashboardLink.boundingBox();
    expect(box.width).toBeGreaterThan(0);
    expect(box.height).toBeGreaterThan(0);
  });
});
