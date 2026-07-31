"""The quality gate. Two layers.

Layer 1 - hard rules. Pure Python, no model. Banned words, signs, length.
          Whole-word match, case-insensitive. Runs first, always.
Layer 2 - the LLM judge. The soft question: does this sound like JotPsych?

The gate runs once per template, at birth (see learn.py). It never runs on a
send, so send time stays pure Python. Fail closed: if the judge errors, refuse.
"""
import re

from . import config

_WORD = [re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
         for w in config.BANNED_WORDS + config.PROFANITY]


def hard_check(text: str):
    """Layer 1. Returns (ok, reason). Runs on template text, never on a name."""
    if len(text) > config.MAX_BODY_CHARS:
        return False, f"too long ({len(text)} chars)"
    if re.search(r"\[[^\]]+\]", text):  # a leftover placeholder like [Your Name]
        return False, "placeholder in square brackets"
    for sign in config.BANNED_SIGNS:
        if sign in text:
            return False, f"banned sign: {sign!r}"
    for pat in _WORD:
        m = pat.search(text)
        if m:
            return False, f"banned word: {m.group(0).lower()!r}"
    # "not only ... but also" pattern
    if re.search(r"\bnot only\b.*\bbut also\b", text, re.IGNORECASE | re.DOTALL):
        return False, "banned pattern: 'not only ... but also'"
    return True, None


JUDGE_PROMPT = """You are the brand editor for JotPsych, an AI medical-notes tool for clinicians who run their own practices.
Judge this outreach email. Say PASS if it sounds like a real person from JotPsych: warm, plain, peer to peer, respectful of a busy clinician's time, and never like an AI wrote it.
Say FAIL if it is off-brand, salesy, robotic, or over-eager.
Answer with exactly "PASS" or "FAIL: <short reason>".

SUBJECT: {subject}
BODY:
{body}
"""


def judge(subject: str, body: str, llm):
    """Layer 2. Returns (ok, reason). Fails closed on any error."""
    try:
        verdict = llm.complete(JUDGE_PROMPT.format(subject=subject, body=body)).strip()
    except Exception as e:
        return False, f"judge error: {e}"
    if verdict.upper().startswith("PASS"):
        return True, None
    reason = verdict.split(":", 1)[1].strip() if ":" in verdict else "off-brand"
    return False, f"judge: {reason}"


def check(subject: str, body: str, llm):
    """Full gate: Layer 1 then Layer 2. Returns (ok, reason)."""
    ok, reason = hard_check(subject + "\n" + body)
    if not ok:
        return False, reason
    return judge(subject, body, llm)
