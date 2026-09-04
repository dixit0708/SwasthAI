# SWASTHAI — AI AGENT DEVELOPMENT RULES

## 0. HOW THIS FILE WORKS

This is the authoritative instruction file for any AI coding agent (Claude Code, Codex, or otherwise) working in this repository. It applies to every file in this repo unless a more specific instruction file overrides it for a subdirectory.

Section 61 at the end of this file ("Current Implementation Status") reflects what actually exists in the codebase today, as opposed to the target architecture described in the rest of this document. Read Section 61 before assuming a described component already exists — several sections below describe the intended end-state, not the current state.

---

## 1. PROJECT IDENTITY

Project:

**SwasthAI — AI-Powered Personalized Healthcare Ecosystem**

SwasthAI is an AI-powered healthcare platform designed to provide:

* AI-based disease risk assessment
* Medical image analysis
* Medical report understanding
* Personalized health guidance
* Medication management
* Family health management
* Digital medical records
* Doctor discovery
* Appointment scheduling

The platform is intended to evolve into a serious, production-quality healthcare application. It is currently being built as a B.Tech CSE major project, but treat it as a **real healthcare product**, not as a simple college-project demo.

---

# 2. CORE DEVELOPMENT PRINCIPLE

Every implementation must prioritize:

1. Correctness
2. Security
3. Maintainability
4. User experience
5. Accessibility
6. Privacy
7. Modularity
8. Performance
9. Testability
10. Clear documentation

Never sacrifice architecture or security merely to implement something faster.

---

# 3. TECHNOLOGY STACK

Use the following technology stack unless there is a strong technical reason to change it.

### Frontend

* HTML5
* CSS3
* Vanilla JavaScript
* Minimal React only where genuinely necessary

Do NOT convert the entire project to React.

Do NOT introduce Next.js, Vue, Angular, Svelte, or another frontend framework unless explicitly instructed.

Use the existing frontend architecture whenever possible (see `frontend/` — plain HTML pages, `frontend/css/`, `frontend/js/`).

### Backend

* Python
* FastAPI
* Pydantic / pydantic-settings
* Uvicorn
* Motor (async MongoDB driver)
* bcrypt for password hashing, PyJWT for tokens

These are already pinned in `backend/requirements.txt` — check it before adding anything new.

### Database

Primary database:

**MongoDB**

Use MongoDB unless there is a documented architectural reason to migrate to MySQL.

### AI / ML

Python-based:

* scikit-learn
* XGBoost
* TensorFlow/Keras or PyTorch where appropriate
* OpenCV (`opencv-python-headless`) for image preprocessing
* LLM APIs where required

### Testing

* Pytest / pytest-asyncio (already configured — see `backend/pytest.ini`, `backend/tests/`)
* Browser testing where available

---

# 4. REPOSITORY STRUCTURE

Maintain this separation:

```text
swasthAI/
│
├── frontend/
│   ├── assets/            (icons, illustrations, images)
│   ├── css/                (variables.css, layout.css, components.css, per-page css, css/components/)
│   ├── js/                 (per-page js, auth-guard.js, components.js, main.js, site-nav.js)
│   └── *.html               (index, login, register, dashboard, ai-health, doctors, appointments, etc.)
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/   (one router module per resource, e.g. auth.py)
│   │   │       ├── deps.py       (shared FastAPI dependencies — current user, db, etc.)
│   │   │       └── router.py     (aggregates endpoint routers under /api/v1)
│   │   ├── core/            (config.py — settings via pydantic-settings; security.py — hashing/JWT)
│   │   ├── db/               (mongodb.py — connection; repository.py — BaseRepository; collections.py — per-collection repos)
│   │   ├── models/           (Pydantic models, e.g. user.py)
│   │   ├── services/         (business logic layer — CREATE THIS as features grow; do not put business logic in route handlers)
│   │   └── ai/
│   │       ├── models/       (loaders for trained model artifacts)
│   │       ├── inference/    (image_processing.py, and future inference modules)
│   │       └── safety/        (AI safety / non-diagnostic-language checks)
│   │
│   ├── tests/                (test_ai_inference.py, test_security.py, ...)
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── pytest.ini
│   ├── .env                  (never commit — see Section 16)
│   └── .env.example
│
├── ml_pipeline/
│   ├── diabetes/
│   ├── heart/
│   ├── liver/
│   ├── pneumonia/
│   └── skin/
│   (each is currently a placeholder directory — populate per the layout in Section 5 as models are built)
│
├── storage/
│   ├── reports/
│   ├── medical_images/
│   └── prescriptions/
│   (kept in git via .gitkeep only; actual uploaded content is gitignored — see Section 16)
│
├── AGENTS.md
├── README.md
└── .gitignore
```

