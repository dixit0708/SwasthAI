"""
OCR for scanned/photographed lab report images (JPEG/PNG), via Google's
Gemini API vision input — the same free-tier API already used for the
report analyzer's plain-language explanation step
(app/ai/inference/report_explanation.py), reused here for perception
rather than summarization: this call's only job is a literal transcription
of visible text, never interpretation.

Unlike report_explanation.py's LLM step (an optional enhancement that
fails open to None), OCR is *required* for an image upload — there is no
rule-based fallback for pixels. If GEMINI_API_KEY isn't configured, or the
call fails, image uploads fail closed with a clear error rather than
silently proceeding with no text (AGENTS.md Section 34): the caller must
tell the user image support isn't available right now, not pretend the
image was empty.

Output is still just plain extracted text, fed into the exact same
deterministic lab_report_analysis.py pipeline used for PDF text — this
step's LLM involvement is reading pixels, not interpreting medical
content, so it doesn't reintroduce the hallucination risk AGENTS.md
Section 11 asks to avoid for the actual value extraction/classification.
"""
from app.core.config import settings

MODEL_NAME = "gemini-3.5-flash-lite"

SUPPORTED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/jpg")
MAX_FILE_SIZE_MB = 15
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

OCR_SYSTEM_INSTRUCTION = (
    "You transcribe text from images of medical lab reports. Output only the "
    "text visible in the image, verbatim, preserving line breaks as closely "
    "as the layout allows. Do not summarize, explain, interpret, correct, or "
    "add anything not visible in the image. If no text is visible, output "
    "nothing."
)


def extract_text_from_image(contents: bytes, content_type: str) -> str:
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(
            "Unsupported file type. Please upload a PDF, or a JPEG/PNG photo or scan "
            "of your report."
        )

    if not contents:
        raise ValueError("File contents are empty.")

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")

    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "Image-based report scanning isn't available right now. Please upload a "
            "text-based PDF report instead."
        )

    from google import genai
    from google.genai import types

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=contents, mime_type=content_type),
                "Transcribe all visible text from this lab report image.",
            ],
            config=types.GenerateContentConfig(
                system_instruction=OCR_SYSTEM_INSTRUCTION,
                temperature=0.0,
                max_output_tokens=4000,
            ),
        )
    except Exception as e:
        raise ValueError(
            "Couldn't read text from this image right now. Please try again, or upload "
            "a text-based PDF instead."
        ) from e

    text = (response.text or "").strip()
    if not text:
        raise ValueError(
            "No text could be read from this image. Please make sure the photo is clear "
            "and well-lit, or upload a text-based PDF instead."
        )
    return text
