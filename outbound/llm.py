"""The model seam. One verb: complete(prompt) -> text.

RealLLM talks to Anthropic. FakeLLM is deterministic and offline, so tests and
demos need no API key. The brain does not know or care which one it holds.
"""
import hashlib

from . import config


class FakeLLM:
    """Deterministic stand-in. Same prompt in, same text out. No network."""

    def complete(self, prompt: str) -> str:
        p = prompt.lower()
        if "judge" in p:
            # Off-brand only if the writer explicitly marked it so (used in tests).
            return "FAIL: off-brand" if "[[offbrand]]" in prompt else "PASS"
        # Template generation. Vary by a stable hash so children differ.
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        subjects = [
            "A quicker way through your notes",
            "Still spending evenings on notes?",
            "Worth another look, {name}?",
            "Notes done before the patient leaves",
        ]
        bodies = [
            "Hi {name}, a lot of clinicians came back to JotPsych this year after "
            "trying it once. If notes still run into your evenings, it may be worth "
            "another look. Want a short demo?",
            "Hi {name}, quick one. Clinicians tell us the win is finishing notes "
            "before the patient walks out. If that would help your week, I can show "
            "you in ten minutes.",
            "Hi {name}, no pitch. If your current tool is working, ignore this. If "
            "notes are still a grind, a lot of people gave JotPsych a second try and "
            "stayed. Happy to show you why.",
        ]
        return "SUBJECT: " + subjects[h % len(subjects)] + "\nBODY: " + bodies[h % len(bodies)]


class RealLLM:
    """Anthropic-backed. Used when ANTHROPIC_API_KEY is set."""

    def __init__(self):
        import anthropic  # imported lazily so the fake path needs no dependency
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def complete(self, prompt: str) -> str:
        msg = self.client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def get_llm():
    return RealLLM() if config.ANTHROPIC_API_KEY else FakeLLM()