Do not casually reorganize this structure.

If structural changes are necessary (e.g. introducing `backend/app/services/`), explain why before making major changes, and prefer adding the missing piece over restructuring what already exists.

---

# 5. ML TRAINING VS PRODUCTION INFERENCE

This is a critical architectural rule.

### Training

All offline training must remain inside:

```text
ml_pipeline/
```

Each model must have its own pipeline.

Example:

```text
ml_pipeline/diabetes/
├── data/
│   ├── raw/
│   ├── processed/
│   └── README.md
├── preprocessing.py
├── train.py
├── evaluate.py
├── inference_test.py
└── README.md
```

Training code must NOT be placed inside:

```text
backend/app/
```

### Production inference

Production model loading and inference must remain inside:

```text
backend/app/ai/
```

The backend must consume trained model artifacts (from `backend/app/ai/models/`, loaded once — see Section 35).

Never train a model during an API request.

Never download Kaggle datasets during an API request.

Never perform expensive model training during FastAPI startup.

---

# 6. SWASTHAI AI MODELS

The system currently plans five major AI areas, corresponding to the five `ml_pipeline/` subfolders.

### Structured-data models

1. Diabetes
2. Heart disease
3. Liver disease

Use appropriate machine-learning models.

XGBoost may be used where appropriate, but NEVER assume XGBoost is automatically the best model.

Compare suitable algorithms and select based on validation performance and practical considerations.

### Computer vision models

4. Pneumonia
5. Skin disease

Use CNN-based approaches and appropriate transfer-learning architectures where justified.

OpenCV may be used for image validation and preprocessing.

Important:

**CNN is the model/architecture. OpenCV is a preprocessing/image-processing library.**

Do not confuse the two.

---

# 7. DATASET RULES

Public/Kaggle datasets may be used for research and model development.

Never blindly train on downloaded datasets.

For every dataset:

1. Document source
2. Document dataset license/usage terms where available
3. Preserve original dataset separately
4. Never modify the original raw dataset
5. Create a cleaned/preprocessed copy
6. Check missing values
7. Check duplicates
8. Check invalid records
9. Check class imbalance
10. Check outliers where relevant
11. Check label quality
12. Check possible data leakage
13. Split data correctly
14. Document preprocessing
15. Record final dataset statistics

Recommended structure:

```text
ml_pipeline/<model>/
├── data/
│   ├── raw/
│   ├── processed/
│   └── README.md
├── preprocessing.py
├── train.py
├── evaluate.py
└── README.md
```

Raw datasets must not be committed to Git unless explicitly approved. `.gitignore` already excludes `ml_pipeline/*/data/` and `ml_pipeline/*/models/` — keep it that way.

Large datasets must not be unnecessarily stored inside the repository.

---

# 8. DATA LEAKAGE PREVENTION

This is mandatory.

Never allow:

* test data to influence training
* preprocessing fitted on test data
* duplicated samples across train/test
* patient-level leakage in medical image datasets where patient metadata exists

Fit preprocessing transformations only on training data.

Evaluation must be performed on data not used for model selection/training.

---

# 9. MODEL EVALUATION

Every trained model must have documented evaluation.

Depending on the problem, report:

* Accuracy
* Precision
* Recall
* F1-score
* Macro F1
* ROC-AUC where appropriate
* Confusion matrix
* Per-class metrics

Do not report only accuracy for medical classification tasks.

For imbalanced datasets, pay particular attention to:

* Recall
* Precision
* F1
* Sensitivity
* Specificity

Never fabricate performance metrics.

Never improve metrics artificially.

Never modify evaluation results manually.

---

# 10. MODEL ARTIFACTS

Trained models must be versioned and documented.

Every model should have metadata containing information such as:

```text
model name
model version
dataset version/source
training date
features/input format
preprocessing version
evaluation metrics
limitations
```

Never load an arbitrary `.pkl`, `.h5`, `.keras`, `.pt`, or `.onnx` file without knowing what it contains.

---

# 11. MEDICAL SAFETY

SwasthAI is a healthcare information and decision-support system.

AI output must NEVER be presented as a definitive medical diagnosis.

Use language such as:

* Risk assessment
* AI-generated insight
* Possible concern
* Health information
* Suggested next step

Avoid unsupported statements such as:

* "You definitely have..."
* "You are diagnosed with..."
* "This proves you have..."

Where appropriate, encourage consultation with a qualified healthcare professional.

Never fabricate medical information.

Never invent medical references.

Never create false clinical certainty.

---

# 12. MEDICAL IMAGE PROCESSING

