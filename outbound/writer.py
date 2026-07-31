"""Make an email, and make new templates.

Making an email = fill the {name} slot and append the CAN-SPAM footer.
Pure Python. No model. No claimed facts. The only fact we hold is the name.

Making a template = ask the model (crossover, mutation, or from scratch).
"""
import re

from . import config
from .channels import unsub_link_for


def clean_name(name):
    """{name} hygiene. Empty or odd names fall back to a safe greeting."""
    name = (name or "").strip()
    name = re.sub(r"[^\w\s'-]", "", name).strip()  # drop stray punctuation
    first = name.split()[0] if name else ""
    return first or "there"


def footer(email):
    link = unsub_link_for(email)
    return f"\n\n{config.MAILING_ADDRESS}\nUnsubscribe: {link}"


def make_email(template, contact):
    """Template + contact -> (subject, body, unsub_link) ready to send.

    The name fills the opening greeting. We always append the JotPsych Team
    sign-off ourselves, so the model can never leave a '[Your Name]' placeholder.
    """
    name = clean_name(contact["name"])
    subject = template["subject"].replace("{name}", name)
    body = template["body"].replace("{name}", name)
    body = f"{body}\n\n{config.SIGNOFF}{footer(contact['email'])}"
    return subject, body, unsub_link_for(contact["email"])


# --- template generation ----------------------------------------------------

BRAND = (
    "You write short outreach emails for JotPsych, an AI medical-notes tool for "
    "clinicians who run their own practices. Voice: warm, plain, and peer to peer, "
    "one clinician to another. Respect a busy clinician's time. No hype, no sales gloss."
)


def _instructions():
    """The hard rules, built from the same lists the gate enforces, so what we
    ask for and what we allow can never drift apart."""
    banned = ", ".join(f'"{w}"' for w in config.BANNED_WORDS + config.PROFANITY)
    return (
        BRAND + "\n\n"
        "Follow these rules exactly:\n"
        "- Start the body with a greeting that uses the literal {name} slot, for "
        "example 'Hi {name},'. Put {name} only there, nowhere else.\n"
        "- Do NOT write any closing, signature, or sender name, and never use a "
        "placeholder in square brackets like [Your Name]. We add the 'JotPsych Team' "
        "sign-off ourselves. End the body on your last real sentence.\n"
        "- We know only the person's first name. Never invent any other fact about them "
        "(no practice size, no location, no contract, no product they use).\n"
        f"- Keep the body under {config.MAX_BODY_CHARS} characters. Plain text only.\n"
        "- Do NOT use the em dash character. Use a period or a comma instead.\n"
        "- Do NOT use exclamation runs (\"!!!\") or \"#1\".\n"
        "- Do NOT use the pattern \"not only ... but also\".\n"
        f"- Do NOT use any of these words or phrases: {banned}.\n"
        "- Sound like a real person, not AI. No corporate filler, no cliches.\n\n"
        "Reply with exactly one line 'SUBJECT: <subject>' then 'BODY: <body>'."
    )


def _parse(text):
    """Pull SUBJECT / BODY out of a model reply."""
    subj = re.search(r"SUBJECT:\s*(.+)", text)
    body = re.search(r"BODY:\s*(.+)", text, re.DOTALL)
    subject = subj.group(1).strip() if subj else "A quick note, {name}"
    body_text = body.group(1).strip() if body else text.strip()
    return subject, body_text


def generate(llm, origin, parents=None):
    """Return (subject, body, origin) for a new candidate template."""
    if origin == "crossover" and parents and len(parents) >= 2:
        task = (
            "Task: write one new outreach email by blending the strongest ideas of "
            f"these two winners into something fresh.\n\nA:\n{parents[0]['body']}\n\n"
            f"B:\n{parents[1]['body']}"
        )
    elif origin == "mutation" and parents:
        task = (
            "Task: rewrite this winning email with one small change in angle or "
            f"opening. Keep what works.\n\n{parents[0]['body']}"
        )
    else:  # random / seed
        task = (
            "Task: write a fresh outreach email to a clinician who tried JotPsych "
            "once and left. Find a new angle."
        )
    prompt = task + "\n\n" + _instructions()
    subject, body = _parse(llm.complete(prompt))
    return subject, body, origin
