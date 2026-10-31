/**
 * SwasthAI — Family Records Module
 * Manages family members, medical history, health records, document uploads,
 * prescriptions, vitals progress tracking with Chart.js, and health timeline.
 */

(function () {
    'use strict';

    // State
    let allMembers = [];
    let currentMemberId = null;
    let currentMember = null;
    let memberRecords = [];
    let memberMeds = [];
    let memberVitals = [];
    let activeVitalsMetric = 'blood_pressure';
    let vitalsChartInstance = null;
    let activeDeleteHandler = null;
    let selectedRecordFile = null;

    // DOM Elements
    const overviewView = document.getElementById('familyOverviewView');
    const profileView = document.getElementById('memberProfileView');
    const globalAlert = document.getElementById('familyGlobalAlert');
    const globalAlertMsg = document.getElementById('familyGlobalAlertMsg');

    // Overview Elements
    const statTotalMembers = document.getElementById('statTotalMembers');
    const statMembersWithRecords = document.getElementById('statMembersWithRecords');
    const statTotalRecords = document.getElementById('statTotalRecords');
    const statActiveMeds = document.getElementById('statActiveMeds');
    const membersGrid = document.getElementById('familyMembersGrid');
    const emptyState = document.getElementById('familyEmptyState');
    const membersCountBadge = document.getElementById('membersCountBadge');
    const recentRecordsSection = document.getElementById('recentRecordsSection');
    const recentRecordsGrid = document.getElementById('overviewRecentRecordsGrid');

    // Profile Elements
    const profileHeaderAvatar = document.getElementById('profileHeaderAvatar');
    const profileHeaderName = document.getElementById('profileHeaderName');
    const profileHeaderRelation = document.getElementById('profileHeaderRelation');
    const profileHeaderBlood = document.getElementById('profileHeaderBlood');
    const profileHeaderAge = document.getElementById('profileHeaderAge');
    const profileHeaderDob = document.getElementById('profileHeaderDob');
    const profileHeaderDobSpan = document.getElementById('profileHeaderDobSpan');
    const profileHeaderGender = document.getElementById('profileHeaderGender');
    const profileHeaderGenderSpan = document.getElementById('profileHeaderGenderSpan');
    const profileHeaderPhone = document.getElementById('profileHeaderPhone');
    const profileHeaderPhoneSpan = document.getElementById('profileHeaderPhoneSpan');
    const profileBreadcrumbName = document.getElementById('profileBreadcrumbName');

    // Profile Tab Counts
    const countProfileHistory = document.getElementById('countProfileHistory');
    const countProfileRecords = document.getElementById('countProfileRecords');
    const countProfileMeds = document.getElementById('countProfileMeds');

    // Profile Tab Containers
    const profileHistoryContainer = document.getElementById('profileHistoryContainer');
    const historyEmptyState = document.getElementById('historyEmptyState');
    const profileRecordsContainer = document.getElementById('profileRecordsContainer');
    const recordsEmptyState = document.getElementById('recordsEmptyState');
    const profileMedsContainer = document.getElementById('profileMedsContainer');
    const medsEmptyState = document.getElementById('medsEmptyState');
    const vitalsLogTableBody = document.getElementById('vitalsLogTableBody');
    const profileTimelineContainer = document.getElementById('profileTimelineContainer');
    const timelineEmptyState = document.getElementById('timelineEmptyState');

    // ==========================================================================
    // UTILITY & NOTIFICATION FUNCTIONS
    // ==========================================================================

    function showAlert(msg, isError = false) {
        if (!globalAlert || !globalAlertMsg) return;
        globalAlertMsg.textContent = msg;
        globalAlert.className = `alert mb-4 ${isError ? 'alert-danger' : 'alert-success'}`;
        globalAlert.hidden = false;
        window.scrollTo({ top: 0, behavior: 'smooth' });
        setTimeout(() => {
            if (globalAlert) globalAlert.hidden = true;
        }, 5000);
    }

    function formatDisplayDate(dateStr) {
        if (!dateStr) return '--';
        try {
            const parts = dateStr.split('-');
            if (parts.length === 3) {
                const d = new Date(parts[0], parts[1] - 1, parts[2]);
                return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            }
            return dateStr;
        } catch (e) {
            return dateStr;
        }
    }

    function getInitials(name) {
        if (!name) return 'F';
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return name.slice(0, 2).toUpperCase();
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ==========================================================================
    // MODAL DIALOG CONTROLS
    // ==========================================================================

    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
            document.documentElement.style.overflow = 'hidden';
            if (window.lenis && typeof window.lenis.stop === 'function') {
                window.lenis.stop();
            }
            const firstInput = modal.querySelector('input:not([type="hidden"]), select, textarea');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 80);
            }
        }
    }

    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('open');
            clearModalErrors(modal);
            const anyOpen = document.querySelector('.modal-overlay.open');
            if (!anyOpen) {
                document.body.style.overflow = '';
                document.documentElement.style.overflow = '';
                if (window.lenis && typeof window.lenis.start === 'function') {
                    window.lenis.start();
                }
            }
        }
    }

    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const overlay = e.target.closest('.modal-overlay');
            if (overlay) closeModal(overlay.id);
        });
    });

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal(overlay.id);
        });
    });

    // ==========================================================================
    // FORM VALIDATION SYSTEM
    // ==========================================================================

    const ALLOWED_MIME_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
    const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png'];
    const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15 MB limit

    function setFieldError(fieldId, message) {
        const input = document.getElementById(fieldId);
        const errEl = document.getElementById(`err_${fieldId}`);
        const groupEl = document.getElementById(`group_${fieldId}`) || input?.closest('.form-group');

        if (input) input.classList.add('is-invalid');
        if (groupEl) groupEl.classList.add('has-error');
        if (errEl) {
            const span = errEl.querySelector('span');
            if (span) span.textContent = message;
            else errEl.textContent = message;
            errEl.style.display = 'flex';
        }
    }

    function clearFieldError(fieldId) {
        const input = document.getElementById(fieldId);
        const errEl = document.getElementById(`err_${fieldId}`);
        const groupEl = document.getElementById(`group_${fieldId}`) || input?.closest('.form-group');

        if (input) input.classList.remove('is-invalid');
        if (groupEl) groupEl.classList.remove('has-error');
        if (errEl) {
            errEl.style.display = 'none';
            const span = errEl.querySelector('span');
            if (span) span.textContent = '';
        }
    }

    function setModalAlert(alertId, message) {
        const alertEl = document.getElementById(alertId);
        if (alertEl) {
            alertEl.innerHTML = `<i class="fas fa-exclamation-circle"></i> <span>${escapeHtml(message)}</span>`;
            alertEl.className = 'modal-form-alert alert-danger';
            alertEl.style.display = 'flex';
        }
    }

    function clearModalAlert(alertId) {
        const alertEl = document.getElementById(alertId);
        if (alertEl) {
            alertEl.style.display = 'none';
            alertEl.innerHTML = '';
        }
    }

    function clearModalErrors(modal) {
        if (!modal) return;
        modal.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        modal.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));
        modal.querySelectorAll('.field-error-msg').forEach(el => {
            el.style.display = 'none';
            const span = el.querySelector('span');
            if (span) span.textContent = '';
        });
        modal.querySelectorAll('.modal-form-alert').forEach(el => {
            el.style.display = 'none';
            el.innerHTML = '';
        });
        const fileError = modal.querySelector('#recordFileError');
        if (fileError) fileError.classList.remove('show');
        const dropzone = modal.querySelector('#recordDropzone');
        if (dropzone) dropzone.classList.remove('is-invalid');
    }

    function validateUploadedFile(file) {
        if (!file) return { valid: false, error: 'No document selected' };

        const ext = '.' + file.name.split('.').pop().toLowerCase();
        const isExtensionValid = ALLOWED_EXTENSIONS.includes(ext);
        const isMimeValid = ALLOWED_MIME_TYPES.includes(file.type.toLowerCase()) || isExtensionValid;

        if (!isExtensionValid && !isMimeValid) {
            return {
                valid: false,
                error: `Unsupported file format (${ext}). Only PDF, JPG, and PNG documents are allowed.`
            };
        }

        if (file.size > MAX_FILE_SIZE_BYTES) {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
            return {
                valid: false,
                error: `File size (${sizeMB} MB) exceeds maximum allowed limit of 15 MB.`
            };
        }

        if (file.size === 0) {
            return {
                valid: false,
                error: 'The selected file is empty (0 bytes). Please choose a valid document.'
            };
        }

        return { valid: true };
    }

    function validatePhoneNumber(value, isRequired = false) {
        if (!value || !value.trim()) {
            if (isRequired) return { valid: false, error: 'Contact phone number is required.' };
            return { valid: true };
        }
        const trimmed = value.trim();
        // Disallow invalid characters (letters or special symbols other than +, -, (, ), ., and spaces)
        if (!/^[+]?[\d\s\-().]{7,25}$/.test(trimmed)) {
            return { valid: false, error: 'Phone number contains invalid characters.' };
        }
        const cleanDigits = trimmed.replace(/\D/g, '');
        if (cleanDigits.length < 10) {
            return { valid: false, error: 'Phone number must contain at least 10 digits.' };
        }
        if (cleanDigits.length > 15) {
            return { valid: false, error: 'Phone number cannot exceed 15 digits.' };
        }
        // Reject dummy repeating digits (e.g. 0000000000, 1111111111)
        if (/^(\d)\1+$/.test(cleanDigits)) {
            return { valid: false, error: 'Please enter a valid phone number, not repeating digits.' };
        }
        // Reject sequential test sequences
        if (cleanDigits === '1234567890' || cleanDigits === '0123456789') {
            return { valid: false, error: 'Please enter a realistic phone number.' };
        }
        // Standard 10-digit mobile must start with 6, 7, 8, or 9
        if (cleanDigits.length === 10) {
            if (!/^[6-9]/.test(cleanDigits)) {
                return { valid: false, error: '10-digit mobile number must start with 6, 7, 8, or 9.' };
            }
        } else if (cleanDigits.length === 11 && cleanDigits.startsWith('0')) {
            if (!/^0[6-9]/.test(cleanDigits)) {
                return { valid: false, error: 'Mobile number must start with 6, 7, 8, or 9 after leading 0.' };
            }
        } else if (cleanDigits.length === 12 && cleanDigits.startsWith('91')) {
            if (!/^91[6-9]/.test(cleanDigits)) {
                return { valid: false, error: 'Indian mobile number (+91) must start with 6, 7, 8, or 9.' };
            }
        } else if (trimmed.startsWith('+')) {
            if (!/^\+[1-9]\d{8,14}$/.test(trimmed.replace(/[\s\-().]/g, ''))) {
                return { valid: false, error: 'International number must follow format +[CountryCode][Number].' };
            }
        }
        return { valid: true };
    }

    function validateEmergencyContact(value) {
        if (!value || !value.trim()) return { valid: true };
        const trimmed = value.trim();
        const cleanDigits = trimmed.replace(/\D/g, '');
        if (cleanDigits.length > 0) {
            if (cleanDigits.length < 10) {
                return { valid: false, error: 'Emergency contact phone number must have at least 10 digits.' };
            }
            if (cleanDigits.length > 15) {
                return { valid: false, error: 'Emergency contact phone number cannot exceed 15 digits.' };
            }
            if (/^(\d)\1+$/.test(cleanDigits)) {
                return { valid: false, error: 'Emergency phone number cannot be repeating digits.' };
            }
            if (cleanDigits.length === 10 && !trimmed.includes('+') && !/^[6-9]/.test(cleanDigits)) {
                return { valid: false, error: '10-digit emergency phone number must start with 6, 7, 8, or 9.' };
            }
        }
        return { valid: true };
    }

    function scrollToFirstError(form) {
        const firstInvalid = form.querySelector('.is-invalid, .has-error');
        if (firstInvalid) {
            firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
            const focusable = firstInvalid.matches('input, select, textarea')
                ? firstInvalid
                : firstInvalid.querySelector('input, select, textarea');
            if (focusable) focusable.focus();
        }
    }

    // Confirmation Modal Helper
    function showConfirm(title, message, onConfirm) {
        const titleEl = document.getElementById('confirmModalTitle');
        const msgEl = document.getElementById('confirmModalMessage');
        const btnConfirm = document.getElementById('btnConfirmAction');

        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;

        activeDeleteHandler = async () => {
            try {
                btnConfirm.disabled = true;
                btnConfirm.textContent = 'Deleting...';
                await onConfirm();
                closeModal('confirmModal');
            } catch (err) {
                showAlert(err.message || 'Action failed', true);
            } finally {
                btnConfirm.disabled = false;
                btnConfirm.textContent = 'Delete';
            }
        };

        btnConfirm.onclick = activeDeleteHandler;
        openModal('confirmModal');
    }

    // ==========================================================================
    // ROUTING & VIEW NAVIGATION
    // ==========================================================================

    function showOverview() {
        currentMemberId = null;
        currentMember = null;
        if (overviewView) overviewView.style.display = 'block';
        if (profileView) profileView.classList.remove('active');

        // Update URL
        const url = new URL(window.location);
        url.searchParams.delete('member');
        window.history.pushState({}, '', url);

        loadOverviewData();
    }

    async function showMemberProfile(memberId, defaultTab = 'tab-overview') {
        currentMemberId = memberId;
        if (overviewView) overviewView.style.display = 'none';
        if (profileView) profileView.classList.add('active');

        // Update URL
        const url = new URL(window.location);
        url.searchParams.set('member', memberId);
        window.history.pushState({}, '', url);

        // Switch to default tab
        switchTab(defaultTab);
        await loadMemberProfileData(memberId);
    }

    window.addEventListener('popstate', () => {
        const urlParams = new URLSearchParams(window.location.search);
        const memId = urlParams.get('member');
        if (memId) {
            showMemberProfile(memId);
        } else {
            showOverview();
        }
    });

    document.getElementById('profileBackToOverview')?.addEventListener('click', (e) => {
        e.preventDefault();
        showOverview();
    });

    // Tab Navigation
    function switchTab(tabKey) {
        document.querySelectorAll('.profile-tab-btn').forEach(btn => {
            const isActive = btn.getAttribute('data-tab') === tabKey;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        document.querySelectorAll('.profile-tab-content').forEach(content => {
            content.classList.toggle('active', content.id === tabKey);
        });

        if (tabKey === 'tab-progress' && memberVitals.length > 0) {
            renderVitalsChart();
        }
    }

    document.querySelectorAll('.profile-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabKey = btn.getAttribute('data-tab');
            switchTab(tabKey);
        });
    });

    // ==========================================================================
    // DATA LOADING: FAMILY OVERVIEW
    // ==========================================================================

    async function loadOverviewData() {
        try {
            // Load stats & members in parallel
            const [overview, members] = await Promise.all([
                SwasthAPI.family.getOverview(),
                SwasthAPI.family.listMembers()
            ]);

            allMembers = members || [];

            // Update stats cards
            if (statTotalMembers) statTotalMembers.textContent = overview.total_members || 0;
            if (statMembersWithRecords) statMembersWithRecords.textContent = overview.members_with_records || 0;
            if (statTotalRecords) statTotalRecords.textContent = overview.total_records || 0;
            if (statActiveMeds) statActiveMeds.textContent = overview.total_medications || 0;

            if (membersCountBadge) {
                membersCountBadge.textContent = `${allMembers.length} member${allMembers.length === 1 ? '' : 's'}`;
            }

            renderMembersGrid(allMembers);

            // Populate member select options for direct record creation
            populateMemberDropdowns(allMembers);

            // Recent records
            if (overview.recent_records && overview.recent_records.length > 0) {
                recentRecordsSection.hidden = false;
                renderRecentRecords(overview.recent_records);
            } else {
                recentRecordsSection.hidden = true;
            }

        } catch (err) {
            showAlert('Failed to load family records. ' + err.message, true);
        }
    }

    function renderMembersGrid(members) {
        if (!membersGrid) return;
        membersGrid.innerHTML = '';

        if (!members || members.length === 0) {
            emptyState.hidden = false;
            membersGrid.hidden = true;
            return;
        }

        emptyState.hidden = true;
        membersGrid.hidden = false;

        members.forEach(m => {
            const card = document.createElement('div');
            card.className = 'family-member-card';

            const initials = getInitials(m.name);
            const color = m.avatar_color || '#0F766E';
            const ageDisplay = m.age !== null && m.age !== undefined ? `${m.age} yrs` : 'Age --';
            const bloodDisplay = m.blood_group ? `<span class="member-badge blood"><i class="fas fa-tint"></i> ${escapeHtml(m.blood_group)}</span>` : '';
            const lastRecordDate = m.latest_activity_date ? `Last: ${formatDisplayDate(m.latest_activity_date)}` : 'No records yet';

            card.innerHTML = `
                <div>
                    <div class="member-card-header">
                        <div class="member-avatar" style="background-color: ${color};">${initials}</div>
                        <div class="member-info">
                            <h3>${escapeHtml(m.name)}</h3>
                            <div class="member-badges">
                                <span class="member-badge relation">${escapeHtml(m.relationship)}</span>
                                <span class="member-badge">${ageDisplay}</span>
                                ${bloodDisplay}
                            </div>
                        </div>
                    </div>

                    <div class="member-card-stats">
                        <div>
                            <div class="member-card-stat-num">${m.records_count || 0}</div>
                            <div class="member-card-stat-label">Records</div>
                        </div>
                        <div>
                            <div class="member-card-stat-num">${m.medications_count || 0}</div>
                            <div class="member-card-stat-label">Active Meds</div>
                        </div>
                        <div>
                            <div class="member-card-stat-num">${m.measurements_count || 0}</div>
                            <div class="member-card-stat-label">Vitals</div>
                        </div>
                    </div>
                </div>

                <div class="member-card-footer">
                    <span class="member-card-meta"><i class="far fa-clock"></i> ${lastRecordDate}</span>
                    <div class="member-card-actions">
                        <button class="btn btn-sm btn-outline btn-member-edit" data-id="${m.id}" title="Edit Member">
                            <i class="fas fa-pencil-alt"></i>
                        </button>
                        <button class="btn btn-sm btn-primary btn-member-view" data-id="${m.id}">
                            View Profile <i class="fas fa-chevron-right" style="font-size:0.75rem;"></i>
                        </button>
                    </div>
                </div>
            `;

            // Card Events
            card.querySelector('.btn-member-view').addEventListener('click', () => {
                showMemberProfile(m.id);
            });

            card.querySelector('.btn-member-edit').addEventListener('click', (e) => {
                e.stopPropagation();
                openEditMemberModal(m);
            });

            membersGrid.appendChild(card);
        });
    }

    function renderRecentRecords(records) {
        if (!recentRecordsGrid) return;
        recentRecordsGrid.innerHTML = '';

        records.slice(0, 4).forEach(r => {
            const card = document.createElement('div');
            card.className = 'record-card';
            const iconClass = r.has_document ? (r.file_name && r.file_name.endsWith('.pdf') ? 'pdf' : 'img') : 'doc';
            const icon = r.has_document ? (r.file_name && r.file_name.endsWith('.pdf') ? 'fas fa-file-pdf' : 'fas fa-file-image') : 'fas fa-file-medical';

            card.innerHTML = `
                <div>
                    <div class="record-top">
                        <div class="record-type-icon ${iconClass}"><i class="${icon}"></i></div>
                        <div>
                            <h4 class="record-title">${escapeHtml(r.title)}</h4>
                            <div class="record-provider">${escapeHtml(r.provider || r.category)}</div>
                        </div>
                    </div>
                    <div class="record-meta-bar">
                        <span><i class="fas fa-user text-muted"></i> ${escapeHtml(r.member_name || 'Member')}</span>
                        <span><i class="far fa-calendar text-muted"></i> ${formatDisplayDate(r.record_date)}</span>
                    </div>
                </div>
                <div class="record-actions">
                    <span class="member-badge">${escapeHtml(r.category)}</span>
                    <button class="btn btn-sm btn-outline btn-open-rec-member" data-member="${r.member_id}">
                        Open Member
                    </button>
                </div>
            `;

            card.querySelector('.btn-open-rec-member').addEventListener('click', () => {
                showMemberProfile(r.member_id, 'tab-records');
            });

            recentRecordsGrid.appendChild(card);
        });
    }

    function populateMemberDropdowns(members) {
        const recordMemberSelect = document.getElementById('recordFormMember');
        if (recordMemberSelect) {
            recordMemberSelect.innerHTML = '<option value="">Select Family Member</option>';
            members.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.textContent = `${m.name} (${m.relationship})`;
                recordMemberSelect.appendChild(opt);
            });
        }
    }

    // ==========================================================================
    // DATA LOADING: INDIVIDUAL MEMBER PROFILE
    // ==========================================================================

    async function loadMemberProfileData(memberId) {
        try {
            // Fetch member details
            const member = await SwasthAPI.family.getMember(memberId);
            currentMember = member;

            // Populate header banner
            profileHeaderName.textContent = member.name;
            profileBreadcrumbName.textContent = member.name;
            profileHeaderRelation.textContent = member.relationship;
            profileHeaderAvatar.textContent = getInitials(member.name);
            profileHeaderAvatar.style.backgroundColor = member.avatar_color || '#0F766E';

            profileHeaderBlood.textContent = member.blood_group ? `Blood: ${member.blood_group}` : 'Blood: Unknown';
            profileHeaderAge.textContent = member.age !== null && member.age !== undefined ? `Age: ${member.age} yrs` : 'Age: --';

            if (member.date_of_birth) {
                profileHeaderDobSpan.hidden = false;
                profileHeaderDob.textContent = formatDisplayDate(member.date_of_birth);
            } else {
                profileHeaderDobSpan.hidden = true;
            }

            if (member.gender) {
                profileHeaderGenderSpan.hidden = false;
                profileHeaderGender.textContent = member.gender;
            } else {
                profileHeaderGenderSpan.hidden = true;
            }

            if (member.phone) {
                profileHeaderPhoneSpan.hidden = false;
                profileHeaderPhone.textContent = member.phone;
            } else {
                profileHeaderPhoneSpan.hidden = true;
            }

            // Overview Tab content
            const emText = document.getElementById('overviewEmergencyText');
            if (emText) emText.textContent = member.emergency_contact || 'None provided';
            const notesText = document.getElementById('overviewNotesText');
            if (notesText) notesText.textContent = member.notes || 'No personal notes saved.';

            // Render Medical History
            renderMedicalHistory(member.medical_history || []);

            // Parallel load records, meds, vitals, timeline
            const [records, meds, vitals, timeline] = await Promise.all([
                SwasthAPI.family.listRecords({ memberId }),
                SwasthAPI.family.listMedications({ memberId }),
                SwasthAPI.family.listMeasurements({ memberId }),
                SwasthAPI.family.getTimeline(memberId)
            ]);

            memberRecords = records || [];
            memberMeds = meds || [];
            memberVitals = vitals || [];

            // Update badge counts
            if (countProfileHistory) countProfileHistory.textContent = (member.medical_history || []).length;
            if (countProfileRecords) countProfileRecords.textContent = memberRecords.length;
            if (countProfileMeds) countProfileMeds.textContent = memberMeds.length;

            renderMemberRecords(memberRecords);
            renderMemberMedications(memberMeds);
            renderMemberVitals(memberVitals);
            renderTimeline(timeline || []);

            // Populate Overview quick cards
            renderOverviewMedsList(memberMeds);
            renderOverviewHistoryList(member.medical_history || []);
            renderOverviewRecentMemberRecords(memberRecords);

        } catch (err) {
            showAlert('Failed to load member profile: ' + err.message, true);
        }
    }

    // ==========================================================================
    // TAB: MEDICAL HISTORY
    // ==========================================================================

    function renderMedicalHistory(items) {
        if (!profileHistoryContainer) return;
        profileHistoryContainer.innerHTML = '';

        if (!items || items.length === 0) {
            historyEmptyState.hidden = false;
            return;
        }

        historyEmptyState.hidden = true;

        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'history-card';

            let icon = 'fas fa-notes-medical';
            if (item.category === 'allergy') icon = 'fas fa-exclamation-triangle';
            if (item.category === 'surgery') icon = 'fas fa-procedures';
            if (item.category === 'family_history') icon = 'fas fa-dna';

            let statusBadge = '<span class="member-badge relation">Ongoing</span>';
            if (item.status === 'resolved') statusBadge = '<span class="member-badge" style="background:#E2E8F0;">Resolved</span>';
            if (item.status === 'in_management') statusBadge = '<span class="member-badge" style="background:#FEF3C7; color:#D97706;">In Management</span>';

            card.innerHTML = `
                <div class="history-card-main">
                    <div class="history-icon-badge"><i class="${icon}"></i></div>
                    <div>
                        <h4 class="history-title">${escapeHtml(item.title)}</h4>
                        <div class="history-meta">
                            ${statusBadge}
                            <span class="member-badge">${escapeHtml(item.category.replace('_', ' ').toUpperCase())}</span>
                            ${item.diagnosed_date ? `<span><i class="far fa-calendar"></i> Diagnosed: ${formatDisplayDate(item.diagnosed_date)}</span>` : ''}
                            ${item.doctor_or_hospital ? `<span><i class="fas fa-hospital"></i> ${escapeHtml(item.doctor_or_hospital)}</span>` : ''}
                        </div>
                        ${item.notes ? `<p class="history-notes">${escapeHtml(item.notes)}</p>` : ''}
                    </div>
                </div>
                <div style="display:flex; gap:0.5rem;">
                    <button class="btn btn-sm btn-outline btn-edit-hist" data-id="${item.id}" title="Edit"><i class="fas fa-pencil-alt"></i></button>
                    <button class="btn btn-sm btn-outline text-danger btn-del-hist" data-id="${item.id}" title="Delete"><i class="fas fa-trash-alt"></i></button>
                </div>
            `;

            card.querySelector('.btn-edit-hist').addEventListener('click', () => {
                openEditHistoryModal(item);
            });

            card.querySelector('.btn-del-hist').addEventListener('click', () => {
                showConfirm('Delete Medical History Entry', `Are you sure you want to delete '${item.title}'?`, async () => {
                    await SwasthAPI.family.deleteHistory(currentMemberId, item.id);
                    showAlert('Medical history entry deleted successfully');
                    await loadMemberProfileData(currentMemberId);
                });
            });

            profileHistoryContainer.appendChild(card);
        });
    }

    function renderOverviewHistoryList(items) {
        const el = document.getElementById('overviewHistoryList');
        if (!el) return;
        if (!items || items.length === 0) {
            el.innerHTML = '<p class="text-muted text-center" style="padding: 1.5rem 0;">No conditions recorded.</p>';
            return;
        }
        el.innerHTML = '';
        items.slice(0, 3).forEach(it => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'flex-between py-2 border-bottom';
            itemDiv.style.borderBottom = '1px solid var(--border-light)';
            itemDiv.innerHTML = `
                <div>
                    <strong style="font-size:0.9rem;">${escapeHtml(it.title)}</strong>
                    <div class="text-muted" style="font-size:0.75rem;">${escapeHtml(it.status)}</div>
                </div>
                <span class="member-badge">${escapeHtml(it.category)}</span>
            `;
            el.appendChild(itemDiv);
        });
    }

    // ==========================================================================
    // TAB: HEALTH RECORDS & DOCUMENTS
    // ==========================================================================

    function renderMemberRecords(records) {
        if (!profileRecordsContainer) return;
        profileRecordsContainer.innerHTML = '';

        if (!records || records.length === 0) {
            recordsEmptyState.hidden = false;
            return;
        }

        recordsEmptyState.hidden = true;

        records.forEach(rec => {
            const card = document.createElement('div');
            card.className = 'record-card';

            const isPdf = rec.file_name && rec.file_name.toLowerCase().endsWith('.pdf');
            const isImg = rec.file_name && (rec.file_name.toLowerCase().endsWith('.jpg') || rec.file_name.toLowerCase().endsWith('.jpeg') || rec.file_name.toLowerCase().endsWith('.png'));

            let iconClass = 'doc';
            let icon = 'fas fa-file-medical';
            if (isPdf) { iconClass = 'pdf'; icon = 'fas fa-file-pdf'; }
            else if (isImg) { iconClass = 'img'; icon = 'fas fa-file-image'; }

            const sizeDisplay = rec.file_size ? `${(rec.file_size / (1024 * 1024)).toFixed(1)} MB` : '';

            card.innerHTML = `
                <div>
                    <div class="record-top">
                        <div class="record-type-icon ${iconClass}"><i class="${icon}"></i></div>
                        <div>
                            <h4 class="record-title">${escapeHtml(rec.title)}</h4>
                            <div class="record-provider">${escapeHtml(rec.provider || 'Clinical Provider')}</div>
                        </div>
                    </div>
                    <div class="record-meta-bar">
                        <span><i class="far fa-calendar"></i> ${formatDisplayDate(rec.record_date)}</span>
                        <span><span class="member-badge">${escapeHtml(rec.category)}</span></span>
                    </div>
                    ${rec.notes ? `<p class="text-secondary" style="font-size:0.85rem; margin-bottom: 0.5rem;">${escapeHtml(rec.notes)}</p>` : ''}
                    ${rec.file_name ? `<div class="text-muted" style="font-size:0.75rem;"><i class="fas fa-paperclip"></i> ${escapeHtml(rec.file_name)} ${sizeDisplay ? `(${sizeDisplay})` : ''}</div>` : ''}
                </div>
                <div class="record-actions">
                    <div style="display:flex; gap:0.4rem;">
                        ${rec.has_document ? `
                            <button class="btn btn-sm btn-outline btn-preview-doc" data-id="${rec.id}" title="Preview / Download Document">
                                <i class="fas fa-eye"></i> View File
                            </button>
                        ` : '<span class="text-muted" style="font-size:0.75rem;">Manual Entry</span>'}
                    </div>
                    <div style="display:flex; gap:0.4rem;">
                        <button class="btn btn-sm btn-outline btn-edit-rec" data-id="${rec.id}" title="Edit"><i class="fas fa-pencil-alt"></i></button>
                        <button class="btn btn-sm btn-outline text-danger btn-del-rec" data-id="${rec.id}" title="Delete"><i class="fas fa-trash-alt"></i></button>
                    </div>
                </div>
            `;

            if (rec.has_document) {
                card.querySelector('.btn-preview-doc').addEventListener('click', () => {
                    previewDocument(rec);
                });
            }

            card.querySelector('.btn-edit-rec').addEventListener('click', () => {
                openEditRecordModal(rec);
            });

            card.querySelector('.btn-del-rec').addEventListener('click', () => {
                showConfirm('Delete Health Record', `Are you sure you want to delete '${rec.title}'? This will also remove any attached document file permanently.`, async () => {
                    await SwasthAPI.family.deleteRecord(rec.id);
                    showAlert('Record deleted successfully');
                    await loadMemberProfileData(currentMemberId);
                });
            });

            profileRecordsContainer.appendChild(card);
        });
    }

    function renderOverviewRecentMemberRecords(records) {
        const grid = document.getElementById('overviewMemberRecordsGrid');
        if (!grid) return;
        grid.innerHTML = '';
        if (!records || records.length === 0) {
            grid.innerHTML = '<p class="text-muted text-center" style="grid-column: 1/-1; padding: 1.5rem 0;">No documents uploaded yet.</p>';
            return;
        }
        records.slice(0, 3).forEach(rec => {
            const card = document.createElement('div');
            card.className = 'record-card';
            card.innerHTML = `
                <div class="record-top">
                    <div class="record-type-icon doc"><i class="fas fa-file-medical"></i></div>
                    <div>
                        <h4 class="record-title">${escapeHtml(rec.title)}</h4>
                        <div class="record-provider">${escapeHtml(rec.category)} • ${formatDisplayDate(rec.record_date)}</div>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
    }

    // Document Preview
    async function previewDocument(rec) {
        const modalTitle = document.getElementById('previewModalTitle');
        const iframe = document.getElementById('previewIframe');
        const img = document.getElementById('previewImg');
        const loader = document.getElementById('previewLoading');
        const dlLink = document.getElementById('previewDownloadLink');

        if (modalTitle) modalTitle.textContent = rec.title;
        iframe.hidden = true;
        img.hidden = true;
        loader.hidden = false;

        openModal('previewModal');

        try {
            const blob = await SwasthAPI.family.fetchDocumentBlob(rec.id);
            const blobUrl = URL.createObjectURL(blob);

            dlLink.href = blobUrl;
            dlLink.download = rec.file_name || 'document';

            loader.hidden = true;

            if (rec.file_type === 'application/pdf' || (rec.file_name && rec.file_name.endsWith('.pdf'))) {
                iframe.src = blobUrl;
                iframe.hidden = false;
            } else {
                img.src = blobUrl;
                img.hidden = false;
            }
        } catch (err) {
            loader.innerHTML = `<p class="text-danger"><i class="fas fa-exclamation-circle"></i> Failed to preview document: ${err.message}</p>`;
        }
    }

    // Search & Filter Records
    document.getElementById('filterRecordCategory')?.addEventListener('change', filterRecordsList);
    document.getElementById('searchRecordInput')?.addEventListener('input', filterRecordsList);

    function filterRecordsList() {
        const cat = document.getElementById('filterRecordCategory')?.value;
        const search = document.getElementById('searchRecordInput')?.value.toLowerCase().trim();

        let filtered = memberRecords;
        if (cat && cat !== 'All') {
            filtered = filtered.filter(r => r.category === cat);
        }
        if (search) {
            filtered = filtered.filter(r =>
                (r.title && r.title.toLowerCase().includes(search)) ||
                (r.provider && r.provider.toLowerCase().includes(search)) ||
                (r.notes && r.notes.toLowerCase().includes(search))
            );
        }
        renderMemberRecords(filtered);
    }

    // ==========================================================================
    // TAB: PRESCRIPTIONS & MEDICATIONS
    // ==========================================================================

    function renderMemberMedications(meds) {
        if (!profileMedsContainer) return;
        profileMedsContainer.innerHTML = '';

        if (!meds || meds.length === 0) {
            medsEmptyState.hidden = false;
            return;
        }

        medsEmptyState.hidden = true;

        meds.forEach(med => {
            const card = document.createElement('div');
            card.className = `med-card status-${med.status}`;

            const statusLabel = med.status === 'active' ? 'Active' : (med.status === 'completed' ? 'Completed' : 'Paused');
            const statusClass = med.status === 'active' ? 'relation' : '';

            card.innerHTML = `
                <div>
                    <div class="med-header">
                        <h4 class="med-title">${escapeHtml(med.name)}</h4>
                        <span class="member-badge ${statusClass}">${statusLabel}</span>
                    </div>
                    <div class="med-dosage-tag">${escapeHtml(med.dosage)} • ${escapeHtml(med.frequency)}</div>
                    ${med.instructions ? `<p class="med-details"><i class="fas fa-info-circle text-muted"></i> ${escapeHtml(med.instructions)}</p>` : ''}
                    ${med.prescribing_doctor ? `<div class="text-muted" style="font-size:0.8rem; margin-bottom:0.4rem;"><i class="fas fa-user-md"></i> Prescribed by: ${escapeHtml(med.prescribing_doctor)}</div>` : ''}
                    <div class="text-muted" style="font-size:0.75rem;">
                        <i class="far fa-calendar-alt"></i> Started: ${formatDisplayDate(med.start_date)} ${med.end_date ? `to ${formatDisplayDate(med.end_date)}` : ''}
                    </div>
                </div>
                <div class="record-actions" style="margin-top: 1rem; border-top: 1px solid var(--border-light); padding-top: 0.75rem;">
                    <div>
                        ${med.status === 'active' ? `
                            <button class="btn btn-sm btn-outline btn-complete-med" data-id="${med.id}">Mark Completed</button>
                        ` : `
                            <button class="btn btn-sm btn-outline btn-reactivate-med" data-id="${med.id}">Reactivate</button>
                        `}
                    </div>
                    <div style="display:flex; gap:0.4rem;">
                        <button class="btn btn-sm btn-outline btn-edit-med" data-id="${med.id}" title="Edit"><i class="fas fa-pencil-alt"></i></button>
                        <button class="btn btn-sm btn-outline text-danger btn-del-med" data-id="${med.id}" title="Delete"><i class="fas fa-trash-alt"></i></button>
                    </div>
                </div>
            `;

            if (card.querySelector('.btn-complete-med')) {
                card.querySelector('.btn-complete-med').addEventListener('click', async () => {
                    await SwasthAPI.family.updateMedication(med.id, { status: 'completed' });
                    await loadMemberProfileData(currentMemberId);
                });
            }

            if (card.querySelector('.btn-reactivate-med')) {
                card.querySelector('.btn-reactivate-med').addEventListener('click', async () => {
                    await SwasthAPI.family.updateMedication(med.id, { status: 'active' });
                    await loadMemberProfileData(currentMemberId);
                });
            }

            card.querySelector('.btn-edit-med').addEventListener('click', () => {
                openEditMedModal(med);
            });

            card.querySelector('.btn-del-med').addEventListener('click', () => {
                showConfirm('Delete Medication Record', `Are you sure you want to delete '${med.name}'?`, async () => {
                    await SwasthAPI.family.deleteMedication(med.id);
                    showAlert('Medication deleted successfully');
                    await loadMemberProfileData(currentMemberId);
                });
            });

            profileMedsContainer.appendChild(card);
        });
    }

    function renderOverviewMedsList(meds) {
        const el = document.getElementById('overviewMedsList');
        if (!el) return;
        const activeMeds = (meds || []).filter(m => m.status === 'active');
        if (activeMeds.length === 0) {
            el.innerHTML = '<p class="text-muted text-center" style="padding: 1.5rem 0;">No active medications.</p>';
            return;
        }
        el.innerHTML = '';
        activeMeds.slice(0, 3).forEach(med => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'flex-between py-2 border-bottom';
            itemDiv.style.borderBottom = '1px solid var(--border-light)';
            itemDiv.innerHTML = `
                <div>
                    <strong style="font-size:0.9rem;">${escapeHtml(med.name)}</strong>
                    <div class="text-muted" style="font-size:0.75rem;">${escapeHtml(med.dosage)} • ${escapeHtml(med.frequency)}</div>
                </div>
                <span class="member-badge relation">Active</span>
            `;
            el.appendChild(itemDiv);
        });
    }

    document.getElementById('filterMedStatus')?.addEventListener('change', (e) => {
        const val = e.target.value;
        if (val === 'All') {
            renderMemberMedications(memberMeds);
        } else {
            renderMemberMedications(memberMeds.filter(m => m.status === val));
        }
    });

    // ==========================================================================
    // TAB: HEALTH PROGRESS & VITALS TRACKING (CHART.JS)
    // ==========================================================================

    function renderMemberVitals(vitals) {
        // Update summary values on cards
        const bpEntries = vitals.filter(v => v.metric_type === 'blood_pressure');
        const glucoseEntries = vitals.filter(v => v.metric_type === 'blood_glucose');
        const weightEntries = vitals.filter(v => v.metric_type === 'weight');
        const hrEntries = vitals.filter(v => v.metric_type === 'heart_rate');

        const latestBP = bpEntries.length > 0 ? bpEntries[bpEntries.length - 1] : null;
        const latestGlucose = glucoseEntries.length > 0 ? glucoseEntries[glucoseEntries.length - 1] : null;
        const latestWeight = weightEntries.length > 0 ? weightEntries[weightEntries.length - 1] : null;
        const latestHR = hrEntries.length > 0 ? hrEntries[hrEntries.length - 1] : null;

        document.getElementById('vitalValBP').textContent = latestBP ? `${latestBP.value}/${latestBP.value_secondary || '--'}` : '--/--';
        document.getElementById('vitalValGlucose').textContent = latestGlucose ? latestGlucose.value : '--';
        document.getElementById('vitalValWeight').textContent = latestWeight ? latestWeight.value : '--';
        document.getElementById('vitalValHR').textContent = latestHR ? latestHR.value : '--';

        renderVitalsTable(vitals);
        renderVitalsChart();
    }

    function renderVitalsTable(vitals) {
        if (!vitalsLogTableBody) return;
        vitalsLogTableBody.innerHTML = '';

        if (!vitals || vitals.length === 0) {
            vitalsLogTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted" style="padding: 2rem 1rem;">No health vitals logged yet.</td></tr>';
            return;
        }

        // Display newest first in table
        [...vitals].reverse().forEach(v => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-light)';
            tr.style.fontSize = '0.9rem';

            let valStr = `${v.value}`;
            if (v.value_secondary !== null && v.value_secondary !== undefined) {
                valStr = `${v.value}/${v.value_secondary}`;
            }

            tr.innerHTML = `
                <td style="padding: 0.75rem 1rem;"><i class="far fa-calendar text-muted"></i> ${formatDisplayDate(v.recorded_date)}</td>
                <td style="padding: 0.75rem 1rem;"><span class="member-badge">${escapeHtml(v.metric_name)}</span></td>
                <td style="padding: 0.75rem 1rem;"><strong>${valStr}</strong> ${escapeHtml(v.unit)}</td>
                <td style="padding: 0.75rem 1rem;" class="text-muted">${escapeHtml(v.notes || '--')}</td>
                <td style="padding: 0.75rem 1rem; text-align: right;">
                    <button class="btn btn-sm btn-outline text-danger btn-del-vital" data-id="${v.id}" title="Delete"><i class="fas fa-trash-alt"></i></button>
                </td>
            `;

            tr.querySelector('.btn-del-vital').addEventListener('click', () => {
                showConfirm('Delete Measurement', `Delete this ${v.metric_name} entry?`, async () => {
                    await SwasthAPI.family.deleteMeasurement(v.id);
                    showAlert('Measurement deleted');
                    await loadMemberProfileData(currentMemberId);
                });
            });

            vitalsLogTableBody.appendChild(tr);
        });
    }

    // Chart.js Visualization
    function renderVitalsChart() {
        const canvas = document.getElementById('vitalsChart');
        if (!canvas) return;

        const filtered = memberVitals.filter(v => v.metric_type === activeVitalsMetric);
        const titleEl = document.getElementById('chartTitle');
        const singleNotice = document.getElementById('chartSingleNotice');

        let metricDisplayName = 'Blood Pressure';
        if (activeVitalsMetric === 'blood_glucose') metricDisplayName = 'Blood Glucose';
        if (activeVitalsMetric === 'weight') metricDisplayName = 'Body Weight';
        if (activeVitalsMetric === 'heart_rate') metricDisplayName = 'Heart Rate';

        if (titleEl) titleEl.textContent = `${metricDisplayName} Trend`;

        if (vitalsChartInstance) {
            vitalsChartInstance.destroy();
            vitalsChartInstance = null;
        }

        if (filtered.length === 0) {
            if (singleNotice) singleNotice.style.display = 'none';
            // Render clean empty placeholder
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = '14px Inter, sans-serif';
            ctx.fillStyle = '#94A3B8';
            ctx.textAlign = 'center';
            ctx.fillText(`No ${metricDisplayName} records found. Click "Log Measurement" to begin tracking.`, canvas.width / 2 || 250, 150);
            return;
        }

        if (filtered.length === 1) {
            if (singleNotice) singleNotice.style.display = 'inline-block';
        } else {
            if (singleNotice) singleNotice.style.display = 'none';
        }

        const labels = filtered.map(f => formatDisplayDate(f.recorded_date));
        const datasets = [];

        if (activeVitalsMetric === 'blood_pressure') {
            datasets.push({
                label: 'Systolic (mmHg)',
                data: filtered.map(f => f.value),
                borderColor: '#DC2626',
                backgroundColor: 'rgba(220, 38, 38, 0.1)',
                tension: 0.3,
                fill: false,
                pointRadius: 5,
                pointHoverRadius: 7
            });
            datasets.push({
                label: 'Diastolic (mmHg)',
                data: filtered.map(f => f.value_secondary || 0),
                borderColor: '#0284C7',
                backgroundColor: 'rgba(2, 132, 199, 0.1)',
                tension: 0.3,
                fill: false,
                pointRadius: 5,
                pointHoverRadius: 7
            });
        } else {
            const unit = filtered[0].unit || '';
            datasets.push({
                label: `${metricDisplayName} (${unit})`,
                data: filtered.map(f => f.value),
                borderColor: '#0F766E',
                backgroundColor: 'rgba(15, 118, 110, 0.15)',
                tension: 0.3,
                fill: true,
                pointRadius: 6,
                pointHoverRadius: 8
            });
        }

        vitalsChartInstance = new Chart(canvas, {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            font: { family: 'Inter, sans-serif', size: 12, weight: '500' },
                            color: '#334155'
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(226, 232, 240, 0.6)' },
                        ticks: { font: { size: 11 }, color: '#64748B' }
                    },
                    y: {
                        grid: { color: 'rgba(226, 232, 240, 0.6)' },
                        ticks: { font: { size: 11 }, color: '#64748B' }
                    }
                }
            }
        });
    }

    // Metric Selector Click Handling
    document.querySelectorAll('.vital-summary-card').forEach(card => {
        card.addEventListener('click', () => {
            document.querySelectorAll('.vital-summary-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            activeVitalsMetric = card.getAttribute('data-metric');
            renderVitalsChart();
        });
    });

    // ==========================================================================
    // TAB: HEALTH TIMELINE
    // ==========================================================================

    function renderTimeline(events) {
        if (!profileTimelineContainer) return;
        profileTimelineContainer.innerHTML = '';

        if (!events || events.length === 0) {
            timelineEmptyState.hidden = false;
            return;
        }

        timelineEmptyState.hidden = true;

        events.forEach(ev => {
            const item = document.createElement('div');
            item.className = 'timeline-item';

            item.innerHTML = `
                <div class="timeline-dot" style="border-color: ${ev.badge_color}; color: ${ev.badge_color};">
                    <i class="${ev.icon}"></i>
                </div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <h4 class="timeline-title">${escapeHtml(ev.title)}</h4>
                        <span class="timeline-date"><i class="far fa-calendar"></i> ${formatDisplayDate(ev.date)}</span>
                    </div>
                    <p class="timeline-desc">${escapeHtml(ev.description)}</p>
                </div>
            `;
            profileTimelineContainer.appendChild(item);
        });
    }

    // ==========================================================================
    // FORM HANDLERS & MODAL ACTIONS
    // ==========================================================================

    // ==========================================================================
    // FORM VALIDATORS
    // ==========================================================================

    function validateMemberForm() {
        let isValid = true;
        clearModalAlert('memberFormAlert');

        const nameInput = document.getElementById('memberFormName');
        const nameVal = nameInput.value.trim();
        if (!nameVal) {
            setFieldError('memberFormName', 'Full name is required.');
            isValid = false;
        } else if (nameVal.length < 2) {
            setFieldError('memberFormName', 'Full name must be at least 2 characters.');
            isValid = false;
        } else if (!/[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]/.test(nameVal)) {
            setFieldError('memberFormName', 'Full name must contain alphabetic letters.');
            isValid = false;
        } else {
            clearFieldError('memberFormName');
        }

        const relationVal = document.getElementById('memberFormRelation').value;
        if (!relationVal) {
            setFieldError('memberFormRelation', 'Please select a relationship.');
            isValid = false;
        } else {
            clearFieldError('memberFormRelation');
        }

        const dobVal = document.getElementById('memberFormDob').value;
        if (dobVal) {
            const dobDate = new Date(dobVal);
            const today = new Date();
            today.setHours(23, 59, 59, 999);
            if (dobDate > today) {
                setFieldError('memberFormDob', 'Date of birth cannot be in the future.');
                isValid = false;
            } else if (dobDate.getFullYear() < 1900) {
                setFieldError('memberFormDob', 'Please enter a valid date of birth (after year 1900).');
                isValid = false;
            } else {
                clearFieldError('memberFormDob');
            }
        } else {
            clearFieldError('memberFormDob');
        }

        const phoneInput = document.getElementById('memberFormPhone');
        const phoneVal = phoneInput ? phoneInput.value.trim() : '';
        const phoneCheck = validatePhoneNumber(phoneVal, false);
        if (!phoneCheck.valid) {
            setFieldError('memberFormPhone', phoneCheck.error);
            isValid = false;
        } else {
            clearFieldError('memberFormPhone');
        }

        const emergencyInput = document.getElementById('memberFormEmergency');
        const emergencyVal = emergencyInput ? emergencyInput.value.trim() : '';
        const emergencyCheck = validateEmergencyContact(emergencyVal);
        if (!emergencyCheck.valid) {
            setFieldError('memberFormEmergency', emergencyCheck.error);
            isValid = false;
        } else {
            clearFieldError('memberFormEmergency');
        }

        if (!isValid) {
            setModalAlert('memberFormAlert', 'Please correct the highlighted fields before saving.');
            scrollToFirstError(memberForm);
        }

        return isValid;
    }

    function validateRecordForm() {
        let isValid = true;
        clearModalAlert('recordFormAlert');

        const memberVal = document.getElementById('recordFormMember').value;
        if (!memberVal) {
            setFieldError('recordFormMember', 'Please select which family member this record belongs to.');
            isValid = false;
        } else {
            clearFieldError('recordFormMember');
        }

        const titleVal = document.getElementById('recordFormTitle').value.trim();
        if (!titleVal) {
            setFieldError('recordFormTitle', 'Record title is required.');
            isValid = false;
        } else if (titleVal.length < 2) {
            setFieldError('recordFormTitle', 'Record title must be at least 2 characters.');
            isValid = false;
        } else {
            clearFieldError('recordFormTitle');
        }

        const categoryVal = document.getElementById('recordFormCategory').value;
        if (!categoryVal) {
            setFieldError('recordFormCategory', 'Please select a document category.');
            isValid = false;
        } else {
            clearFieldError('recordFormCategory');
        }

        const dateVal = document.getElementById('recordFormDate').value;
        if (!dateVal) {
            setFieldError('recordFormDate', 'Date of record is required.');
            isValid = false;
        } else {
            const recDate = new Date(dateVal);
            const today = new Date();
            today.setHours(23, 59, 59, 999);
            if (recDate > today) {
                setFieldError('recordFormDate', 'Record date cannot be in the future.');
                isValid = false;
            } else {
                clearFieldError('recordFormDate');
            }
        }

        const recId = document.getElementById('recordFormId').value;
        const fileError = document.getElementById('recordFileError');
        const fileErrorMsg = document.getElementById('recordFileErrorMsg');
        const dropzone = document.getElementById('recordDropzone');

        if (!recId && !selectedRecordFile) {
            if (fileError && fileErrorMsg) {
                fileErrorMsg.textContent = 'Please attach a medical report document (PDF, JPG, or PNG).';
                fileError.classList.add('show');
            }
            if (dropzone) dropzone.classList.add('is-invalid');
            isValid = false;
        } else if (selectedRecordFile) {
            const check = validateUploadedFile(selectedRecordFile);
            if (!check.valid) {
                if (fileError && fileErrorMsg) {
                    fileErrorMsg.textContent = check.error;
                    fileError.classList.add('show');
                }
                if (dropzone) dropzone.classList.add('is-invalid');
                isValid = false;
            } else {
                if (fileError) fileError.classList.remove('show');
                if (dropzone) dropzone.classList.remove('is-invalid');
            }
        } else {
            if (fileError) fileError.classList.remove('show');
            if (dropzone) dropzone.classList.remove('is-invalid');
        }

        if (!isValid) {
            setModalAlert('recordFormAlert', 'Please correct the highlighted fields before submitting.');
            scrollToFirstError(recordForm);
        }

        return isValid;
    }

    function validateHistoryForm() {
        let isValid = true;
        clearModalAlert('historyFormAlert');

        const titleVal = document.getElementById('historyFormTitle').value.trim();
        if (!titleVal) {
            setFieldError('historyFormTitle', 'Condition, allergy, or event name is required.');
            isValid = false;
        } else if (titleVal.length < 2) {
            setFieldError('historyFormTitle', 'Name must be at least 2 characters.');
            isValid = false;
        } else {
            clearFieldError('historyFormTitle');
        }

        const categoryVal = document.getElementById('historyFormCategory').value;
        if (!categoryVal) {
            setFieldError('historyFormCategory', 'Please select a category.');
            isValid = false;
        } else {
            clearFieldError('historyFormCategory');
        }

        const statusVal = document.getElementById('historyFormStatus').value;
        if (!statusVal) {
            setFieldError('historyFormStatus', 'Please select a status.');
            isValid = false;
        } else {
            clearFieldError('historyFormStatus');
        }

        const dateVal = document.getElementById('historyFormDate').value;
        if (dateVal) {
            const diagDate = new Date(dateVal);
            const today = new Date();
            today.setHours(23, 59, 59, 999);
            if (diagDate > today) {
                setFieldError('historyFormDate', 'Event/diagnosis date cannot be in the future.');
                isValid = false;
            } else {
                clearFieldError('historyFormDate');
            }
        } else {
            clearFieldError('historyFormDate');
        }

        if (!isValid) {
            setModalAlert('historyFormAlert', 'Please check the highlighted fields.');
            scrollToFirstError(historyForm);
        }

        return isValid;
    }

    function validateMedicationForm() {
        let isValid = true;
        clearModalAlert('medicationFormAlert');

        const nameVal = document.getElementById('medFormName').value.trim();
        if (!nameVal) {
            setFieldError('medFormName', 'Medication name is required.');
            isValid = false;
        } else if (nameVal.length < 2) {
            setFieldError('medFormName', 'Medication name must be at least 2 characters.');
            isValid = false;
        } else {
            clearFieldError('medFormName');
        }

        const dosageVal = document.getElementById('medFormDosage').value.trim();
        if (!dosageVal) {
            setFieldError('medFormDosage', 'Dosage is required (e.g. 500 mg, 1 tablet).');
            isValid = false;
        } else {
            clearFieldError('medFormDosage');
        }

        const freqVal = document.getElementById('medFormFrequency').value.trim();
        if (!freqVal) {
            setFieldError('medFormFrequency', 'Frequency is required (e.g. Once daily after breakfast).');
            isValid = false;
        } else {
            clearFieldError('medFormFrequency');
        }

        const statusVal = document.getElementById('medFormStatus').value;
        if (!statusVal) {
            setFieldError('medFormStatus', 'Please select medication status.');
            isValid = false;
        } else {
            clearFieldError('medFormStatus');
        }

        const startVal = document.getElementById('medFormStartDate').value;
        const endVal = document.getElementById('medFormEndDate').value;
        if (startVal && endVal) {
            if (new Date(endVal) < new Date(startVal)) {
                setFieldError('medFormEndDate', 'End date cannot be earlier than start date.');
                isValid = false;
            } else {
                clearFieldError('medFormEndDate');
            }
        } else {
            clearFieldError('medFormEndDate');
        }

        if (!isValid) {
            setModalAlert('medicationFormAlert', 'Please correct the highlighted fields before saving.');
            scrollToFirstError(medicationForm);
        }

        return isValid;
    }

    function validateMeasurementForm() {
        let isValid = true;
        clearModalAlert('measurementFormAlert');

        const type = measFormType.value;
        if (!type) {
            setFieldError('measFormType', 'Please select a measurement type.');
            isValid = false;
        } else {
            clearFieldError('measFormType');
        }

        if (type === 'custom') {
            const customName = document.getElementById('measFormCustomName').value.trim();
            if (!customName) {
                setFieldError('measFormCustomName', 'Custom metric name is required.');
                isValid = false;
            } else if (customName.length < 2) {
                setFieldError('measFormCustomName', 'Metric name must be at least 2 characters.');
                isValid = false;
            } else {
                clearFieldError('measFormCustomName');
            }
        } else {
            clearFieldError('measFormCustomName');
        }

        const valInput = document.getElementById('measFormValue');
        const valStr = valInput.value.trim();
        const numVal = parseFloat(valStr);

        if (!valStr || isNaN(numVal)) {
            setFieldError('measFormValue', 'Please enter a valid numeric value.');
            isValid = false;
        } else if (type === 'blood_pressure') {
            if (numVal < 40 || numVal > 300) {
                setFieldError('measFormValue', 'Systolic BP must be between 40 and 300 mmHg.');
                isValid = false;
            } else {
                clearFieldError('measFormValue');
            }
        } else if (type === 'blood_glucose') {
            if (numVal < 20 || numVal > 1000) {
                setFieldError('measFormValue', 'Blood glucose must be between 20 and 1000 mg/dL.');
                isValid = false;
            } else {
                clearFieldError('measFormValue');
            }
        } else if (type === 'weight') {
            if (numVal <= 0 || numVal > 400) {
                setFieldError('measFormValue', 'Weight must be between 1 and 400 kg.');
                isValid = false;
            } else {
                clearFieldError('measFormValue');
            }
        } else if (type === 'heart_rate') {
            if (numVal < 30 || numVal > 250) {
                setFieldError('measFormValue', 'Heart rate must be between 30 and 250 bpm.');
                isValid = false;
            } else {
                clearFieldError('measFormValue');
            }
        } else {
            if (numVal < 0) {
                setFieldError('measFormValue', 'Value must be positive.');
                isValid = false;
            } else {
                clearFieldError('measFormValue');
            }
        }

        if (type === 'blood_pressure') {
            const secInput = document.getElementById('measFormValueSecondary');
            const secStr = secInput.value.trim();
            const secNum = parseFloat(secStr);
            if (!secStr || isNaN(secNum)) {
                setFieldError('measFormValueSecondary', 'Diastolic BP is required.');
                isValid = false;
            } else if (secNum < 30 || secNum > 200) {
                setFieldError('measFormValueSecondary', 'Diastolic BP must be between 30 and 200 mmHg.');
                isValid = false;
            } else if (secNum >= numVal) {
                setFieldError('measFormValueSecondary', 'Diastolic must be lower than Systolic (' + numVal + ').');
                isValid = false;
            } else {
                clearFieldError('measFormValueSecondary');
            }
        } else {
            clearFieldError('measFormValueSecondary');
        }

        const unitVal = document.getElementById('measFormUnit').value.trim();
        if (!unitVal) {
            setFieldError('measFormUnit', 'Unit is required.');
            isValid = false;
        } else {
            clearFieldError('measFormUnit');
        }

        const dateVal = document.getElementById('measFormDate').value;
        if (!dateVal) {
            setFieldError('measFormDate', 'Recorded date is required.');
            isValid = false;
        } else {
            const measDate = new Date(dateVal);
            const today = new Date();
            today.setHours(23, 59, 59, 999);
            if (measDate > today) {
                setFieldError('measFormDate', 'Recorded date cannot be in the future.');
                isValid = false;
            } else {
                clearFieldError('measFormDate');
            }
        }

        if (!isValid) {
            setModalAlert('measurementFormAlert', 'Please check highlighted measurement values.');
            scrollToFirstError(measurementForm);
        }

        return isValid;
    }

    // ==========================================================================
    // FORM HANDLERS & MODAL ACTIONS
    // ==========================================================================

    // 1. ADD / EDIT FAMILY MEMBER
    const memberForm = document.getElementById('memberForm');
    const memberFormId = document.getElementById('memberFormId');
    const memberModalTitle = document.getElementById('memberModalTitle');

    document.getElementById('btnOpenAddMember')?.addEventListener('click', () => {
        openAddMemberModal();
    });
    document.getElementById('btnEmptyAddMember')?.addEventListener('click', () => {
        openAddMemberModal();
    });
    document.getElementById('btnProfileEditMember')?.addEventListener('click', () => {
        if (currentMember) openEditMemberModal(currentMember);
    });

    function openAddMemberModal() {
        memberForm.reset();
        memberFormId.value = '';
        memberModalTitle.textContent = 'Add Family Member';
        clearModalErrors(document.getElementById('memberModal'));
        openModal('memberModal');
    }

    function openEditMemberModal(member) {
        memberForm.reset();
        memberFormId.value = member.id;
        memberModalTitle.textContent = 'Edit Family Member';
        clearModalErrors(document.getElementById('memberModal'));

        document.getElementById('memberFormName').value = member.name || '';
        document.getElementById('memberFormRelation').value = member.relationship || '';
        document.getElementById('memberFormDob').value = member.date_of_birth || '';
        document.getElementById('memberFormGender').value = member.gender || '';
        document.getElementById('memberFormBlood').value = member.blood_group || '';
        document.getElementById('memberFormPhone').value = member.phone || '';
        document.getElementById('memberFormEmergency').value = member.emergency_contact || '';
        document.getElementById('memberFormNotes').value = member.notes || '';

        const color = member.avatar_color || '#0F766E';
        const radio = document.querySelector(`input[name="memberColor"][value="${color}"]`);
        if (radio) radio.checked = true;

        openModal('memberModal');
    }

    memberForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!validateMemberForm()) return;

        const id = memberFormId.value;
        const colorRadio = document.querySelector('input[name="memberColor"]:checked');

        const payload = {
            name: document.getElementById('memberFormName').value.trim(),
            relationship: document.getElementById('memberFormRelation').value,
            date_of_birth: document.getElementById('memberFormDob').value || null,
            gender: document.getElementById('memberFormGender').value || null,
            blood_group: document.getElementById('memberFormBlood').value || null,
            phone: document.getElementById('memberFormPhone').value.trim() || null,
            emergency_contact: document.getElementById('memberFormEmergency').value.trim() || null,
            notes: document.getElementById('memberFormNotes').value.trim() || null,
            avatar_color: colorRadio ? colorRadio.value : '#0F766E'
        };

        const saveBtn = document.getElementById('btnSaveMember');
        try {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';

            if (id) {
                await SwasthAPI.family.updateMember(id, payload);
                showAlert('Family member updated successfully');
            } else {
                await SwasthAPI.family.createMember(payload);
                showAlert('Family member added successfully');
            }

            closeModal('memberModal');

            if (currentMemberId) {
                await loadMemberProfileData(currentMemberId);
            } else {
                await loadOverviewData();
            }
        } catch (err) {
            setModalAlert('memberFormAlert', err.message || 'Failed to save member');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Member';
        }
    });

    // Real-time Validation for Member Form Inputs
    const memberPhoneInput = document.getElementById('memberFormPhone');
    memberPhoneInput?.addEventListener('blur', () => {
        const val = memberPhoneInput.value.trim();
        if (val) {
            const check = validatePhoneNumber(val, false);
            if (!check.valid) setFieldError('memberFormPhone', check.error);
            else clearFieldError('memberFormPhone');
        } else {
            clearFieldError('memberFormPhone');
        }
    });
    memberPhoneInput?.addEventListener('input', () => {
        if (memberPhoneInput.classList.contains('is-invalid')) {
            const val = memberPhoneInput.value.trim();
            const check = validatePhoneNumber(val, false);
            if (check.valid) clearFieldError('memberFormPhone');
        }
    });

    const memberEmergencyInput = document.getElementById('memberFormEmergency');
    memberEmergencyInput?.addEventListener('blur', () => {
        const val = memberEmergencyInput.value.trim();
        if (val) {
            const check = validateEmergencyContact(val);
            if (!check.valid) setFieldError('memberFormEmergency', check.error);
            else clearFieldError('memberFormEmergency');
        } else {
            clearFieldError('memberFormEmergency');
        }
    });
    memberEmergencyInput?.addEventListener('input', () => {
        if (memberEmergencyInput.classList.contains('is-invalid')) {
            const val = memberEmergencyInput.value.trim();
            const check = validateEmergencyContact(val);
            if (check.valid) clearFieldError('memberFormEmergency');
        }
    });

    const memberNameInput = document.getElementById('memberFormName');
    memberNameInput?.addEventListener('blur', () => {
        const val = memberNameInput.value.trim();
        if (!val) setFieldError('memberFormName', 'Full name is required.');
        else if (val.length < 2) setFieldError('memberFormName', 'Full name must be at least 2 characters.');
        else clearFieldError('memberFormName');
    });
    memberNameInput?.addEventListener('input', () => {
        if (memberNameInput.classList.contains('is-invalid') && memberNameInput.value.trim().length >= 2) {
            clearFieldError('memberFormName');
        }
    });

    document.getElementById('memberFormRelation')?.addEventListener('change', (e) => {
        if (e.target.value) clearFieldError('memberFormRelation');
    });

    // Delete Member from Profile View
    document.getElementById('btnProfileDeleteMember')?.addEventListener('click', () => {
        if (!currentMember) return;
        showConfirm(
            'Delete Family Member',
            `Are you sure you want to delete ${currentMember.name}? This will permanently remove their profile, attached medical documents, medications, and vitals.`,
            async () => {
                await SwasthAPI.family.deleteMember(currentMember.id, true);
                showAlert('Family member deleted');
                showOverview();
            }
        );
    });

    // 2. ADD / UPLOAD HEALTH RECORD
    const recordForm = document.getElementById('recordForm');
    const recordDropzone = document.getElementById('recordDropzone');
    const recordFileInput = document.getElementById('recordFileInput');
    const fileSelectedDisplay = document.getElementById('fileSelectedDisplay');
    const selectedFileName = document.getElementById('selectedFileName');
    const selectedFileSize = document.getElementById('selectedFileSize');
    const btnRemoveSelectedFile = document.getElementById('btnRemoveSelectedFile');

    document.getElementById('btnOpenAddRecordDirect')?.addEventListener('click', () => {
        openRecordModal(null);
    });
    document.getElementById('btnProfileUploadRecord')?.addEventListener('click', () => {
        openRecordModal(currentMemberId);
    });
    document.getElementById('btnTabUploadRecord')?.addEventListener('click', () => {
        openRecordModal(currentMemberId);
    });

    function openRecordModal(memberId = null) {
        recordForm.reset();
        document.getElementById('recordFormId').value = '';
        selectedRecordFile = null;
        clearModalErrors(document.getElementById('recordModal'));

        if (fileSelectedDisplay) fileSelectedDisplay.style.display = 'none';
        if (recordDropzone) {
            recordDropzone.style.display = 'block';
            recordDropzone.classList.remove('is-invalid');
        }

        const memberSelect = document.getElementById('recordFormMember');
        if (memberSelect && memberId) {
            memberSelect.value = memberId;
        }

        // Set today's date as default
        document.getElementById('recordFormDate').value = new Date().toISOString().split('T')[0];

        openModal('recordModal');
    }

    function openEditRecordModal(rec) {
        recordForm.reset();
        document.getElementById('recordFormId').value = rec.id;
        document.getElementById('recordFormMember').value = rec.member_id;
        document.getElementById('recordFormTitle').value = rec.title;
        document.getElementById('recordFormCategory').value = rec.category;
        document.getElementById('recordFormDate').value = rec.record_date;
        document.getElementById('recordFormProvider').value = rec.provider || '';
        document.getElementById('recordFormNotes').value = rec.notes || '';
        clearModalErrors(document.getElementById('recordModal'));

        // Hide file upload for edit
        if (recordDropzone) recordDropzone.style.display = 'none';
        if (fileSelectedDisplay) fileSelectedDisplay.style.display = 'none';

        openModal('recordModal');
    }

    // Drag and Drop File Handlers
    recordDropzone?.addEventListener('click', () => recordFileInput?.click());
    recordFileInput?.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handleFileSelect(e.target.files[0]);
        }
    });

    recordDropzone?.addEventListener('dragover', (e) => {
        e.preventDefault();
        recordDropzone.classList.add('dragover');
    });
    recordDropzone?.addEventListener('dragleave', () => recordDropzone.classList.remove('dragover'));
    recordDropzone?.addEventListener('drop', (e) => {
        e.preventDefault();
        recordDropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    function handleFileSelect(file) {
        const fileError = document.getElementById('recordFileError');
        const fileErrorMsg = document.getElementById('recordFileErrorMsg');
        const dropzone = document.getElementById('recordDropzone');

        const check = validateUploadedFile(file);
        if (!check.valid) {
            selectedRecordFile = null;
            if (recordFileInput) recordFileInput.value = '';
            if (fileSelectedDisplay) fileSelectedDisplay.style.display = 'none';
            if (dropzone) {
                dropzone.style.display = 'block';
                dropzone.classList.add('is-invalid');
            }
            if (fileError && fileErrorMsg) {
                fileErrorMsg.textContent = check.error;
                fileError.classList.add('show');
            }
            return;
        }

        selectedRecordFile = file;
        if (dropzone) dropzone.classList.remove('is-invalid');
        if (fileError) fileError.classList.remove('show');

        const sizeFormatted = file.size >= 1024 * 1024
            ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
            : `${(file.size / 1024).toFixed(0)} KB`;

        if (selectedFileName) selectedFileName.textContent = file.name;
        if (selectedFileSize) selectedFileSize.textContent = `(${sizeFormatted})`;

        if (fileSelectedDisplay) fileSelectedDisplay.style.display = 'flex';
        if (dropzone) dropzone.style.display = 'none';
    }

    btnRemoveSelectedFile?.addEventListener('click', () => {
        selectedRecordFile = null;
        if (recordFileInput) recordFileInput.value = '';
        if (fileSelectedDisplay) fileSelectedDisplay.style.display = 'none';
        const dropzone = document.getElementById('recordDropzone');
        if (dropzone) {
            dropzone.style.display = 'block';
            dropzone.classList.remove('is-invalid');
        }
        const fileError = document.getElementById('recordFileError');
        if (fileError) fileError.classList.remove('show');
    });

    // Real-time Validation for Record Form Inputs
    document.getElementById('recordFormMember')?.addEventListener('change', (e) => {
        if (e.target.value) clearFieldError('recordFormMember');
    });
    const recordTitleInput = document.getElementById('recordFormTitle');
    recordTitleInput?.addEventListener('blur', () => {
        const val = recordTitleInput.value.trim();
        if (!val) setFieldError('recordFormTitle', 'Record title is required.');
        else if (val.length < 2) setFieldError('recordFormTitle', 'Record title must be at least 2 characters.');
        else clearFieldError('recordFormTitle');
    });
    recordTitleInput?.addEventListener('input', () => {
        if (recordTitleInput.classList.contains('is-invalid') && recordTitleInput.value.trim().length >= 2) {
            clearFieldError('recordFormTitle');
        }
    });
    document.getElementById('recordFormCategory')?.addEventListener('change', (e) => {
        if (e.target.value) clearFieldError('recordFormCategory');
    });
    document.getElementById('recordFormDate')?.addEventListener('change', (e) => {
        if (e.target.value) clearFieldError('recordFormDate');
    });

    recordForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!validateRecordForm()) return;

        const id = document.getElementById('recordFormId').value;
        const saveBtn = document.getElementById('btnSaveRecord');

        try {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';

            if (id) {
                // Update record metadata
                await SwasthAPI.family.updateRecord(id, {
                    title: document.getElementById('recordFormTitle').value.trim(),
                    category: document.getElementById('recordFormCategory').value,
                    record_date: document.getElementById('recordFormDate').value,
                    provider: document.getElementById('recordFormProvider').value.trim() || null,
                    notes: document.getElementById('recordFormNotes').value.trim() || null
                });
                showAlert('Record details updated');
            } else {
                // Upload record with file (FormData)
                const formData = new FormData();
                formData.append('member_id', document.getElementById('recordFormMember').value);
                formData.append('title', document.getElementById('recordFormTitle').value.trim());
                formData.append('category', document.getElementById('recordFormCategory').value);
                formData.append('record_date', document.getElementById('recordFormDate').value);

                const prov = document.getElementById('recordFormProvider').value.trim();
                if (prov) formData.append('provider', prov);

                const notes = document.getElementById('recordFormNotes').value.trim();
                if (notes) formData.append('notes', notes);

                if (selectedRecordFile) {
                    formData.append('file', selectedRecordFile);
                }

                await SwasthAPI.family.createRecord(formData);
                showAlert('Health record uploaded successfully');
            }

            closeModal('recordModal');

            if (currentMemberId) {
                await loadMemberProfileData(currentMemberId);
            } else {
                await loadOverviewData();
            }
        } catch (err) {
            setModalAlert('recordFormAlert', err.message || 'Failed to save health record');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Record';
        }
    });

    // 3. MEDICAL HISTORY ITEM FORM
    const historyForm = document.getElementById('historyForm');
    const historyFormId = document.getElementById('historyFormId');

    document.getElementById('btnProfileAddHistory')?.addEventListener('click', openAddHistoryModal);
    document.getElementById('btnTabAddHistory')?.addEventListener('click', openAddHistoryModal);

    function openAddHistoryModal() {
        historyForm.reset();
        historyFormId.value = '';
        document.getElementById('historyModalTitle').textContent = 'Add Medical History Entry';
        clearModalErrors(document.getElementById('historyModal'));
        openModal('historyModal');
    }

    function openEditHistoryModal(item) {
        historyForm.reset();
        historyFormId.value = item.id;
        document.getElementById('historyModalTitle').textContent = 'Edit Medical History Entry';
        clearModalErrors(document.getElementById('historyModal'));

        document.getElementById('historyFormTitle').value = item.title;
        document.getElementById('historyFormCategory').value = item.category;
        document.getElementById('historyFormStatus').value = item.status;
        document.getElementById('historyFormDate').value = item.diagnosed_date || '';
        document.getElementById('historyFormDoctor').value = item.doctor_or_hospital || '';
        document.getElementById('historyFormNotes').value = item.notes || '';

        openModal('historyModal');
    }

    historyForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!validateHistoryForm()) return;

        const itemId = historyFormId.value;
        const saveBtn = document.getElementById('btnSaveHistory');

        const payload = {
            title: document.getElementById('historyFormTitle').value.trim(),
            category: document.getElementById('historyFormCategory').value,
            status: document.getElementById('historyFormStatus').value,
            diagnosed_date: document.getElementById('historyFormDate').value || null,
            doctor_or_hospital: document.getElementById('historyFormDoctor').value.trim() || null,
            notes: document.getElementById('historyFormNotes').value.trim() || null
        };

        try {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';

            if (itemId) {
                await SwasthAPI.family.updateHistory(currentMemberId, itemId, payload);
                showAlert('Medical history updated');
            } else {
                await SwasthAPI.family.addHistory(currentMemberId, payload);
                showAlert('Medical history entry added');
            }

            closeModal('historyModal');
            await loadMemberProfileData(currentMemberId);
        } catch (err) {
            setModalAlert('historyFormAlert', err.message || 'Failed to save history entry');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Entry';
        }
    });

    // 4. PRESCRIPTION / MEDICATION FORM
    const medicationForm = document.getElementById('medicationForm');
    const medicationFormId = document.getElementById('medicationFormId');

    document.getElementById('btnProfileAddMed')?.addEventListener('click', openAddMedModal);
    document.getElementById('btnTabAddMed')?.addEventListener('click', openAddMedModal);

    function openAddMedModal() {
        medicationForm.reset();
        medicationFormId.value = '';
        document.getElementById('medicationModalTitle').textContent = 'Add Prescription / Medication';
        document.getElementById('medFormStartDate').value = new Date().toISOString().split('T')[0];
        clearModalErrors(document.getElementById('medicationModal'));
        openModal('medicationModal');
    }

    function openEditMedModal(med) {
        medicationForm.reset();
        medicationFormId.value = med.id;
        document.getElementById('medicationModalTitle').textContent = 'Edit Prescription / Medication';
        clearModalErrors(document.getElementById('medicationModal'));

        document.getElementById('medFormName').value = med.name;
        document.getElementById('medFormDosage').value = med.dosage;
        document.getElementById('medFormFrequency').value = med.frequency;
        document.getElementById('medFormStartDate').value = med.start_date || '';
        document.getElementById('medFormEndDate').value = med.end_date || '';
        document.getElementById('medFormDoctor').value = med.prescribing_doctor || '';
        document.getElementById('medFormStatus').value = med.status;
        document.getElementById('medFormInstructions').value = med.instructions || '';

        openModal('medicationModal');
    }

    medicationForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!validateMedicationForm()) return;

        const medId = medicationFormId.value;
        const saveBtn = document.getElementById('btnSaveMedication');

        const payload = {
            member_id: currentMemberId,
            name: document.getElementById('medFormName').value.trim(),
            dosage: document.getElementById('medFormDosage').value.trim(),
            frequency: document.getElementById('medFormFrequency').value.trim(),
            start_date: document.getElementById('medFormStartDate').value || null,
            end_date: document.getElementById('medFormEndDate').value || null,
            prescribing_doctor: document.getElementById('medFormDoctor').value.trim() || null,
            status: document.getElementById('medFormStatus').value,
            instructions: document.getElementById('medFormInstructions').value.trim() || null
        };

        try {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';

            if (medId) {
                await SwasthAPI.family.updateMedication(medId, payload);
                showAlert('Medication updated');
            } else {
                await SwasthAPI.family.createMedication(payload);
                showAlert('Medication added successfully');
            }

            closeModal('medicationModal');
            await loadMemberProfileData(currentMemberId);
        } catch (err) {
            setModalAlert('medicationFormAlert', err.message || 'Failed to save medication');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Medication';
        }
    });

    // 5. HEALTH MEASUREMENT / VITAL FORM
    const measurementForm = document.getElementById('measurementForm');
    const measFormType = document.getElementById('measFormType');
    const measCustomGroup = document.getElementById('measCustomNameGroup');
    const measSecondaryGroup = document.getElementById('measValSecondaryGroup');
    const measValLabel = document.getElementById('measValLabel');
    const measFormUnit = document.getElementById('measFormUnit');

    document.getElementById('btnProfileLogVital')?.addEventListener('click', openMeasurementModal);
    document.getElementById('btnTabLogVital')?.addEventListener('click', openMeasurementModal);

    function openMeasurementModal() {
        measurementForm.reset();
        document.getElementById('measFormDate').value = new Date().toISOString().split('T')[0];
        clearModalErrors(document.getElementById('measurementModal'));
        updateMeasurementFields();
        openModal('measurementModal');
    }

    measFormType?.addEventListener('change', updateMeasurementFields);

    function updateMeasurementFields() {
        const type = measFormType.value;
        if (type === 'blood_pressure') {
            measSecondaryGroup.style.display = 'block';
            measCustomGroup.style.display = 'none';
            measValLabel.textContent = 'Systolic (mmHg) *';
            measFormUnit.value = 'mmHg';
        } else if (type === 'blood_glucose') {
            measSecondaryGroup.style.display = 'none';
            measCustomGroup.style.display = 'none';
            measValLabel.textContent = 'Blood Glucose (mg/dL) *';
            measFormUnit.value = 'mg/dL';
        } else if (type === 'weight') {
            measSecondaryGroup.style.display = 'none';
            measCustomGroup.style.display = 'none';
            measValLabel.textContent = 'Weight (kg) *';
            measFormUnit.value = 'kg';
        } else if (type === 'heart_rate') {
            measSecondaryGroup.style.display = 'none';
            measCustomGroup.style.display = 'none';
            measValLabel.textContent = 'Heart Rate (bpm) *';
            measFormUnit.value = 'bpm';
        } else {
            measSecondaryGroup.style.display = 'none';
            measCustomGroup.style.display = 'block';
            measValLabel.textContent = 'Recorded Value *';
            measFormUnit.value = '';
        }
    }

    measurementForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!validateMeasurementForm()) return;

        const type = measFormType.value;
        const saveBtn = document.getElementById('btnSaveMeasurement');

        let metricName = 'Blood Pressure';
        if (type === 'blood_glucose') metricName = 'Blood Glucose';
        if (type === 'weight') metricName = 'Body Weight';
        if (type === 'heart_rate') metricName = 'Heart Rate';
        if (type === 'custom') metricName = document.getElementById('measFormCustomName').value.trim() || 'Custom Metric';

        const payload = {
            member_id: currentMemberId,
            metric_type: type,
            metric_name: metricName,
            value: parseFloat(document.getElementById('measFormValue').value),
            value_secondary: type === 'blood_pressure' && document.getElementById('measFormValueSecondary').value ? parseFloat(document.getElementById('measFormValueSecondary').value) : null,
            unit: measFormUnit.value.trim(),
            recorded_date: document.getElementById('measFormDate').value,
            notes: document.getElementById('measFormNotes').value.trim() || null
        };

        try {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';

            await SwasthAPI.family.createMeasurement(payload);
            showAlert('Measurement logged successfully');

            closeModal('measurementModal');
            await loadMemberProfileData(currentMemberId);
        } catch (err) {
            setModalAlert('measurementFormAlert', err.message || 'Failed to save measurement');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Measurement';
        }
    });

    // ==========================================================================
    // INITIALIZATION & REAL-TIME VALIDATION CLEARING
    // ==========================================================================

    function initValidationListeners() {
        document.querySelectorAll('.modal-overlay form').forEach(form => {
            form.querySelectorAll('input, select, textarea').forEach(input => {
                const clearFn = () => {
                    clearFieldError(input.id);
                    const alertEl = form.querySelector('.modal-form-alert');
                    if (alertEl) alertEl.style.display = 'none';
                };
                input.addEventListener('input', clearFn);
                input.addEventListener('change', clearFn);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initValidationListeners();

        const urlParams = new URLSearchParams(window.location.search);
        const memId = urlParams.get('member');
        if (memId) {
            showMemberProfile(memId);
        } else {
            showOverview();
        }
    });

})();