Uploaded medical images should preferably be processed in memory.

Use:

```text
bytes
↓
validation
↓
NumPy buffer
↓
OpenCV decoding
↓
preprocessing
↓
CNN inference
```

Do not permanently write uploaded images to disk unless storage is explicitly required.

Do not use FastAPI-specific objects inside framework-agnostic image-processing services. `backend/app/ai/inference/image_processing.py` is the existing entry point for this — extend it rather than duplicating logic elsewhere.

For example, image-processing functions should preferably accept:

```python
bytes
content_type
```

rather than:

```python
UploadFile
```

FastAPI routers should handle HTTP-specific errors.

---

# 13. BACKEND ARCHITECTURE

Keep these responsibilities separated:

### API layer (`backend/app/api/v1/`)

Handles:

* HTTP requests
* authentication
* validation
* response formatting
* HTTP errors

### Service layer (`backend/app/services/` — to be created)

Handles:

* business logic
* AI orchestration
* database operations
* report processing
* healthcare workflows

This layer does not exist yet in the repo. As soon as a route handler needs more than trivial logic, create `backend/app/services/` and move that logic there instead of growing the route handler.

### AI layer (`backend/app/ai/`)

Handles:

* model loading
* preprocessing
* inference
* prediction post-processing
* AI safety checks

### Database layer (`backend/app/db/`)

Handles:

* MongoDB connection (`mongodb.py`)
* repositories (`repository.py`, `collections.py`)
* CRUD operations
* database queries

Do not place all logic inside FastAPI route functions.

---

# 14. DATABASE RULES

Use MongoDB with clear collection boundaries.

Core collections (already scaffolded as repositories in `backend/app/db/collections.py`):

```text
users
health_profiles
family_members
medical_records
medical_reports
predictions
health_metrics
health_goals
medications
notifications
doctors
appointments
ai_conversations
audit_logs
```

Every user-owned record must have proper ownership/access control.

Never allow:

```text
GET /records/{id}
```

to return another user's record merely because the ID is known.

Always validate authorization.

Use timestamps where appropriate:

```text
created_at
updated_at
```

---

# 15. AUTHENTICATION & SECURITY

Authentication must use secure practices. `backend/app/core/security.py` is the existing home for hashing/JWT logic — extend it rather than reimplementing elsewhere.

Never:

* store plaintext passwords
* expose secrets in frontend code
* commit `.env`
* hardcode API keys
* expose MongoDB credentials
* expose private medical records
* trust user-supplied user IDs without authorization checks

Use:

* secure password hashing (bcrypt)
* JWT/session authentication as appropriate (PyJWT)
* environment variables
* authorization checks
* input validation
* rate limiting where appropriate
* secure CORS configuration
* audit logging for sensitive operations

---

# 16. ENVIRONMENT VARIABLES

Never hardcode:

* database credentials
* API keys
* JWT secrets
* LLM API keys
* production URLs containing secrets

Use:

```text
backend/.env
```

and keep `backend/.env.example` up to date whenever a new variable is introduced.

`backend/.env` is already gitignored (`.env`, `.env.*`, with `!.env.example` excepted) — do not change that.

If `.env` is accidentally detected as tracked/staged, stop and notify the developer.

---

# 17. FRONTEND RULES

The frontend must remain user-centered.

The user should never need to understand:

* CNN
* XGBoost
* ML pipeline
* model architecture
* API implementation

Use patient-friendly terminology. The existing pages already follow this (e.g. `ai-health.html`, `health-insights.html` rather than raw model names).

For example:

Instead of:

```text
Disease Prediction
```

prefer:

```text
AI Health Insights
```

Instead of:

```text
XGBoost Diabetes Model
```

use:

```text
Diabetes Risk Assessment
```

---

# 18. PUBLIC WEBSITE NAVIGATION

Public navigation should remain minimal:

```text
Home
How It Works
Services
About
```

Actions:

```text
Login
Get Started
```

Do not overload the public navigation with application features.

---

# 19. AUTHENTICATED APPLICATION NAVIGATION

Logged-in users should see:

```text
Dashboard
My Health
AI Insights
Family
Doctors
```

And:

```text
Notifications
Profile
```

Do not add unnecessary navigation items.

---

# 20. MY HEALTH

My Health should contain:

### Health Profile

* Age
* Gender
* Height
* Weight
* Blood group
* Existing conditions
* Allergies
* Lifestyle information

### Medical History

* Previous conditions
* Past treatments
* Relevant medical history

### Medications

* Current medicines
* Dosage
* Schedule
* Medication reminders

### Health Goals

* Wellness goals
* Goal progress
* Personalized recommendations

