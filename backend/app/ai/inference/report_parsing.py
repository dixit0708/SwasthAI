"""
Framework-agnostic extraction of text from an uploaded lab report — a
text-based PDF via pdfplumber, or a JPEG/PNG photo/scan via Gemini OCR
(app/ai/inference/image_ocr.py, since a scanned image has no selectable
text for pdfplumber to find). Runs entirely in memory (AGENTS.md Section
12) — the uploaded file is never written to disk, here or by any caller.

`validate_and_extract_text` is the single entry point the service layer
calls regardless of which format was uploaded; it dispatches to the image
path first (a separate module, since OCR is a fundamentally different,
LLM-backed operation with its own required-vs-optional failure semantics —
see image_ocr.py's docstring) and otherwise handles PDFs itself.
"""
from io import BytesIO

import pdfplumber

from app.ai.inference.image_ocr import SUPPORTED_IMAGE_TYPES, extract_text_from_image
from app.core.config import settings

SUPPORTED_PDF_TYPES = ("application/pdf",)
MAX_FILE_SIZE_MB = 15
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
# Bounds parsing time for a pathological multi-hundred-page upload.
MAX_PAGES = 15
# A scanned PDF with no text layer falls back to OCR-ing each page as an
# image — a separate Gemini call per page, so capped tighter than
# MAX_PAGES. Most lab reports needing this path are 1-2 pages.
MAX_OCR_PAGES = 5


def validate_and_extract_text(contents: bytes, content_type: str) -> str:
    if content_type in SUPPORTED_IMAGE_TYPES:
        return extract_text_from_image(contents, content_type)

    if content_type not in SUPPORTED_PDF_TYPES:
        raise ValueError(
            "Unsupported file type. Please upload a PDF, or a JPEG/PNG photo or scan "
            "of your report."
        )

    if not contents:
        raise ValueError("File contents are empty.")

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")

    try:
        with pdfplumber.open(BytesIO(contents)) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                raise ValueError(f"PDF has too many pages. Maximum supported is {MAX_PAGES} pages.")
            text_parts = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(text_parts).strip()
            if not text:
                text = _ocr_scanned_pdf(pdf)
    except ValueError:
        raise
    except Exception:
        raise ValueError(
            "Could not read this PDF. It may be corrupted or password-protected."
        )

    if not text:
        raise ValueError(
            "No text could be found in this PDF, even after attempting to read it as a "
            "scanned document. Please try a clearer scan, or a text-based PDF export."
        )
    return text


def _ocr_scanned_pdf(pdf) -> str:
    """No selectable text layer — likely a scanned/photographed PDF rather
    than a digital export. Renders each page as an image and reads it the
    same way a direct JPEG/PNG upload would be (image_ocr.py).
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "No selectable text was found in this PDF, and reading it as a scanned "
            "document isn't available right now. Please upload a text-based PDF, or a "
            "clearer JPEG/PNG photo of the report."
        )

    page_texts = []
    last_error = None
    for page in pdf.pages[:MAX_OCR_PAGES]:
        buf = BytesIO()
        page.to_image(resolution=200).original.save(buf, format="PNG")
        try:
            page_texts.append(extract_text_from_image(buf.getvalue(), "image/png"))
        except ValueError as e:
            last_error = e
            continue

    text = "\n".join(page_texts).strip()
    if not text and last_error:
        raise last_error
    return text
