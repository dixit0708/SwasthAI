/**
 * SwasthAI — Diet & lifestyle plan.
 *
 * 1. A short questionnaire (daily routine, food preference, regional food,
 *    activity, habits). Answers are saved to the health profile with
 *    PUT /health-profile/me, so they are asked only once and can be edited.
 * 2. The plan from GET /diet/recommendations: an Indian day of meals timed
 *    to the user's routine, eating guidance, a week of activity, routine
 *    and habit tips, and medication safe-use tips.
 *
 * All guidance comes from the server's rule-based engine; this file only
 * collects answers and presents the result.
 */
(() => {
  const root = document.getElementById('dietContent');
  if (!root) return;
  const esc = AppUI.esc;

  const INTENSITY = {
    rest: ['Rest', ''],
    light: ['Light', 'pill--info'],
    moderate: ['Moderate', 'pill--ok'],
    vigorous: ['Vigorous', 'pill--warn']
  };

  // ── Questionnaire definition ─────────────────────────────────────────────
  const STEPS = [
    {
      key: 'occupation_type',
      title: 'Which best describes your day?',
      hint: 'This decides when your meals are planned and which daily tips you get.',
      options: [
        ['student', 'fa-graduation-cap', 'Student', 'School, college or coaching, with long study hours'],
        ['working_professional', 'fa-briefcase', 'Working professional', 'Day job, mostly at a desk or in meetings'],
        ['night_shift', 'fa-moon', 'Night or rotating shifts', 'Hospital, BPO, factory, security or similar'],
        ['homemaker', 'fa-house', 'Homemaker', 'Running the home and caring for family'],
        ['physical_work', 'fa-person-digging', 'Physically active job', 'On your feet: field work, labour, delivery, farming'],
        ['retired', 'fa-person-cane', 'Retired', 'Mostly at home, with a flexible routine']
      ]
    },
    {
      key: 'diet_preference',
      title: 'What do you eat?',
      hint: 'Every food suggestion will follow this.',
      options: [
        ['vegetarian', 'fa-leaf', 'Vegetarian', 'No meat, fish or eggs'],
        ['eggetarian', 'fa-egg', 'Vegetarian + eggs', 'Vegetarian, but eggs are fine'],
        ['non_vegetarian', 'fa-drumstick-bite', 'Non-vegetarian', 'Eggs, fish, chicken or meat'],
        ['vegan', 'fa-seedling', 'Vegan', 'No animal products, including milk and curd'],
        ['jain', 'fa-spa', 'Jain', 'Vegetarian, without onion, garlic or root vegetables']
      ]
    },
    {
      key: 'cuisine_region',
      title: 'What kind of food do you usually eat at home?',
      hint: 'So your plan uses the staples you already cook.',
      options: [
        ['north', 'fa-bread-slice', 'North Indian', 'Roti, dal, sabzi, paratha, poha'],
        ['south', 'fa-bowl-rice', 'South Indian', 'Rice, sambar, rasam, idli, dosa'],
        ['east', 'fa-fish', 'East Indian', 'Rice, dal, machher jhol, chira, luchi'],
        ['west', 'fa-wheat-awn', 'West Indian', 'Bhakri, thepla, poha, dal-rice'],
        ['mixed', 'fa-utensils', 'A mix', 'Both roti and rice, from different regions']
      ]
    },
    {
      key: 'activity_level',
      title: 'How active are you on most days?',
      hint: 'Your exercise plan starts from where you are today.',
      options: [
        ['sedentary', 'fa-couch', 'Mostly sitting', 'Little or no exercise'],
        ['light', 'fa-person-walking', 'Lightly active', 'Walks or light exercise 1 to 2 days a week'],
        ['moderate', 'fa-person-running', 'Moderately active', 'Exercise 3 to 5 days a week'],
        ['active', 'fa-dumbbell', 'Very active', 'Exercise or sport 6 to 7 days a week']
      ]
    },
    { key: 'habits', title: 'A few habits', hint: 'All optional. Skip anything you prefer not to answer.' }
  ];

  const HABITS = {
    smoking_status: ['Tobacco (cigarette, bidi, gutka, khaini)', [['never', 'Never'], ['former', 'Used to, stopped'], ['current', 'Currently']]],
    alcohol_use: ['Alcohol', [['none', 'Don\'t drink'], ['occasional', 'Occasionally'], ['regular', 'Regularly']]]
  };

  const quiz = { step: 0, answers: {}, profile: null };

  function choiceHtml(name, [value, icon, title, desc], checked) {
    return `
      <label class="choice">
        <input type="radio" name="${esc(name)}" value="${esc(value)}"${checked ? ' checked' : ''}>
        <span class="choice__icon"><i class="fas ${esc(icon)}" aria-hidden="true"></i></span>
        <span class="choice__text"><span class="choice__title">${esc(title)}</span><span class="choice__desc">${esc(desc)}</span></span>
      </label>`;
  }

  function smallChoiceHtml(name, [value, label], checked) {
    return `
      <label class="choice choice--small">
        <input type="radio" name="${esc(name)}" value="${esc(value)}"${checked ? ' checked' : ''}>
        <span class="choice__title">${esc(label)}</span>
      </label>`;
  }

  function habitsStepHtml() {
    const a = quiz.answers;
    const p = quiz.profile || {};
    const needsBody = !p.height_cm || !p.weight_kg;
    const groups = Object.entries(HABITS).map(([key, [label, opts]]) => `
      <div class="quiz__group">
        <h3>${esc(label)}</h3>
        <div class="choice-grid choice-grid--compact">${opts.map((o) => smallChoiceHtml(key, o, a[key] === o[0])).join('')}</div>
      </div>`).join('');
    return `
      ${groups}
      <div class="quiz__group">
        <h3>Sleep</h3>
        <label class="field" style="max-width:260px;">
          <span class="field__label">Hours of sleep on most nights</span>
          <input type="number" class="field__control" id="quizSleep" min="0" max="24" step="0.5" inputmode="decimal" placeholder="e.g. 7" value="${a.sleep_hours ?? ''}">
        </label>
      </div>
      ${needsBody ? `
      <div class="quiz__group">
        <h3>Height and weight</h3>
        <div class="form-grid" style="max-width:520px;">
          <label class="field"><span class="field__label">Height <small>(cm)</small></span>
            <input type="number" class="field__control" id="quizHeight" min="30" max="260" step="0.1" inputmode="decimal" placeholder="e.g. 165" value="${a.height_cm ?? ''}"></label>
          <label class="field"><span class="field__label">Weight <small>(kg)</small></span>
            <input type="number" class="field__control" id="quizWeight" min="1" max="400" step="0.1" inputmode="decimal" placeholder="e.g. 62" value="${a.weight_kg ?? ''}"></label>
        </div>
        <p class="field__hint" style="margin-top: var(--sp-2);">Used to work out your BMI, which shapes portion advice.</p>
      </div>` : ''}`;
  }

  function renderQuiz() {
    const step = STEPS[quiz.step];
    const total = STEPS.length;
    const isLast = quiz.step === total - 1;
    const body = step.options
      ? `<div class="choice-grid">${step.options.map((o) => choiceHtml(step.key, o, quiz.answers[step.key] === o[0])).join('')}</div>`
      : habitsStepHtml();

    root.innerHTML = `
      <section class="panel quiz" aria-labelledby="quizLegend">
        <div class="panel__body">
          <div class="quiz__top">
            <span>Question ${quiz.step + 1} of ${total}</span>
            ${quiz.profile && hasCoreAnswers(quiz.profile) ? '<button type="button" class="btn btn-ghost btn-compact" id="quizCancel">Back to my plan</button>' : '<span>Takes about a minute</span>'}
          </div>
          <div class="quiz__bar" aria-hidden="true"><span style="width:${Math.round(((quiz.step + 1) / total) * 100)}%"></span></div>
          <form id="quizForm" novalidate>
            <fieldset>
              <legend id="quizLegend" tabindex="-1">${esc(step.title)}</legend>
              <p class="quiz__hint">${esc(step.hint)}</p>
              ${body}
            </fieldset>
            <p class="form-status form-status--error" id="quizError" role="alert" hidden></p>
            <div class="quiz__nav">
              <button type="button" class="btn btn-outline" id="quizBack"${quiz.step === 0 ? ' disabled' : ''}>Back</button>
              <button type="submit" class="btn btn-primary" id="quizNext">${isLast ? 'Create my plan' : 'Next'}</button>
            </div>
          </form>
        </div>
      </section>`;

    document.getElementById('quizLegend').focus({ preventScroll: true });
    document.getElementById('quizBack').addEventListener('click', () => {
      collect();
      quiz.step -= 1;
      renderQuiz();
    });
    document.getElementById('quizCancel')?.addEventListener('click', loadPlan);
    document.getElementById('quizForm').addEventListener('submit', onNext);
  }

  function collect() {
    const form = document.getElementById('quizForm');
    if (!form) return;
    const step = STEPS[quiz.step];
    if (step.options) {
      const picked = form.querySelector(`input[name="${step.key}"]:checked`);
      if (picked) quiz.answers[step.key] = picked.value;
      return;
    }
    Object.keys(HABITS).forEach((key) => {
      const picked = form.querySelector(`input[name="${key}"]:checked`);
      if (picked) quiz.answers[key] = picked.value;
    });
    const num = (id) => {
      const el = document.getElementById(id);
      if (!el || el.value.trim() === '') return undefined;
      return Number(el.value);
    };
    quiz.answers.sleep_hours = num('quizSleep');
    quiz.answers.height_cm = num('quizHeight');
    quiz.answers.weight_kg = num('quizWeight');
  }

  function showQuizError(message) {
    const error = document.getElementById('quizError');
    error.textContent = message;
    error.hidden = false;
  }

  async function onNext(e) {
    e.preventDefault();
    collect();
    const step = STEPS[quiz.step];
    if (step.options && !quiz.answers[step.key]) {
      showQuizError('Please choose one option to continue.');
      return;
    }
    if (quiz.step < STEPS.length - 1) {
      quiz.step += 1;
      renderQuiz();
      return;
    }

    const a = quiz.answers;
    if (a.sleep_hours !== undefined && (Number.isNaN(a.sleep_hours) || a.sleep_hours < 0 || a.sleep_hours > 24)) {
      return showQuizError('Sleep must be between 0 and 24 hours.');
    }
    if (a.height_cm !== undefined && (Number.isNaN(a.height_cm) || a.height_cm < 30 || a.height_cm > 260)) {
      return showQuizError('Please enter your height in centimetres (30 to 260).');
    }
    if (a.weight_kg !== undefined && (Number.isNaN(a.weight_kg) || a.weight_kg < 1 || a.weight_kg > 400)) {
      return showQuizError('Please enter your weight in kilograms (1 to 400).');
    }

    // Send only what was answered, so nothing already on the profile is cleared.
    const payload = {};
    ['occupation_type', 'diet_preference', 'cuisine_region', 'activity_level', 'smoking_status', 'alcohol_use', 'sleep_hours', 'height_cm', 'weight_kg']
      .forEach((key) => { if (a[key] !== undefined && a[key] !== null && a[key] !== '') payload[key] = a[key]; });

    const button = document.getElementById('quizNext');
    AppUI.setBusy(button, true, 'Creating your plan...');
    try {
      quiz.profile = await SwasthAPI.healthProfile.update(payload);
      // Guard against a silent loop: if the server did not keep the core
      // answers, say so here instead of showing the questionnaire again.
      if (!hasCoreAnswers(quiz.profile)) {
        AppUI.setBusy(button, false);
        showQuizError('We could not save your answers just now. Please try again in a moment.');
        return;
      }
      AppUI.toast('Your answers are saved. You can change them any time.');
      await loadPlan();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      AppUI.setBusy(button, false);
      showQuizError(AppUI.errorText(err));
    }
  }

  function hasCoreAnswers(profile) {
    return Boolean(profile.occupation_type && profile.diet_preference && profile.cuisine_region && profile.activity_level);
  }

  function startQuiz(profile) {
    quiz.profile = profile;
    quiz.step = 0;
    quiz.answers = {
      occupation_type: profile.occupation_type,
      diet_preference: profile.diet_preference,
      cuisine_region: profile.cuisine_region,
      activity_level: profile.activity_level,
      smoking_status: profile.smoking_status,
      alcohol_use: profile.alcohol_use,
      sleep_hours: profile.sleep_hours ?? undefined
    };
    renderQuiz();
  }

  // ── Plan ─────────────────────────────────────────────────────────────────
  function planForHtml(planFor) {
    const chips = [planFor.occupation, planFor.diet, planFor.region].filter(Boolean)
      .map((v) => `<span class="pill pill--plain" style="background:#fff; border:1px solid var(--border);">${esc(v)}</span>`).join(' ');
    return `
      <div class="plan-for">
        <div>
          <div class="plan-for__label">Your plan is built for</div>
          <div style="display:flex; gap: var(--sp-2); flex-wrap:wrap;">${chips}</div>
        </div>
        <button type="button" class="btn btn-outline btn-compact" id="editAnswers"><i class="fas fa-pen" aria-hidden="true"></i>&nbsp; Change my answers</button>
      </div>`;
  }

  function mealsHtml(plan) {
    const meals = plan.meals.map((m) => `
      <li class="meal">
        <div class="meal__when"><span class="meal__time">${esc(m.time)}</span><span class="meal__slot">${esc(m.slot)}</span></div>
        <div>
          <ul class="meal__items">${m.items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>
          ${m.tip ? `<p class="meal__tip"><i class="fas fa-lightbulb" aria-hidden="true"></i>${esc(m.tip)}</p>` : ''}
        </div>
      </li>`).join('');
    const swaps = (plan.swaps || []).map((s) => `<li>${esc(s)}</li>`).join('');
    return `
      <section class="panel" aria-labelledby="mealsTitle" style="margin-bottom: var(--sp-8);">
        <div class="panel__head">
          <h2 class="panel__title" id="mealsTitle" style="font-size: var(--text-lg);">Your day of eating</h2>
          <span class="pill pill--plain">Sample day &middot; swap dishes freely</span>
        </div>
        ${plan.schedule_note ? `<div class="panel__body" style="padding-bottom:0;"><p class="field__hint" style="margin:0;"><i class="fas fa-clock" aria-hidden="true"></i> ${esc(plan.schedule_note)}</p></div>` : ''}
        <ol class="meals" style="margin-top: var(--sp-2);">${meals}</ol>
        ${swaps ? `
          <div class="panel__body" style="border-top: 1px solid var(--border-light);">
            <h3 style="font-size: var(--text-sm); margin: 0 0 var(--sp-3);">Changes for your health</h3>
            <ul class="plain-list">${swaps}</ul>
          </div>` : ''}
      </section>`;
  }

  function tile(label, value, hint, icon) {
    return `
      <div class="stat-tile">
        <div class="stat-tile__top">${esc(label)} <span class="stat-tile__icon"><i class="fas ${icon}" aria-hidden="true"></i></span></div>
        <div class="stat-tile__value stat-tile__value--text">${value}</div>
        <div class="stat-tile__hint">${hint}</div>
      </div>`;
  }

  // "What this plan is based on". Unknown values say "Not recorded": the
  // plan never assumes a reading it does not have.
  function basisHtml(m) {
    const bmi = typeof m.bmi === 'number'
      ? [`${m.bmi.toFixed(1)}`, m.bmi > 25 ? 'Above the healthy range' : m.bmi < 18.5 ? 'Below the healthy range' : 'Healthy range']
      : ['Not recorded', '<a href="health-profile.html">Add height and weight</a>'];
    const heart = typeof m.heart_risk === 'number'
      ? [`${Math.round(m.heart_risk * 100)}%`, m.heart_risk_elevated ? 'Higher risk indicator' : 'Lower risk indicator']
      : ['Not assessed', '<a href="prediction-heart.html">Take the heart assessment</a>'];
    const glucose = typeof m.fasting_glucose === 'number'
      ? [`${m.fasting_glucose} mg/dL`, m.fasting_glucose >= 100 ? 'Above the usual fasting range' : 'Within the usual fasting range']
      : typeof m.two_hour_glucose === 'number'
        ? [`${m.two_hour_glucose} mg/dL`, m.two_hour_glucose >= 140 ? '2-hour test: above the usual range' : '2-hour test: within the usual range']
        : ['Not recorded', 'From a lab report or the diabetes assessment'];
    const flags = [
      m.high_bp ? 'Raised blood pressure on record' : '',
      m.high_cholesterol ? 'High cholesterol on record' : '',
      m.diabetes_risk_elevated ? 'Higher diabetes risk indicator' : '',
      m.liver_risk_elevated ? 'Higher liver risk indicator' : ''
    ].filter(Boolean);
    const other = flags.length ? [`${flags.length} to consider`, esc(flags.join(', '))] : ['None flagged', 'From your assessments and profile'];

    return `
      <section aria-labelledby="basisTitle" style="margin-bottom: var(--sp-8);">
        <h2 id="basisTitle" style="font-size: var(--text-lg); margin: 0 0 var(--sp-4);">Health details used</h2>
        <div class="stat-grid" style="margin-bottom:0;">
          ${tile('Body mass index', bmi[0], bmi[1], 'fa-weight-scale')}
          ${tile('Heart risk score', heart[0], heart[1], 'fa-heart-pulse')}
          ${tile('Blood sugar', glucose[0], glucose[1], 'fa-droplet')}
          ${tile('Other health flags', other[0], other[1], 'fa-clipboard-check')}
        </div>
      </section>`;
  }

  const ASSESSMENT_ICONS = { diabetes: 'fa-droplet', heart: 'fa-heart-pulse', liver: 'fa-flask' };
  const ASSESSMENT_PAGES = {
    diabetes: 'prediction-diabetes-choose.html',
    heart: 'prediction-heart.html',
    liver: 'prediction-liver-choose.html'
  };

  // The latest result of each diabetes, heart and liver assessment, and
  // what each one changed in the plan.
  function assessmentsHtml(items) {
    if (!items || !items.length) return '';
    const taken = new Set(items.map((a) => a.assessment));
    const notTaken = Object.keys(ASSESSMENT_PAGES).filter((k) => !taken.has(k));
    const rows = items.map((a) => `
      <li class="row-item">
        <span class="row-item__icon ${a.is_elevated ? 'row-item__icon--violet' : 'row-item__icon--teal'}"><i class="fas ${ASSESSMENT_ICONS[a.assessment] || 'fa-clipboard-check'}" aria-hidden="true"></i></span>
        <div class="row-item__main">
          <div class="row-item__title">${esc(a.label)}</div>
          <div class="row-item__meta">${a.assessed_at ? `${esc(AppUI.fmtDate(a.assessed_at))} &middot; ` : ''}${esc(a.plan_effect)}</div>
        </div>
        <div class="row-item__aside"><span class="pill ${a.is_elevated ? 'pill--warn' : 'pill--ok'}">${a.is_elevated ? 'Higher risk indicator' : 'Lower risk indicator'}</span></div>
      </li>`).join('');
    const more = notTaken.length
      ? `<div class="panel__body" style="border-top: 1px solid var(--border-light);"><p class="field__hint" style="margin:0;">Not taken yet: ${notTaken.map((k) => `<a href="${ASSESSMENT_PAGES[k]}">${esc(k.charAt(0).toUpperCase() + k.slice(1))} assessment</a>`).join(', ')}. Taking it lets your plan reflect that result too.</p></div>`
      : '';
    return `
      <section class="panel" aria-labelledby="assessUsedTitle" style="margin-bottom: var(--sp-8);">
        <div class="panel__head">
          <h2 class="panel__title" id="assessUsedTitle" style="font-size: var(--text-lg);">Your health check results</h2>
          <a class="panel__link" href="predictions.html#history">All results</a>
        </div>
        <div class="panel__body" style="padding-bottom:0;"><p class="field__hint" style="margin:0;">Your plan uses the latest result of each assessment you have taken for yourself. Results saved for family members are not used.</p></div>
        <ul class="rows" style="margin-top: var(--sp-2);">${rows}</ul>
        ${more}
      </section>`;
  }

  function nudgeHtml(missing) {
    if (!missing || !missing.length) return '';
    const parts = [];
    if (missing.includes('height_weight')) parts.push('Add your <a href="health-profile.html">height and weight</a> for portion advice that fits your body.');
    if (missing.includes('risk_assessment')) parts.push('Take a <a href="predictions.html">risk assessment</a> so the plan can reflect your risk indicators.');
    if (!parts.length) return '';
    return `
      <div class="notice" style="margin-bottom: var(--sp-6);">
        <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i>
        <span><strong>Make this plan more personal.</strong> ${parts.join(' ')}</span>
      </div>`;
  }

  function eatingHtml(data) {
    const cards = (data.recommendations || []).map((rec) => `
      <section class="panel">
        <div class="panel__head">
          <div>
            <span class="pill pill--plain" style="margin-bottom:6px;">${esc(rec.category)}</span>
            <h3 class="panel__title" style="font-size: var(--text-lg);">${esc(rec.diet)}</h3>
          </div>
        </div>
        <div class="panel__body">
          <p style="margin:0 0 var(--sp-4); color: var(--text-secondary);"><strong>Why this is suggested:</strong> ${esc(rec.reason)}</p>
          <ul class="plain-list">${(rec.rules || []).map((r) => `<li>${esc(r)}</li>`).join('')}</ul>
        </div>
      </section>`).join('');

    const notes = (data.preference_notes || []).map((n) => `
      <div class="notice notice--ok" style="margin-top: var(--sp-4);"><i class="fas fa-utensils" aria-hidden="true"></i><span>${esc(n)}</span></div>`).join('');

    return `
      <section aria-labelledby="eatingTitle" style="margin-bottom: var(--sp-8);">
        <h2 id="eatingTitle" style="font-size: var(--text-lg); margin: 0 0 var(--sp-4);">Eating guidance</h2>
        <div class="stack">${cards}</div>
        ${notes}
      </section>`;
  }

  function exerciseHtml(plan) {
    if (!plan) return '';
    const rows = plan.sessions.map((s) => {
      const [label, tone] = INTENSITY[s.intensity] || [s.intensity, ''];
      return `
        <li class="row-item">
          <span class="row-item__icon ${s.intensity === 'rest' ? '' : 'row-item__icon--teal'}" style="font-size:0.75rem; font-weight:700;">${esc(s.day.slice(0, 3))}</span>
          <div class="row-item__main">
            <div class="row-item__title">${esc(s.activity)}</div>
            <div class="row-item__meta">${esc(s.day)}${s.duration_minutes ? ` &middot; ${s.duration_minutes} minutes` : ''}</div>
          </div>
          <div class="row-item__aside"><span class="pill ${tone}">${esc(label)}</span></div>
        </li>`;
    }).join('');
    const totalMinutes = plan.sessions.reduce((sum, s) => sum + (s.duration_minutes || 0), 0);

    return `
      <section class="panel" aria-labelledby="exerciseTitle" style="margin-bottom: var(--sp-8);">
        <div class="panel__head">
          <h2 class="panel__title" id="exerciseTitle" style="font-size: var(--text-lg);">Your week of activity</h2>
          <span class="pill pill--plain">${esc(plan.level)} &middot; ${totalMinutes} min this week</span>
        </div>
        <div class="panel__body" style="padding-bottom:0;">
          <p style="margin:0; color: var(--text-secondary);">${esc(plan.weekly_target)}</p>
          ${plan.timing_tip ? `<p class="field__hint" style="margin: var(--sp-2) 0 0;"><i class="fas fa-clock" aria-hidden="true"></i> ${esc(plan.timing_tip)}</p>` : ''}
        </div>
        <ul class="rows" style="margin-top: var(--sp-4);">${rows}</ul>
        ${plan.cautions && plan.cautions.length ? `
          <div class="panel__body" style="border-top: 1px solid var(--border-light);">
            <h3 style="font-size: var(--text-sm); margin: 0 0 var(--sp-3);">Stay safe</h3>
            <ul class="plain-list">${plan.cautions.map((c) => `<li>${esc(c)}</li>`).join('')}</ul>
          </div>` : ''}
      </section>`;
  }

  function tipsPanel(id, title, items) {
    if (!items || !items.length) return '';
    return `
      <section class="panel" aria-labelledby="${id}" style="margin-bottom: var(--sp-8);">
        <div class="panel__head"><h2 class="panel__title" id="${id}" style="font-size: var(--text-lg);">${esc(title)}</h2></div>
        <div class="panel__body"><ul class="plain-list">${items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul></div>
      </section>`;
  }

  function medicationHtml(guidance) {
    const meds = (guidance && guidance.medications) || [];
    const body = meds.length
      ? `
        <ul class="rows">${meds.map((m) => `
          <li class="row-item">
            <span class="row-item__icon row-item__icon--violet"><i class="fas fa-pills" aria-hidden="true"></i></span>
            <div class="row-item__main">
              <div class="row-item__title">${esc(m.name)}${m.dosage ? ` <span style="font-weight:500; color:var(--text-secondary);">&middot; ${esc(m.dosage)}</span>` : ''}</div>
              <div class="row-item__meta">${esc(m.frequency || '')}${m.instructions ? ` &middot; ${esc(m.instructions)}` : ''}${m.member_name ? ` &middot; ${esc(m.member_name)}` : ''}</div>
            </div>
          </li>`).join('')}</ul>
        <div class="panel__body" style="border-top: 1px solid var(--border-light);">
          <h3 style="font-size: var(--text-sm); margin: 0 0 var(--sp-3);">Taking your medicines safely</h3>
          <ul class="plain-list">${guidance.tips.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>
        </div>`
      : AppUI.state({
          icon: 'fa-pills',
          title: 'No current medications recorded',
          text: 'Add the medicines you take to see them here alongside safe-use tips.',
          actionHtml: '<a class="btn btn-outline btn-compact" href="medications.html">Add medications</a>'
        });

    return `
      <section class="panel" id="medication" aria-labelledby="medicationTitle" style="margin-bottom: var(--sp-8);">
        <div class="panel__head">
          <h2 class="panel__title" id="medicationTitle" style="font-size: var(--text-lg);">Medication guidance</h2>
          ${meds.length ? '<a class="panel__link" href="medications.html">Manage list</a>' : ''}
        </div>
        ${body}
      </section>`;
  }

  function renderPlan(data) {
    const routineTitle = data.meal_plan.plan_for.occupation
      ? `Tips for your routine: ${data.meal_plan.plan_for.occupation}`
      : 'Tips for your routine';
    root.innerHTML = `
      ${planForHtml(data.meal_plan.plan_for)}
      ${nudgeHtml(data.missing_inputs)}
      ${assessmentsHtml(data.assessments_used)}
      ${basisHtml(data.metrics_evaluated || {})}
      ${mealsHtml(data.meal_plan)}
      ${eatingHtml(data)}
      ${exerciseHtml(data.exercise_plan)}
      ${tipsPanel('routineTitle', routineTitle, data.routine_tips)}
      ${tipsPanel('habitsTitle', 'Daily habits', data.lifestyle_guidance)}
      ${medicationHtml(data.medication_guidance)}
      <div class="notice notice--warn"><i class="fas fa-circle-info" aria-hidden="true"></i><span>${esc(data.disclaimer)}</span></div>`;

    document.getElementById('editAnswers').addEventListener('click', async () => {
      try {
        startQuiz(quiz.profile || await SwasthAPI.healthProfile.get());
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (err) {
        AppUI.toast(AppUI.errorText(err), 'error');
      }
    });

    // Arriving from a link such as medications.html -> #medication.
    if (window.location.hash) {
      document.querySelector(window.location.hash)?.scrollIntoView({ block: 'start' });
    }
  }

  async function loadPlan() {
    root.innerHTML = `<div class="panel">${AppUI.skeletonRows(4)}</div>`;
    try {
      const [profile, plan] = await Promise.all([
        SwasthAPI.healthProfile.get(),
        SwasthAPI.diet.recommendations()
      ]);
      quiz.profile = profile;
      if (!hasCoreAnswers(profile)) {
        startQuiz(profile);
        return;
      }
      renderPlan(plan);
    } catch (err) {
      root.innerHTML = `<div class="panel">${AppUI.errorState(AppUI.errorText(err), 'dietRetry')}</div>`;
      document.getElementById('dietRetry')?.addEventListener('click', loadPlan);
    }
  }

  loadPlan();
})();