Do NOT add generic wearable-style tracking unless explicitly implemented.

Do not invent:

* heart-rate dashboards
* sleep dashboards
* glucose graphs
* blood-pressure graphs
* wearable integrations

---

# 21. AI INSIGHTS

AI Insights may contain:

### Disease Risk

* Diabetes
* Heart disease
* Liver disease

### Medical Image Analysis

* Pneumonia
* Skin disease

### Medical Report Analyzer

* Report upload
* Parameter extraction
* Abnormal-value identification
* Plain-language explanation

### Personalized Recommendations

Where implemented:

* Diet
* Exercise
* Lifestyle
* Preventive guidance

---

# 22. FAMILY HEALTH

Family functionality must maintain separate profiles and permissions.

Support:

* Add family member
* Family profile
* Medical history
* Medical records
* Reports
* Medications
* Relevant AI insights

Never expose private information across family accounts without explicit authorization.

---

# 23. DOCTOR MODULE

Doctors functionality may include:

* Doctor discovery
* Specialty filtering
* Doctor profiles
* Availability
* Appointment scheduling
* Appointment management

Never fabricate real doctors or appointments.

If backend data does not exist, use a clear product empty state.

---

# 24. UI/UX QUALITY

The interface should feel:

**Premium · Modern · Trustworthy · Calm · Human · Intelligent**

Use:

* strong typography
* generous whitespace
* clear hierarchy
* subtle motion
* polished hover states
* responsive design
* accessible interactions

Avoid:

* excessive gradients
* excessive glassmorphism
* neon effects
* excessive animations
* generic Bootstrap styling
* unnecessary cards
* clutter

---

# 25. ANIMATION RULES

Animation is encouraged when it improves UX.

Use subtle motion for:

* page entrance
* navigation
* dropdowns
* mobile menus
* buttons
* cards
* active states

If React is already used, Framer Motion may be used selectively.

Since this project is Vanilla HTML/CSS/JS, prefer:

* CSS transitions
* CSS keyframes
* lightweight JavaScript

Do NOT convert the entire project to React merely to use Framer Motion.

Always respect:

```text
prefers-reduced-motion
```

---

# 26. RESPONSIVE DESIGN

Every frontend change must be checked at:

```text
320px
375px
425px
768px
1024px
1280px
1440px
1920px
```

Never solve responsive problems simply by hiding important content.

Avoid:

* horizontal overflow
* squeezed buttons
* unreadable text
* inaccessible menus
* tiny touch targets

---

# 27. ACCESSIBILITY

Use:

* semantic HTML
* proper headings
* accessible labels
* keyboard navigation
* visible focus states
* sufficient contrast
* ARIA only when necessary
* reduced-motion support

Interactive elements must be keyboard accessible.

Target **WCAG 2.1 AA** as the minimum bar for any patient-facing screen. When a component cannot reasonably meet AA (e.g. a complex chart), provide an accessible text-based alternative alongside it.

---

# 28. API INTEGRATION

Frontend and backend communication must be explicit and modular.

Do not scatter API URLs throughout HTML files.

Prefer a centralized configuration/API utility (introduce one in `frontend/js/` if it doesn't already exist, and reuse it from every page's JS file rather than hardcoding base URLs).

Development:

```text
Frontend
http://localhost:5500 (or the configured static server / Vercel preview)

Backend
http://127.0.0.1:8000
```

API integration must handle:

* loading
* success
* errors
* empty states
* authentication failures
* network failures

Never silently fail.

---

# 29. PLACEHOLDER / UNAVAILABLE FEATURES

Some features may be developed in phases. Several backend features (predictions, medical records, family, doctors, appointments, AI insights) are not implemented yet — only auth exists today (see Section 61).

When backend functionality does not yet exist:

DO:

```text
Design the UI
Create appropriate empty states
Create loading states
Prepare API integration boundaries
```

DO NOT:

* fabricate AI results
* fabricate patient data
* fabricate doctors
* fabricate appointments
* fabricate medical reports
* fabricate notifications

User-facing copy should remain professional.

Do not write:

```text
Dummy
Fake
College Project
Backend Pending
```

---

# 30. FILE MODIFICATION RULES

Before modifying a file:

1. Inspect it.
2. Understand its dependencies.
3. Search for usages.
4. Determine whether other pages depend on it.
5. Make the smallest appropriate change.

Do not rewrite entire files unnecessarily.

Do not delete files unless they are demonstrably obsolete.

Before deleting anything, verify:

* no imports
* no references
* no routes
* no scripts
* no build/deployment dependency

---

# 31. DEPENDENCY RULES

Do not install dependencies casually.

Before adding a package:

