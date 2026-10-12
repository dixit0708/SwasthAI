"""
One-off local diagnostic: prints exactly what the report analyzer's own
text-extraction pipeline (PDF via pdfplumber, image/scanned-PDF via Gemini
OCR) produces for a given file, plus which lab parameters it recognized in
that text. Nothing is sent anywhere except the file itself to Gemini, the
same as a real upload would — run this locally and paste back the printed
output (redact your name/DOB/ID first; keep the test names/values/lines
as-is).

Usage (run from the backend/ directory, same as the server itself — the
.env file is loaded relative to the current working directory, so running
this from the repo root won't find GEMINI_API_KEY and OCR will fail):
    cd backend
    ../venv/Scripts/python.exe dump_report_text.py path/to/report.pdf
    ../venv/Scripts/python.exe dump_report_text.py path/to/photo.jpg
"""
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.ai.inference.lab_report_analysis import extract_lab_values, extract_qualitative_results
from app.ai.inference.report_parsing import validate_and_extract_text

if len(sys.argv) != 2:
    print("Usage: python dump_report_text.py <path-to-file>")
    sys.exit(1)

path = sys.argv[1]
content_type, _ = mimetypes.guess_type(path)
if content_type is None:
    print(f"Could not guess a content type for {path}")
    sys.exit(1)

with open(path, "rb") as f:
    contents = f.read()

print(f"content_type: {content_type}")
print("Extracting text (this calls Gemini OCR for an image/scanned PDF, same as a real upload)...")
print()

try:
    text = validate_and_extract_text(contents, content_type)
except ValueError as e:
    print(f"EXTRACTION FAILED: {e}")
    sys.exit(1)

print("--- extracted text ---")
print(text)
print()

numeric = extract_lab_values(text)
qualitative = extract_qualitative_results(text)

print(f"--- recognized numeric parameters: {len(numeric)} ---")
for v in numeric:
    print(" -", v["key"], v["label"], v["value"], v["unit"])

print(f"--- recognized qualitative tests: {len(qualitative)} ---")
for q in qualitative:
    print(" -", q["key"], q["label"], q["status"])
