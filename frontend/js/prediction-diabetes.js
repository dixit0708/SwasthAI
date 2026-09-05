/**
 * SwasthAI — Diabetes Risk Assessment page.
 * Submits the form to the real backend model and renders its
 * non-diagnostic risk response.
 */

const DIABETES_RISK_STYLES = {
  low: { textClass: 'text-success', label: 'Low Risk' },
  moderate: { textClass: 'text-warning', label: 'Moderate Risk' },
  elevated: { textClass: 'text-danger', label: 'Elevated Risk' }
};

// The trained model needs a "Diabetes Pedigree Function" score, a technical
// value nobody outside a research paper has heard of. Rather than ask for
// it directly, we ask a plain-language family-history question and map the
// answer to an approximate value in the same range the model was trained
// on (~0.08-2.42, median ~0.37) — this is a reasonable approximation for a
// simplified UI, not a precise clinical formula.
const FAMILY_HISTORY_TO_PEDIGREE = {
  none: 0.15,
  one: 0.5,
  multiple: 1.0,
  unsure: 0.37
};

function calculateBmi(heightCm, weightKg) {
  const heightM = heightCm / 100;
  return weightKg / (heightM * heightM);
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('diabetesForm');
  if (!form) return;

  const alertBox = document.getElementById('diabetesFormAlert');
  const alertText = document.getElementById('diabetesFormAlertText');
  const submitBtn = document.getElementById('diabetesSubmitBtn');
  const resultCard = document.getElementById('resultCard');

  function showError(message) {
    alertText.textContent = message;
    alertBox.style.display = 'flex';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    alertBox.style.display = 'none';
    resultCard.style.display = 'none';

    const heightCm = Number(document.getElementById('dbHeight').value);
    const weightKg = Number(document.getElementById('dbWeight').value);
    const familyHistory = document.getElementById('dbFamilyHistory').value;

    const payload = {
      age: Number(document.getElementById('dbAge').value),
      pregnancies: Number(document.getElementById('dbPregnancies').value),
      bmi: Math.round(calculateBmi(heightCm, weightKg) * 10) / 10,
      glucose: Number(document.getElementById('dbGlucose').value),
      blood_pressure: Number(document.getElementById('dbBloodPressure').value),
      skin_thickness: Number(document.getElementById('dbSkinThickness').value),
      insulin: Number(document.getElementById('dbInsulin').value),
      diabetes_pedigree_function: FAMILY_HISTORY_TO_PEDIGREE[familyHistory] ?? FAMILY_HISTORY_TO_PEDIGREE.unsure
    };

    submitBtn.disabled = true;
    submitBtn.textContent = 'Running AI Model...';
    try {
      const result = await SwasthAPI.predictions.diabetes(payload);
      const style = DIABETES_RISK_STYLES[result.risk_level] || DIABETES_RISK_STYLES.moderate;

      document.getElementById('resultRiskLevel').className = style.textClass;
      document.getElementById('resultRiskLevel').textContent =
        `${style.label} (${Math.round(result.risk_probability * 100)}%)`;
      document.getElementById('resultMessage').textContent = result.message;
      document.getElementById('resultDisclaimer').textContent = result.disclaimer;
      resultCard.style.display = 'block';
    } catch (err) {
      if (err.status === 503) {
        showError('The diabetes risk model is not available right now. Please try again later.');
      } else {
        showError(err.message);
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Run AI Model';
    }
  });
});