1. Check whether existing dependencies already solve the problem (check `backend/requirements.txt` first).
2. Check whether the functionality can be implemented without it.
3. Consider bundle/environment size.
4. Consider maintenance.
5. Consider security.
6. Explain the reason.

Never add a large framework for a small feature.

---

# 32. TESTING

Every significant backend feature should have tests. `backend/tests/` already has `test_ai_inference.py` and `test_security.py` as the pattern to follow.

Test:

* validation
* authentication
* authorization
* API responses
* database behavior
* AI inference boundaries
* error handling

For AI:

* valid input
* invalid input
* missing features
* malformed image
* unsupported file type
* large files
* model loading failure
* inference failure

---

# 33. LOGGING

Logs must be useful but must not expose sensitive information.

Never log:

* passwords
* API keys
* JWT secrets
* complete medical reports
* unnecessary personal health information

Use appropriate log levels.

---

# 34. ERROR HANDLING

Never hide exceptions silently.

Return meaningful errors.

Frontend should show user-friendly messages.

Backend should log technical details appropriately.

Do not expose internal stack traces to users in production.

---

# 35. PERFORMANCE

Prefer:

* lazy loading where useful
* optimized images
* efficient database queries
* model loading once rather than per request
* minimal frontend JavaScript
* caching where appropriate

Do not optimize prematurely.

Measure before making complicated performance changes.

---

# 36. DOCUMENTATION

Every major feature should be documented.

AI modules should document:

* dataset
* preprocessing
* model
* training
* evaluation
* limitations
* inference input/output

Backend modules should document:

* endpoint
* request
* response
* authentication requirements
* errors

---

# 37. GIT RULES

Git operations require special care.

The AI agent must NOT:

* push automatically
* force push
* reset the repository destructively
* delete branches
* rewrite history
* amend commits
* modify remote configuration

Unless explicitly instructed by the developer.

Before recommending a commit:

```text
git status
git diff
```

must be checked.

Never commit:

```text
.env
venv/
__pycache__/
.pytest_cache/
large datasets
temporary files
credentials
API keys
secrets
```

The agent must never run:

```text
git push
```

unless the developer explicitly requests it.

---

# 38. DO NOT DESTROY USER WORK

This is one of the highest-priority rules.

Never:

* overwrite user changes without inspection
* delete working code without justification
* replace the architecture unnecessarily
* reset the repository to an earlier state
* discard uncommitted changes

If unexpected changes are found, STOP and report them before overwriting them.

---

# 39. BEFORE IMPLEMENTING A FEATURE

Follow this workflow:

```text
Understand
    ↓
Inspect existing code
    ↓
Identify dependencies
    ↓
Plan minimal changes
    ↓
Implement
    ↓
Test
    ↓
Review
    ↓
Document
```

Do not immediately start editing files without understanding the existing implementation.

---

# 40. AFTER IMPLEMENTATION

Always perform:

```text
Syntax check
↓
Tests
↓
Lint/static checks where available
↓
Browser/UI check where applicable
↓
Console error check
↓
Review changed files
```

Then provide a concise report:

```text
Files changed:
Features implemented:
Tests performed:
Issues found:
Backend dependencies:
Remaining work:
```

---

# 41. AGENT COMMUNICATION RULE

Do not ask unnecessary questions.

If the requirement is sufficiently clear:

**Implement it.**

If there are multiple reasonable approaches:

**Choose the simplest architecture-compatible approach and explain the decision.**

Ask for clarification only when proceeding would risk:

* data loss
* security
* architectural damage
* irreversible changes
* significant scope changes

---

# 42. NO OVER-ENGINEERING

Do not implement enterprise complexity unless the project actually needs it.

Prefer:

```text
Simple
Modular
Readable
Testable
Secure
```

over:

```text
Complex
Over-abstracted
Over-engineered
```

The goal is a strong B.Tech major project with genuine engineering quality.

---

# 43. FINAL RULE (PRIORITY ORDER)

When uncertain, prioritize:

```text
User safety
>
Security
>
Correctness
>
Architecture
>
Maintainability
>
UX
>
Performance
>
Convenience
```

Never compromise medical safety or security to make a feature appear complete.

The agent must treat this repository as a continuously evolving healthcare product and preserve the architecture and decisions documented in this file.

---

# 44. REGULATORY & COMPLIANCE CONTEXT

SwasthAI handles sensitive personal health data. Even as a student project, build as if compliance mattered, because the architecture will carry forward.

Be aware of, and design toward, principles from:

