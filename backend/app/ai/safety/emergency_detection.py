"""Emergency detection for the AI Health Assistant (AGENTS.md Section 47).

Runs in code, before any LLM call. If a message looks like a medical
emergency or mentions self-harm, the assistant must not chat or attempt an
assessment: it returns a fixed response that points to emergency services
first. A system-prompt instruction alone is not a safety control, because
the model may not follow it and the call may fail or time out.

The patterns are deliberately broad. A false positive costs the user one
extra message; a false negative could delay emergency care.
"""
import re
from typing import Optional

MEDICAL_EMERGENCY = "medical_emergency"
SELF_HARM = "self_harm"

_SELF_HARM_PATTERNS = [
    r"\bsuicid\w*",
    r"\bkill(ing)? (myself|my ?self)\b",
    r"\bend(ing)? (my|this) life\b",
    r"\b(want|wish|going|plan\w*) to die\b",
    r"\bdon'?t want to (live|be alive)\b",
    r"\bno reason to live\b",
    r"\bself[\s-]?harm\w*",
    r"\b(hurt|harm|cut)(ting)? (myself|my ?self)\b",
    r"\btake my (own )?life\b",
    r"\boverdos(e|ed|ing) on purpose\b",
]

_MEDICAL_PATTERNS = [
    # Heart / chest
    r"\b(chest|heart) (pain|pressure|tightness|heaviness)\b",
    r"\bpain in (my |the )?chest\b",
    r"\bheart attack\b",
    r"\bcrushing (pain|chest)\b",
    # Breathing
    r"\b(can'?t|cannot|can not|unable to|hard to|trouble|struggling to) breath\w*",
    r"\b(difficulty|difficult to|shortness of) breath\w*",
    r"\bdifficulty in breathing\b",
    r"\bbreathless\w*",
    r"\bchok(e|ing)\b",
    r"\b(lips|face) (are |is )?(turning |going )?blue\b",
    # Stroke
    r"\b(having|had|think\w*|might be|may be|signs of) (a )?stroke\b",
    r"\bface (is )?droop\w*",
    r"\bslurred speech\b",
    r"\bsudden (numbness|weakness|confusion|vision loss|loss of vision)\b",
    r"\b(can'?t|cannot) (move|feel) (my|one|the) (arm|leg|side|face)\b",
    # Bleeding
    r"\b(severe|heavy|uncontrolled) bleeding\b",
    r"\bbleeding (heavily|a lot|won'?t stop|will not stop)\b",
    r"\b(vomiting|coughing|throwing up) (up )?blood\b",
    # Consciousness / seizure
    r"\b(unconscious|unresponsive|passed out|not waking up|won'?t wake up)\b",
    r"\b(fainted|collapsed)\b",
    r"\b(having|had) (a )?(seizure|convulsion|fit)s?\b",
    # Allergy / poisoning
    r"\banaphyla\w*",
    r"\b(throat|tongue) (is )?(swelling|closing|swollen)\b",
    r"\b(took|taken|swallowed|drank) (an? )?(overdose|poison|bleach|acid|pesticide|kerosene)\b",
    r"\boverdosed\b",
    # Other
    r"\bsevere (burn|head injury|allergic reaction)\b",
    r"\bworst headache of my life\b",
]

_SELF_HARM_RE = re.compile("|".join(_SELF_HARM_PATTERNS), re.IGNORECASE)
_MEDICAL_RE = re.compile("|".join(_MEDICAL_PATTERNS), re.IGNORECASE)

MEDICAL_EMERGENCY_RESPONSE = (
    "**This may be a medical emergency. Please get help now.**\n\n"
    "- **Call 112** (national emergency number) or **108** (ambulance) right away.\n"
    "- If you can, ask someone nearby to stay with you and help.\n"
    "- Do not wait to see if the symptoms pass, and do not drive yourself.\n\n"
    "I can't assess an emergency, and chatting with me is not a substitute for "
    "urgent care. Once you are safe and have been seen by a doctor, I'm here to "
    "help with any questions."
)

SELF_HARM_RESPONSE = (
    "**I'm really glad you told me. You don't have to go through this alone.**\n\n"
    "- **Tele-MANAS: call 14416** (free, 24x7 mental health support from the "
    "Government of India, in many languages).\n"
    "- If you are in immediate danger or have already hurt yourself, "
    "**call 112** now.\n"
    "- If you can, reach out to someone you trust and let them stay with you.\n\n"
    "I'm an AI and can't give you the support a trained person can, but the "
    "people on these lines can, right now."
)


def detect_emergency(message: str) -> Optional[str]:
    """Returns SELF_HARM, MEDICAL_EMERGENCY, or None.

    Self-harm is checked first so that a message mentioning both (e.g. an
    intentional overdose) gets the crisis-line response.
    """
    if not message:
        return None
    if _SELF_HARM_RE.search(message):
        return SELF_HARM
    if _MEDICAL_RE.search(message):
        return MEDICAL_EMERGENCY
    return None


def emergency_response(category: str) -> str:
    return SELF_HARM_RESPONSE if category == SELF_HARM else MEDICAL_EMERGENCY_RESPONSE
