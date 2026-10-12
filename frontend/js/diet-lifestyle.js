/**
 * SwasthAI — Diet & Lifestyle Guidance Client (Module 3).
 * Interacts with GET /api/v1/diet/recommendations using authenticated session token.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const metricBmi = document.getElementById('metricBmi');
    const metricHeartRisk = document.getElementById('metricHeartRisk');
    const metricHighBp = document.getElementById('metricHighBp');
    const metricGlucose = document.getElementById('metricGlucose');
    const dietProtocolsTags = document.getElementById('dietProtocolsTags');
    const recommendationsList = document.getElementById('recommendationsList');
    const lifestyleCard = document.getElementById('lifestyleCard');
    const lifestyleList = document.getElementById('lifestyleList');
    const dietDisclaimerText = document.getElementById('dietDisclaimerText');

    const token = typeof swasthaiGetToken === 'function' ? swasthaiGetToken() : null;
    if (!token) return;

    try {
        const res = await fetch(`${SWASTHAI_API_BASE}/diet/recommendations`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) {
            recommendationsList.innerHTML = `
                <div class="card" style="padding: 2rem; text-align: center; color: var(--danger);">
                    <i class="fas fa-triangle-exclamation fa-2x" style="margin-bottom: 0.5rem;"></i>
                    <p>Failed to load dietary recommendations. Please try again later.</p>
                </div>
            `;
            return;
        }

        const data = await res.json();

        // 1. Render Metrics
        const m = data.metrics_evaluated || {};
        if (metricBmi) {
            metricBmi.textContent = m.bmi ? `${m.bmi} kg/m²` : 'Not recorded';
            if (m.bmi > 25.0) metricBmi.style.color = '#e11d48';
        }
        if (metricHeartRisk) {
            metricHeartRisk.textContent = (m.heart_risk !== null && m.heart_risk !== undefined)
                ? `${Math.round(m.heart_risk * 100)}%`
                : 'Not evaluated';
            if (m.heart_risk > 0.50) metricHeartRisk.style.color = '#e11d48';
        }
        if (metricHighBp) {
            metricHighBp.textContent = m.high_bp ? 'Elevated / High' : 'Normal / Low';
            if (m.high_bp) metricHighBp.style.color = '#e11d48';
        }
        if (metricGlucose) {
            metricGlucose.textContent = m.fasting_glucose ? `${m.fasting_glucose} mg/dL` : 'Not recorded';
            if (m.fasting_glucose >= 100.0) metricGlucose.style.color = '#e11d48';
        }

        // 2. Render Diet Protocol Badges
        if (dietProtocolsTags) {
            dietProtocolsTags.innerHTML = '';
            (data.diet_types || []).forEach(type => {
                const badge = document.createElement('span');
                badge.className = 'badge badge-primary';
                badge.style.padding = '0.5rem 1rem';
                badge.style.fontSize = '0.85rem';
                badge.style.borderRadius = '2rem';
                badge.innerHTML = `<i class="fas fa-check-circle"></i> ${type}`;
                dietProtocolsTags.appendChild(badge);
            });
        }

        // 3. Render Recommendations
        if (recommendationsList) {
            recommendationsList.innerHTML = '';
            (data.recommendations || []).forEach(rec => {
                const card = document.createElement('div');
                card.className = 'card';
                card.style.background = 'white';
                card.style.border = '1px solid var(--border)';
                card.style.boxShadow = 'var(--shadow-sm)';
                card.style.borderRadius = 'var(--radius-md)';

                const rulesHtml = (rec.rules || []).map(r => `
                    <li style="margin-bottom: 0.5rem; line-height: 1.5;">
                        <i class="fas fa-arrow-right text-primary" style="font-size: 0.75rem; margin-right: 0.5rem;"></i>
                        ${r}
                    </li>
                `).join('');

                card.innerHTML = `
                    <div class="card-header flex" style="justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding: 1rem 1.25rem;">
                        <div>
                            <span class="badge badge-primary" style="font-size: 0.75rem; margin-bottom: 0.25rem;">${rec.category}</span>
                            <h3 style="margin: 0.25rem 0 0 0; font-size: 1.2rem; color: var(--text-primary);">${rec.diet}</h3>
                        </div>
                    </div>
                    <div class="card-body" style="padding: 1.25rem;">
                        <div style="background: var(--bg-surface-alt); padding: 0.75rem 1rem; border-radius: var(--radius-sm); margin-bottom: 1rem; font-size: var(--text-sm); color: var(--text-secondary);">
                            <strong><i class="fas fa-circle-exclamation text-primary"></i> Clinical Rationale:</strong> ${rec.reason}
                        </div>
                        <h4 style="font-size: 0.95rem; margin: 0 0 0.75rem 0; color: var(--text-primary);">Actionable Dietary Rules:</h4>
                        <ul style="list-style: none; padding-left: 0; margin: 0;">
                            ${rulesHtml}
                        </ul>
                    </div>
                `;
                recommendationsList.appendChild(card);
            });
        }

        // 4. Render Lifestyle Guidance
        if (lifestyleCard && lifestyleList && data.lifestyle_guidance && data.lifestyle_guidance.length) {
            lifestyleCard.style.display = 'block';
            lifestyleList.innerHTML = data.lifestyle_guidance.map(item => `
                <li style="margin-bottom: 0.4rem; line-height: 1.5;">${item}</li>
            `).join('');
        }

        // 5. Update Disclaimer
        if (dietDisclaimerText && data.disclaimer) {
            dietDisclaimerText.textContent = data.disclaimer;
        }

    } catch (e) {
        console.error('Error fetching diet guidance:', e);
        if (recommendationsList) {
            recommendationsList.innerHTML = `
                <div class="card" style="padding: 2rem; text-align: center; color: var(--danger);">
                    <p>Failed to connect to the SwasthAI API. Please verify the backend server is running.</p>
                </div>
            `;
        }
    }
});