* **India's Digital Personal Data Protection Act (DPDP), 2023** — lawful purpose, consent, data minimization, breach notification, right to correction/erasure.
* **Ayushman Bharat Digital Mission (ABDM)** conventions, if/when integrating with Indian health-ID infrastructure (e.g. ABHA-style identifiers) — do not fabricate integration; document it as a future-phase item.
* General health-data best practices analogous to HIPAA (access control, audit trails, encryption in transit/at rest) as an engineering discipline, not a legal claim of certification.

Never claim the app is "HIPAA compliant," "DPDP certified," or similar in user-facing copy unless this has actually been verified by the developer. State capabilities factually (e.g. "your data is encrypted and access-controlled").

---

# 45. CONSENT MANAGEMENT

Any collection, storage, or AI processing of health data must be tied to explicit user consent.

Required:

* Consent must be captured at signup and at first use of each sensitive feature (e.g. uploading a medical image, adding a family member's records).
* Consent state must be stored per user (e.g. `consent_flags` on the user or a `consents` collection) with a timestamp and version of the terms accepted.
* Family member profiles added by a primary account holder must be clearly marked as "managed by" that account, since the family member has not personally consented.
* Users must be able to view and revoke consent from their profile settings.

Never process a new category of sensitive data (e.g. genetic info, mental health data) under a consent scope that didn't cover it.

This is not implemented yet (see Section 61) — build it in as the `users` model and registration flow mature, not bolted on afterward.

---

# 46. DATA RETENTION & DELETION

* Provide a "delete my account" flow that removes or irreversibly anonymizes personal health data, not just the login credentials.
* Deletion requests must cascade correctly across `users`, `health_profiles`, `family_members`, `medical_records`, `medical_reports`, `predictions`, `medications`, and `ai_conversations` — do not leave orphaned personally identifiable data.
* Distinguish between **soft delete** (recoverable, short grace period) and **hard delete** (permanent, after grace period or explicit confirmation). Document which is used where.
* `audit_logs` may retain minimal non-content metadata (e.g. "record X deleted at time Y") for integrity purposes even after the underlying record is gone — never retain the medical content itself for this purpose.
* Backups containing deleted user data must age out on a documented schedule; do not treat backups as a loophole around deletion requests.

---

# 47. AI CONVERSATION & CHATBOT SAFETY

The `ai_conversations` collection implies a conversational AI feature (`frontend/ai-assistant.html` / `frontend/js/ai-assistant.js` already exist on the frontend as the intended UI for this). This carries additional, specific risk beyond the structured-data risk models.

Mandatory rules for any AI chat/report-explainer feature:

* **Emergency detection**: if a user's message indicates a potential medical emergency (e.g. chest pain, difficulty breathing, severe bleeding, stroke symptoms, suicidal ideation or self-harm intent), the response must not attempt further diagnosis or casual conversation. It must clearly and immediately direct the user to emergency services or a crisis helpline, in plain language, before anything else.
* Never let the AI conversation feature attempt to talk a user out of seeking emergency or professional care.
* Apply the same non-diagnostic language rules from Section 11 inside chat responses — a conversational tone does not relax the "never present as definitive diagnosis" rule.
* Treat the LLM prompt/context for this feature as untrusted-adjacent: sanitize what's inserted from user-uploaded report text before it reaches the model, and do not let uploaded document content override system instructions (basic prompt-injection hygiene).
* Log conversation metadata for safety auditing (e.g. "emergency-pattern flagged"), but avoid persisting full free-text emergency-related messages longer than necessary — see Section 33 on sensitive logging.
* Rate-limit and monitor this feature separately from other API routes; it is a more expensive and more misuse-prone surface than the structured-data endpoints.

---

# 48. FILE UPLOAD SECURITY

For medical images, reports, and prescriptions uploaded through the platform (destined for `storage/medical_images/`, `storage/reports/`, `storage/prescriptions/`):

* Enforce a maximum file size per upload type and reject oversized files with a clear error, not a silent failure.
* Validate MIME type and file signature (not just the file extension) before processing.
* Reject or safely handle unsupported/malformed files rather than passing them into OpenCV/CNN pipelines unguarded.
* Strip or ignore embedded metadata (e.g. EXIF GPS data in photos) that isn't needed, since it can leak location information.
* If files are persisted to `storage/`, treat that directory as containing sensitive data: apply the same access-control rules as database records (Section 14) — a stored file path must never be guessable or served without an authorization check.
* Do not execute, evaluate, or render uploaded file contents as code under any circumstance.

---

# 49. API DESIGN CONVENTIONS

To keep a large FastAPI backend consistent as it grows:

* Use a consistent response shape across endpoints, e.g. `{ "success": bool, "data": ..., "error": ... }` or FastAPI's native model-based responses — pick one convention, document it in `backend/README.md` (create it if it doesn't exist), then keep it uniform.
* Use standard HTTP status codes correctly (200/201 for success, 400 for validation errors, 401/403 for auth, 404 for missing resources, 429 for rate limits, 500 only for genuine server faults).
* The API is already versioned via `backend/app/api/v1/` (mounted under `/api/v1/...`) — keep using this pattern for future versions rather than a big-bang migration.
* Paginate any list endpoint that can grow unbounded (medical records, notifications, appointments) — never return an entire collection in one response.
* Keep request/response Pydantic models explicit; avoid returning raw MongoDB documents (which may include internal fields) directly to the client.

