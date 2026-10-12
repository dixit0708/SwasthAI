# Medical Report Analyzer

`POST /api/v1/report-analysis/analyze` (auth required, multipart file upload).

## How it works

Extraction and classification are a fixed, deterministic pipeline —
chosen over an LLM specifically to avoid hallucination risk on the actual
numbers (AGENTS.md Section 11). An LLM is used only for the last step, to
turn those already-correct structured values into a plain-language
explanation — never to do the extraction itself.

**What actually makes this "easier to read" than the raw report** — worth
being explicit about, since the recognized-values list alone is otherwise
just a re-statement of numbers the report already prints. Two things do
the real work: `PARAMETER_DESCRIPTIONS`/`QUALITATIVE_DESCRIPTIONS` in
`lab_report_analysis.py` attach a plain-English "what this measures" line
to every one of the ~53 numeric parameters and 8 screening tests (e.g.
"MCHC" → "How concentrated the hemoglobin is inside your red blood
cells."), shown for every value regardless of status — jargon translation
a raw report never provides. And the frontend groups recognized values by
panel (Complete Blood Count, Lipid Profile, Liver Function, etc. — see
`CATEGORY_LABELS` in `report-analyzer.js`) instead of one flat list in
whatever order OCR happened to encounter them, which matters especially
for a photographed report where the visual layout/columns are lost during
extraction. These descriptions are static and factual (what a test
generally measures — never what a specific result means for the person
who uploaded it), so they carry none of the hallucination risk an LLM
doing this would; the *why does this matter for you* reasoning still only
comes from the LLM explanation step below.

1. **Text extraction** — `backend/app/ai/inference/report_parsing.py` reads
   the uploaded file in memory (never written to disk):
   - A text-based PDF: `pdfplumber` pulls its selectable text directly.
   - A PDF with no selectable text layer (a scanned/photographed PDF): each
     page (capped at `MAX_OCR_PAGES = 5`) is rendered to an image via
     `pdfplumber`'s built-in `page.to_image()` (backed by the already-
     installed `pypdfium2`, no extra dependency) and read the same way an
     image upload is.
   - A JPEG/PNG upload: `app/ai/inference/image_ocr.py` sends it to
     Google's Gemini API (vision input) with a strict "transcribe only,
     verbatim, no commentary" system instruction, and returns the raw text.
     This reuses the same free-tier Gemini API already wired up for the
     explanation step below, rather than adding a Tesseract binary or a
     torch-based OCR library — see the "Known limitations" section for
     what this trades off. **Unlike** the explanation step, OCR is
     *required* for an image upload (there's no rule-based fallback for
     pixels) — a missing key or a failed call fails the request closed,
     with a clear error, rather than silently proceeding with no text.
