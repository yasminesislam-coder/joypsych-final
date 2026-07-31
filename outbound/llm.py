"""The model seam. One verb: complete(prompt) -> text.

RealLLM talks to Anthropic. FakeLLM is deterministic and offline, so tests and
demos need no API key. The brain does not know or care which one it holds.
"""
import hashlib

from . import config


class FakeLLM:
    """Deterministic stand-in. Same prompt in, same text out. No network."""

    def complete(self, prompt: str) -> str:
        if "judge" in prompt.lower():
            # Off-brand only if the writer explicitly marked it so (used in tests).
            return "FAIL: off-brand" if "[[offbrand]]" in prompt else "PASS"
        # Template generation: sample the real starter templates so fake-mode
        # output is on-brand. Vary by a stable hash so children differ.
        from .writer import STARTER_TEMPLATES
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        t = STARTER_TEMPLATES[h % len(STARTER_TEMPLATES)]
        return f"SUBJECT: {t['subject']}\nBODY: {t['body']}"


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
