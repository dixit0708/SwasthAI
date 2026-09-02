/**
 * SwasthAI — Health Insights sample charts.
 * Neutral, illustrative sample data only (not real medical data).
 */
document.addEventListener('DOMContentLoaded', () => {
  if (typeof Chart === 'undefined') return;

  const style = getComputedStyle(document.documentElement);
  const primary = style.getPropertyValue('--primary').trim() || '#0F766E';
  const info = style.getPropertyValue('--info').trim() || '#0284C7';
  const warning = style.getPropertyValue('--warning').trim() || '#D97706';
  const danger = style.getPropertyValue('--danger').trim() || '#DC2626';
  const muted = style.getPropertyValue('--text-muted').trim() || '#64748B';
  const border = style.getPropertyValue('--border').trim() || '#E2E8F0';

  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.color = muted;
  Chart.defaults.borderColor = border;

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const weeks = ['Wk 1', 'Wk 2', 'Wk 3', 'Wk 4', 'Wk 5', 'Wk 6', 'Wk 7', 'Wk 8'];

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false } },
      y: { grid: { color: border }, beginAtZero: false }
    }
  };

  function lineChart(id, data, color, opts = {}) {
    const el = document.getElementById(id);
    if (!el) return;
    new Chart(el, {
      type: 'line',
      data: {
        labels: opts.labels || days,
        datasets: [{
          data,
          borderColor: color,
          backgroundColor: color + '22',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: color
        }]
      },
      options: { ...baseOptions, ...(opts.options || {}) }
    });
  }

  function barChart(id, data, color, opts = {}) {
    const el = document.getElementById(id);
    if (!el) return;
    new Chart(el, {
      type: 'bar',
      data: {
        labels: opts.labels || days,
        datasets: [{
          data,
          backgroundColor: color,
          borderRadius: 6,
          maxBarThickness: 28
        }]
      },
      options: { ...baseOptions, ...(opts.options || {}) }
    });
  }

  // Heart Rate (bpm, resting, 7 days)
  lineChart('chartHeartRate', [74, 72, 75, 71, 70, 73, 71], danger);

  // Weight (kg, 8 weeks)
  lineChart('chartWeight', [78.4, 78.1, 77.9, 77.6, 77.8, 77.3, 77.0, 76.6], info, { labels: weeks });

  // Blood Pressure (systolic / diastolic, 7 days)
  const bpEl = document.getElementById('chartBloodPressure');
  if (bpEl) {
    new Chart(bpEl, {
      type: 'line',
      data: {
        labels: days,
        datasets: [
          { label: 'Systolic', data: [128, 126, 130, 124, 122, 125, 123], borderColor: warning, backgroundColor: 'transparent', tension: 0.4, pointRadius: 3 },
          { label: 'Diastolic', data: [84, 82, 85, 80, 79, 81, 80], borderColor: primary, backgroundColor: 'transparent', tension: 0.4, pointRadius: 3 }
        ]
      },
      options: {
        ...baseOptions,
        plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } }
      }
    });
  }

  // Blood Glucose (mg/dL, 7 days)
  lineChart('chartGlucose', [108, 112, 105, 118, 110, 104, 107], '#7C3AED');

  // Sleep (hours, 7 days)
  barChart('chartSleep', [6.2, 5.8, 7.1, 6.5, 5.9, 7.4, 7.8], primary);

  // Activity (steps in thousands, 7 days)
  barChart('chartActivity', [6.4, 8.2, 5.1, 9.0, 7.3, 10.2, 4.8], info);
});