2. **Value extraction** — `backend/app/ai/inference/lab_report_analysis.py`
   scans the extracted text line by line for a fixed table of **~46 common
   numeric parameters** across CBC (including the full differential and
   red-cell indices), lipid panel, liver panel (LFT), kidney panel
   (KFT, including electrolytes), thyroid panel, glucose/diabetes, iron
   studies, vitamins, and vitals — using regex aliases, and pulls the
   first number found after a match.

   **Panel coverage and where the reference ranges came from** (general
   adult ranges — see the standing caveat in "Known limitations" below;
   sources checked against each other, not taken from a single site,
   after one early source gave an albumin range that turned out to be
   wrong on cross-check):
   | Panel | Parameters | Representative sources |
   |---|---|---|
   | CBC | Hemoglobin, RBC, WBC, Platelets, Hematocrit/PCV, MCV, MCH, MCHC, RDW, ESR, Neutrophils/Lymphocytes/Monocytes/Eosinophils/Basophils (%) | [NCBI StatPearls](https://www.ncbi.nlm.nih.gov/sites/books/NBK604207/), [Medscape MCH/MCHC](https://emedicine.medscape.com/article/2054497-overview), [Medscape MCV](https://emedicine.medscape.com/article/2085770-overview) |
   | Lipid | Total/LDL/HDL Cholesterol, Triglycerides | (unchanged from v1) |
   | Liver (LFT) | ALT/SGPT, AST/SGOT, Total Bilirubin, ALP, GGT, Total Protein, Albumin, Globulin | [Cleveland Clinic](https://my.clevelandclinic.org/health/diagnostics/17662-liver-function-tests), [MedlinePlus](https://medlineplus.gov/lab-tests/total-protein-and-albumin-globulin-a-g-ratio/), [LaboratoryInfo.com](https://laboratoryinfo.com/liver-function-test-lfts/) |
   | Kidney (KFT) | Creatinine, Blood Urea/BUN, Sodium, Potassium, Chloride, Uric Acid | [Metropolis India](https://www.metropolisindia.com/blog/health-wellness/kidney-function-test-purpose-normal-ranges), [Physiopedia](https://www.physio-pedia.com/Renal_Function_Test_(RFT)) |
   | Thyroid | TSH, T3 (Total), T4 (Total), Free T3, Free T4 | [Asian Heart Institute](https://asianheartinstitute.org/blog/tsh-thyroid-test-normal-ranges-for-t3-t4-tsh/), [Testing.com](https://www.testing.com/thyroid-testing-example-results/) |
   | Glucose | Fasting Glucose, HbA1c, Post-Prandial (PP), Random | (unchanged / standard ADA-consistent bands) |
   | Iron studies | Serum Iron, Ferritin, TIBC, Transferrin Saturation | [MSD Manual Professional](https://www.msdmanuals.com/professional/multimedia/table/typical-normal-serum-values-for-iron-iron-binding-capacity-ferritin-and-transferrin-saturation), [University of Iowa Path Handbook](https://www.healthcare.uiowa.edu/path_handbook/handbook/test1151.html) |
   | Vitamins | Vitamin D (25-OH), Vitamin B12 | [WebMD B12](https://www.webmd.com/a-to-z-guides/vitamin-b12-test), [ABIM lab reference ranges](https://www.abim.org/media/e2wdwdqu/laboratory-reference-ranges.pdf) |
   | Vitals | Pulse, Respiratory Rate, Body Temperature, Blood Pressure (systolic/diastolic) | standard AHA-consistent adult resting ranges |

   **Sex-specific ranges were deliberately widened, not picked one-sided.**
   A few values (uric acid, ferritin) have real, clinically different
   normal ranges for men vs. women, but this tool has no patient-sex input
   to key off. Rather than silently applying the male (or female) range to
   everyone, the reference band stored is the union of both commonly-cited
   ranges — trading a little precision (a borderline-abnormal result for
   one sex might read as "normal") for never misclassifying a genuinely
   normal result for the *other* sex as abnormal.

   **Alias collisions were the main hazard in adding ~30 more parameters
   to one flat table**, and are worth knowing about if extending this
   further:
   - **"Free T3"/"Free T4" vs. "T3"/"T4" (Total).** A bare `\bt3\b` alias
     also matches inside "Free T3" — without a guard, the same number
     would get reported twice, once against the Total range (80-220
     ng/dL) and once against the wildly different Free range (2.3-4.2
     pg/mL), producing a false "critically low Total T3" that was never
     actually on the report. Fixed with a negative lookbehind on the
     Total aliases, `(?<!free )\bt3\b` — Python's `re` requires
     fixed-width lookbehind, so this only guards against exactly one
     space before "t3"/"t4", not arbitrary whitespace.
   - **"MCH" vs. "MCHC"** turned out to need no special handling — `\b`
     word boundaries don't occur *inside* an alphanumeric token, so
     `\bmch\b` correctly never matches the "MCH" that's a substring of
     "MCHC". Verified with a test rather than assumed.
   - **"Serum Iron" vs. "Total Iron-Binding Capacity"** — a bare
     `\biron\b` alias would also fire on "...Binding Capacity" lines
     mentioning "Iron". Guarded with a negative lookahead,
     `\biron\b(?!.{0,15}binding)`.

   **Vitals were added after testing against a real general-checkup-style
   report** — a genuinely different document type from a lab panel (no
   blood work at all, just BP/pulse/temperature/respiratory rate and
   clinical notes), which the tool didn't recognize at all before. Two
   things vitals needed that plain lab values didn't:
   - **Comma decimals** — a temperature printed as "36,8 °C" (European-
     style/OCR artifact) needs `,` treated as the decimal separator. This
     is opt-in per parameter (`LabParameter.allow_comma_decimal`, off by
     default) rather than a global change, specifically because a lab
     value like a platelet count can legitimately use a comma as a
     *thousands* separator ("150,000/µL") — treating that as a decimal
     would silently corrupt it.
   - **Blood pressure is a compound reading** (systolic/diastolic, e.g.
     "140/90 mmHg") and doesn't fit one-value-per-parameter, so it has its
     own small extractor (`_extract_blood_pressure`) that produces two
     ordinary recognized values. If a report has a malformed BP line
     (e.g. missing the diastolic number — a real case hit during
     testing), it's simply not recognized rather than guessing a value.

   Separately, `extract_qualitative_results()`
   handles a different report shape: infectious-disease screening panels
   (HIV, Hepatitis B/HBsAg, Syphilis/RPR-VDRL, Hepatitis C, Dengue NS1
   Antigen, Dengue IgM Antibody, Malaria Antigen, COVID-19/SARS-CoV-2)
   reported as Reactive/Non-Reactive or Positive/Negative rather than a
   number. It finds the test's own result within a bounded window of text
   after the test name (cut off at the report's own "Interpretation"
   legend, so a later, unrelated legend row like "Reactive | Indicates
   presence of..." is never mistaken for the patient's actual result), and
   picks whichever of the normal/abnormal wording appears *first* — which
   correctly resolves "Non-Reactive" containing the substring "Reactive",
   since the full "Non-Reactive" match always starts earlier in the text
   than the bare word inside it. HIV/HBsAg/RPR/Hepatitis C were added
   after testing against a real Dr Lal PathLabs report that was entirely
   this test type; Dengue/Malaria/COVID were added afterward from
   researching other common Indian-lab screening panels.

   **Dengue IgG is deliberately excluded, on purpose, not an oversight.**
   Unlike every other test in this table, a reactive Dengue IgG *alone*
   commonly just means a past infection (long-term immunity) rather than
   a current one — a materially less urgent finding.
   `QUALITATIVE_ABNORMAL_NOTICE`'s "contact your doctor promptly,
   confirmatory testing is the standard next step" framing (below) is
   accurate and appropriate for NS1/IgM/every other test here, but would
   misrepresent what a reactive IgG-only result actually means — so rather
   than build (and risk getting wrong) a second, gentler message just for
   this one case, it's simply not recognized yet.
3. **Classification** — each recognized numeric value is compared against a
   general adult reference range and labeled `low` / `normal` / `high`;
   each recognized screening test is labeled `normal` (non-reactive/
   negative) or `abnormal` (reactive/positive).
4. **Rule-based summary** — `backend/app/ai/safety/report_safety.py` turns
   the classified values into a template-generated plain-language summary,
   a short list of follow-up questions grouped by category, and the
   standard non-diagnostic disclaimer (`REPORT_ANALYSIS_DISCLAIMER`). This
   step has no external dependency and always succeeds.

   **A reactive/positive screening result gets distinct, more direct
   wording** (`QUALITATIVE_ABNORMAL_NOTICE`), not the generic "outside
   typical range" phrasing used for numeric values — a reactive HIV/
   Hepatitis B/Syphilis screen carries real urgency (confirmatory testing,
   possibly time-sensitive) that a mildly high cholesterol reading doesn't.
   It's still non-diagnostic (every one of these tests' own report text
   says a screening result alone doesn't confirm anything — the notice
   says the same), but it does directly say "contact your doctor promptly"
   rather than generic "consider discussing at your next visit" language.
   This mirrors the spirit of AGENTS.md Section 47's emergency-detection
   requirement for the (separate, not-yet-built) AI chat feature — user
   safety outranks even the project's own strong anti-alarm-language
   norms here (Section 43's priority order).
5. **LLM explanation (enhancement layer)** —
   `backend/app/ai/inference/report_explanation.py` sends the *already-
   extracted, already-classified* values (never the raw report text) to
   Google's Gemini API (`gemini-3.5-flash-lite`) with a strict system
   instruction enforcing the same non-diagnostic language rules, and
   returns a short, friendlier explanation in `llm_explanation`. Chosen
   over Claude/OpenAI specifically because Gemini has a genuinely free
   tier (Google AI Studio, no billing account) — a real constraint for a
   student project. The `-lite` variant specifically: the newest flagship
   `gemini-3.8-flash` free tier is capped at just 20 requests/day, whereas
   the lite tier has a far more generous free daily quota — worth
   re-checking at aistudio.google.com/apikey's rate-limit page if this
   ever starts failing again. Get a free key there and set
   `GEMINI_API_KEY` in `backend/.env`.

   **Why only structured values, never raw report text, reach the LLM:**
   every value the model sees was produced by step 2 against our own fixed
   parameter table — none of it is copied verbatim from the user's
   uploaded document. This closes off the prompt-injection surface AGENTS.md
   Section 47 warns about almost entirely, since there's no attacker-
   controlled free text in the prompt for hidden instructions to hide in.

   **This step is optional and fails open, never closed:** if
   `GEMINI_API_KEY` is unset, or the call errors, times out, or is safety-
   filtered, `generate_plain_language_explanation()` catches it and returns
   `None` — the endpoint still returns 200 with the rule-based `summary`
   intact. A Gemini outage never breaks report analysis; it only means the
   friendlier explanation is temporarily missing.

Only the structured result (recognized values + summary + explanation) is
persisted, to `medical_reports`, scoped to the uploading user. The raw
file is discarded after the request.

**All of this runs off the event loop via `run_in_threadpool`** (in
`report_analysis_service.py`) — the OCR and explanation calls are
*synchronous* network calls under the hood (the `google-genai` SDK's
default client), and awaiting a blocking call directly inside an `async
def` would freeze FastAPI's single-threaded event loop for every other
in-flight request on the server, not just this one. This was an actual bug
caught by testing (an image upload appeared to hang, and a concurrent
request never started until the first one finished) — fixed by running
both `validate_and_extract_text` and `generate_plain_language_explanation`
through `starlette.concurrency.run_in_threadpool`, the same pattern
`predict.py` already uses for model loading.

## Known limitations (v1)

* **Image analysis is genuinely slow — budget up to a minute or so.** An
  image upload makes two sequential Gemini calls (OCR, then the
  explanation step), both on a free-tier model, and free-tier vision calls
  are slower than free-tier text-only calls. The upload UI sets this
  expectation with a longer-running spinner message rather than the
  PDF path's near-instant one. A text-based PDF is unaffected — no OCR
  call is needed for it.
* **No general unit conversion.** Each parameter assumes one canonical
  unit (see the table in `lab_report_analysis.py`); a report using a
  different unit for the same parameter will either be misclassified or
  not classified. **One specific case is handled, because it's a real bug
  a real report surfaced**: WBC and Platelet Count are near-universally
  printed by modern hematology analyzers as "×10³/µL" (or the numerically
  identical "×10⁹/L") rather than the full absolute count — a report
  printing "5.7" for a genuinely normal 5,700/µL WBC count was being
  compared against a reference range meant for the full count, misreading
  a normal result as "Low". The canonical range for these two parameters
  is now in that same thousands scale to match what real reports actually
  print, with `LabParameter.normalize_if_above` as a safety net: if the
  raw extracted number is implausibly large for the thousands scale (a
  report printing the full absolute count instead), it's divided by 1000
  before classifying, rather than reading as wildly, obviously "High".
  Every other parameter still has this general limitation — a value
  printed in an unexpected unit is silently wrong or unrecognized, not
  auto-converted.
* **Reference ranges are general adult ranges**, not the specific lab's own
  printed range, not age-adjusted, and — for the handful of parameters
  where normal genuinely differs by sex (uric acid, ferritin) — widened to
  cover both rather than picking one (see the value-extraction section
  above). Sources are listed per-panel above; the user's own report is
  always authoritative over this table — the UI and disclaimer say this
  explicitly.
* **Recall, not precision, is the weak point.** Unusual report layouts,
  multi-column PDF tables that don't extract linearly, or parameter names
  not in the alias list will simply not be recognized — the tool says so
  rather than guessing.
* **No "critical value" tier.** Values are only classified normal/low/high
  against a general range, not flagged as clinically urgent — that would
  require validated, per-parameter emergency thresholds this project
  hasn't built or verified. The always-visible safety notice instead
  gives a generic prompt to contact a doctor promptly for new or
  worsening symptoms.
* **Neither the OCR step nor the LLM explanation step has dedicated rate
  limiting or usage monitoring yet** (AGENTS.md Section 47 asks for this on
  the conversational AI feature; the same principle applies here once this
  endpoint sees real traffic). An image upload consumes *two* Gemini
  free-tier requests (OCR + explanation) instead of one, so it burns
  through the shared daily quota faster than a PDF upload. Google's free
  tier itself enforces a daily/per-minute cap — once exceeded, the
  explanation step fails closed to `None` (report analysis still works),
  but OCR failing closed means the image upload itself fails with an
  error, since there's no rule-based fallback for reading pixels.
* **Gemini's own safety filtering can decline a request** (rare, given the
  prompt contains only clinical-sounding structured data) — treated the
  same as any other failure: caught, logged, `None` returned.
* **Qualitative screening coverage is still a fixed list**, now 8 tests
  (HIV, HBsAg, Syphilis/RPR-VDRL, Hepatitis C, Dengue NS1, Dengue IgM,
  Malaria Antigen, COVID-19) rather than the original 4. Notably absent on
  purpose: **Dengue IgG** (see above — different clinical meaning, would
  need its own, gentler message rather than reusing
  `QUALITATIVE_ABNORMAL_NOTICE`), **Widal/typhoid** (reported as a titer
  like "1:160", not Reactive/Non-Reactive — doesn't fit this framework at
  all yet), and **pregnancy/hCG** (a "Positive" result isn't a concerning
  finding the way every other test here is, so it would need a
  third, distinct message tone this project hasn't built). Extend
  `QUALITATIVE_TESTS` the same way if more tests come up — but check the
  clinical framing question first, not just whether it's Reactive/
  Non-Reactive shaped.
* **Numeric coverage now spans ~46 parameters** (was 16) across CBC, LFT,
  KFT, thyroid, glucose, iron studies, vitamins, and vitals — but is still
  a fixed table, not a general-purpose parser. A parameter name/
  abbreviation not in `LAB_PARAMETERS`' aliases, or a panel not covered at
  all (e.g. cardiac markers, urine routine/microscopy, coagulation
  studies/PT-INR), will simply not be recognized.
* **`backend/dump_report_text.py`** is a small local-only diagnostic: it
  prints exactly what `pdfplumber` extracts from a given PDF, with nothing
  sent anywhere. Use it whenever a real report comes back with "couldn't
  recognize any parameters" to see the actual text layout and extend the
  alias/qualitative-test tables to match, the same way this file's
  extraction logic was built.
