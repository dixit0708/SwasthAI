/**
 * SwasthAI — AI Health Assistant Client (Module 2).
 * Interacts with POST /api/v1/assistant/chat using authenticated session token.
 */

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendChatBtn');
    const chatMessages = document.getElementById('chatMessages');
    const contextMetricsList = document.getElementById('contextMetricsList');
    const quickPrompts = document.querySelectorAll('.quick-prompt');

    // 1. Fetch and display user's contextual metrics
    async function loadUserContext() {
        if (!contextMetricsList) return;
        const token = typeof swasthaiGetToken === 'function' ? swasthaiGetToken() : null;
        if (!token) return;

        try {
            const res = await fetch(`${SWASTHAI_API_BASE}/diet/recommendations`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                renderContext(data.metrics_evaluated);
            } else {
                contextMetricsList.innerHTML = `
                    <div style="background: var(--bg-surface-alt); padding: 0.75rem; border-radius: var(--radius-sm); font-size: var(--text-xs); color: var(--text-secondary);">
                        <i class="fas fa-info-circle text-primary"></i> Complete health assessments to enrich AI context.
                    </div>
                `;
            }
        } catch (e) {
            console.error('Failed to load health context:', e);
        }
    }

    function renderContext(metrics) {
        if (!metrics) return;
        const bmiText = metrics.bmi ? `${metrics.bmi} (Overweight)` : (metrics.bmi ? `${metrics.bmi}` : 'Not recorded');
        const heartText = metrics.heart_risk !== null && metrics.heart_risk !== undefined 
            ? `${Math.round(metrics.heart_risk * 100)}%` 
            : 'Not evaluated';
        const bpText = metrics.high_bp ? 'Elevated / High' : 'Normal / Not flagged';
        const glucoseText = metrics.fasting_glucose ? `${metrics.fasting_glucose} mg/dL` : 'Not recorded';
        const conds = (metrics.conditions && metrics.conditions.length) ? metrics.conditions.join(', ') : 'None listed';

        contextMetricsList.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr; gap: 0.5rem; font-size: var(--text-xs);">
                <div style="background: var(--bg-surface-alt); padding: 0.6rem 0.8rem; border-radius: var(--radius-sm); border-left: 3px solid var(--primary);">
                    <strong>BMI:</strong> ${bmiText}
                </div>
                <div style="background: var(--bg-surface-alt); padding: 0.6rem 0.8rem; border-radius: var(--radius-sm); border-left: 3px solid #e11d48;">
                    <strong>Heart Risk:</strong> ${heartText}
                </div>
                <div style="background: var(--bg-surface-alt); padding: 0.6rem 0.8rem; border-radius: var(--radius-sm); border-left: 3px solid #f59e0b;">
                    <strong>Blood Pressure:</strong> ${bpText}
                </div>
                <div style="background: var(--bg-surface-alt); padding: 0.6rem 0.8rem; border-radius: var(--radius-sm); border-left: 3px solid #10b981;">
                    <strong>Fasting Glucose:</strong> ${glucoseText}
                </div>
                <div style="background: var(--bg-surface-alt); padding: 0.6rem 0.8rem; border-radius: var(--radius-sm); border-left: 3px solid #6366f1;">
                    <strong>Conditions:</strong> ${conds}
                </div>
            </div>
        `;
    }

    // 2. Chat Bubble Helpers
    function appendMessage(sender, text, disclaimer = null) {
        const bubble = document.createElement('div');
        bubble.style.maxWidth = '85%';
        bubble.style.padding = '0.9rem 1.25rem';
        bubble.style.borderRadius = '1rem';
        bubble.style.fontSize = '0.95rem';
        bubble.style.lineHeight = '1.5';
        bubble.style.boxShadow = 'var(--shadow-sm)';

        if (sender === 'user') {
            bubble.style.alignSelf = 'flex-end';
            bubble.style.background = 'var(--primary)';
            bubble.style.color = 'white';
            bubble.style.borderBottomRightRadius = '0';
            bubble.textContent = text;
        } else {
            bubble.style.alignSelf = 'flex-start';
            bubble.style.background = 'white';
            bubble.style.color = 'var(--text-primary)';
            bubble.style.borderBottomLeftRadius = '0';
            bubble.style.border = '1px solid var(--border)';
            
            let html = `<div>${text.replace(/\n/g, '<br>')}</div>`;
            if (disclaimer) {
                html += `<div style="margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed var(--border); font-size: 0.75rem; color: var(--text-muted);"><i class="fas fa-shield-halved text-primary"></i> ${disclaimer}</div>`;
            }
            bubble.innerHTML = html;
        }

        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function appendLoadingBubble() {
        const loading = document.createElement('div');
        loading.id = 'aiThinkingBubble';
        loading.style.alignSelf = 'flex-start';
        loading.style.background = 'white';
        loading.style.padding = '0.75rem 1.25rem';
        loading.style.borderRadius = '1rem 1rem 1rem 0';
        loading.style.border = '1px solid var(--border)';
        loading.style.fontSize = '0.85rem';
        loading.style.color = 'var(--text-secondary)';
        loading.innerHTML = '<i class="fas fa-spinner fa-spin text-primary"></i> SwasthAI is thinking...';
        chatMessages.appendChild(loading);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return loading;
    }

    // 3. Submit Message Handler
    async function sendMessage(messageText) {
        const text = (messageText || (chatInput && chatInput.value) || '').trim();
        if (!text) return;

        appendMessage('user', text);
        if (chatInput) chatInput.value = '';
        if (sendBtn) sendBtn.disabled = true;

        const loadingBubble = appendLoadingBubble();
        const token = typeof swasthaiGetToken === 'function' ? swasthaiGetToken() : null;

        try {
            const res = await fetch(`${SWASTHAI_API_BASE}/assistant/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ message: text })
            });

            if (loadingBubble && loadingBubble.parentNode) {
                loadingBubble.parentNode.removeChild(loadingBubble);
            }

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                appendMessage('assistant', `I encountered an issue processing your request: ${errData.detail || 'Service unavailable'}. Please try again.`);
            } else {
                const data = await res.json();
                appendMessage('assistant', data.response, data.disclaimer);
            }
        } catch (e) {
            if (loadingBubble && loadingBubble.parentNode) {
                loadingBubble.parentNode.removeChild(loadingBubble);
            }
            appendMessage('assistant', 'Unable to reach the assistant service. Please check your connection and ensure the backend is running.');
            console.error('Chat error:', e);
        } finally {
            if (sendBtn) sendBtn.disabled = false;
            if (chatInput) chatInput.focus();
        }
    }

    // Expose handleSend alias for programmatic and external invocation
    window.handleSend = sendMessage;

    if (chatForm) {
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            sendMessage();
        });
    }

    // Quick prompts
    quickPrompts.forEach(chip => {
        chip.addEventListener('click', () => {
            const promptText = chip.textContent.trim();
            sendMessage(promptText);
        });
    });

    loadUserContext();
});