---

# 50. CODE STYLE & LINTING

* Python: format with **Black**, sort imports with **isort**, lint with **flake8** or **ruff**. Type-hint public functions where practical.
* JavaScript: keep a consistent style (Prettier config recommended even without a build step) and avoid mixing formatting conventions across files.
* Keep functions and modules focused — prefer several small, named functions in the service layer over one large route handler.
* Run available linters/formatters as part of the "after implementation" checklist in Section 40, not just tests.

---

# 51. GIT WORKFLOW & COMMIT CONVENTIONS

* Use short-lived feature branches named descriptively (e.g. `feature/diabetes-risk-model`, `fix/report-upload-validation`), not direct commits to `main` for anything non-trivial.
* Write commit messages that describe the change and why, e.g. `feat(ai): add liver disease risk endpoint` — a lightweight conventional-commits style (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`) is encouraged but not mandatory.
* Keep commits scoped to one logical change where practical, rather than bundling unrelated fixes together.
* This section operates within, and does not relax, the Git restrictions already defined in Section 37.

---

# 52. CI, DEPENDENCY SECURITY & VULNERABILITY CHECKS

* If a CI pipeline exists (GitHub Actions or similar), it should at minimum run: tests, linting, and a dependency vulnerability scan (e.g. `pip-audit` for Python, `npm audit` for any Node tooling). No CI pipeline exists in this repo yet.
* Before adding a new dependency (per Section 31), also check it for known vulnerabilities and recent maintenance activity.
* Do not silence or bypass a failing security check to merge faster; report it to the developer instead.

---

# 53. MONITORING & HEALTH CHECKS

* A `/health` endpoint already exists on the backend (see `backend/app/main.py`, reachable at `http://127.0.0.1:8000/health`) — keep it reporting service and database connectivity without leaking internal details (stack traces, config values).
* Log key operational events (startup, model load success/failure, DB connection loss) at appropriate levels per Section 33.
* Prefer structured logging (consistent fields like `timestamp`, `level`, `route`, `user_id_hash`) over ad hoc print statements, to make future debugging and audit review tractable.

---

# 54. SECRETS ROTATION & BACKUP STRATEGY

* Treat all secrets in `backend/.env` as rotatable: do not hardcode assumptions (e.g. token lifetimes, key formats) that would break if a secret were rotated.
* If/when the project has a real deployment, document a MongoDB backup schedule and periodically verify that a backup can actually be restored — an untested backup is not a backup.
* Backups must be stored with the same access-control rigor as the live database (Section 15), since a backup file is a full copy of sensitive data.

---

# 55. SESSION & TOKEN MANAGEMENT

* Access tokens should be short-lived; use a refresh-token pattern rather than long-lived access tokens where session persistence is needed.
* Invalidate sessions/tokens on password change and on explicit logout.
* Never store JWTs or session tokens in a way accessible to injected scripts (prefer httpOnly cookies over `localStorage` where feasible for this stack). Check `frontend/js/auth.js` and `frontend/js/auth-guard.js` before changing how tokens are stored client-side.

---

# 56. NOTIFICATIONS & PRIVACY

* Notification content (email, SMS, push) that references health information must be minimal — e.g. "You have a new report ready to view" rather than including diagnostic details in the notification body itself.
* Respect user notification preferences; provide a way to opt out of non-critical notifications.

---

# 57. LOCALIZATION (FUTURE-READY, NOT REQUIRED YET)

* Avoid hardcoding user-facing strings in a way that would block future Hindi/regional-language support (e.g. prefer centralizing UI copy over scattering literals across many files), even though full i18n is not required for the current phase.
* Keep medical units and formats (height, weight, date formats) clearly labeled, since Indian users may expect metric units by default.

---

# 58. MODEL FAIRNESS

* When evaluating structured-data models (Section 9), check performance across available demographic slices (e.g. age group, gender) where the dataset supports it, not just aggregate metrics.
* Document any known dataset imbalance that could bias predictions for underrepresented groups, in the model's README (Section 10).
* Do not present a risk score as equally reliable across populations the training data barely covered — note this as a stated limitation.

---

# 59. INCIDENT RESPONSE (LIGHTWEIGHT)

If a security or data issue is discovered while working (e.g. an exposed credential, an authorization bypass, a bug that returned another user's data):

1. Stop further related changes.
2. Report the issue to the developer immediately and clearly, including scope (what data/users could have been affected).
3. Do not attempt to silently patch and hide evidence of the issue — document what happened and what was fixed.
4. Do not push a fix without the developer's awareness, per Section 37.

---

# 60. DEFINITION OF DONE

A feature is not complete until:

* It matches the architecture and terminology rules in this file.
* Tests exist and pass for the relevant layer(s) (Section 32).
* Errors are handled per Section 34, not silently swallowed.
* No secrets, medical content, or PII appear in logs (Section 33) or commits (Section 37).
* Responsive and accessibility checks have been considered for any UI change (Sections 26–27).
* The Section 40 post-implementation report has been produced.

This section does not replace the reporting workflow in Section 40 — it is the checklist that report is verifying against.

---

# 61. CURRENT IMPLEMENTATION STATUS

This section exists so an agent doesn't assume a described component is already built. Update it whenever a major piece described elsewhere in this file actually lands.

**Backend — implemented:**
* FastAPI app skeleton (`backend/app/main.py`), `/health` endpoint.
* API versioning scaffold: `backend/app/api/v1/router.py`, `deps.py`.
* Auth endpoint: `backend/app/api/v1/endpoints/auth.py` (register/login-style flow, bcrypt + JWT — this is the only endpoint module that exists).
* Core: `backend/app/core/config.py` (pydantic-settings), `backend/app/core/security.py` (hashing/JWT).
* DB layer: `backend/app/db/mongodb.py` (connection), `backend/app/db/repository.py` (`BaseRepository`), `backend/app/db/collections.py` (all 14 collection repositories from Section 14 are already scaffolded, instantiated and ready to use even though most have no endpoints yet).
* Models: `backend/app/models/user.py` only.
* AI scaffolding: `backend/app/ai/models/`, `backend/app/ai/inference/image_processing.py`, `backend/app/ai/safety/` exist as empty/near-empty packages — no trained models are loaded yet.
* Tests: `backend/tests/test_ai_inference.py`, `backend/tests/test_security.py`.

**Backend — not yet implemented:**
* `backend/app/services/` (service layer) does not exist yet — create it per Section 13 as soon as a route needs non-trivial business logic.
* No endpoints yet for health profiles, family members, medical records/reports, predictions, health metrics/goals, medications, notifications, doctors, appointments, AI conversations, or audit logs, despite their repositories already existing.
* No trained ML/CNN model artifacts are loaded or served yet.
* Consent management (Section 45) and account-deletion cascade (Section 46) are not implemented.
* No CI pipeline exists yet (Section 52).

**ML pipeline:**
* `ml_pipeline/diabetes/`, `heart/`, `liver/`, `pneumonia/`, `skin/` are currently placeholder/empty directories — no training scripts, data, or model artifacts exist yet. Follow the Section 5/7 layout when populating each.

**Frontend — implemented:**
* Full static HTML page set already exists for the planned surface area: landing/marketing pages (`index.html`, `about.html`, `features.html`, `how-it-works.html`), auth pages (`login.html`, `register.html`, `forgot-password.html`), and authenticated app pages (`dashboard.html`, `ai-health.html`, `ai-assistant.html`, `health-insights.html`, `health-profile.html`, `health-tracking.html`, `diet-lifestyle.html`, `medical-records.html`, `medications.html`, `family.html`, `doctors.html`, `doctor-profile.html`, `appointments.html`, `predictions.html` plus per-disease `prediction-*.html` pages, `report-analyzer.html`), plus `privacy.html`/`terms.html`.
* Corresponding JS modules exist per page under `frontend/js/`, plus shared `auth.js`, `auth-guard.js`, `components.js`, `main.js`, `site-nav.js`.
* Styling is organized under `frontend/css/` with `variables.css`, `layout.css`, `typography.css`, `responsive.css`, `components.css` (+ `css/components/`), and per-page stylesheets.
* Because most backend endpoints don't exist yet, most of these pages are necessarily working against empty states, local/mock-free placeholders, or partial API integration — per Section 29, do not fabricate data to make them look more complete than the backend supports.

**Infra:**
* `docker-compose.yml` exists at the repo root (verify its services before assuming what it runs).
* `frontend/.vercel/` indicates the frontend is deployed via Vercel; treat `frontend/.env.local` and `backend/.env` as environment-specific and never commit real values.
