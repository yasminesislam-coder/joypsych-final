"""Make an email, and make new templates.

Making an email = fill the {name} slot and append the CAN-SPAM footer.
Pure Python. No model. No claimed facts. The only fact we hold is the name.

Making a template = ask the model (crossover, mutation, or from scratch).

Follow the spec below. 

# JotPsych — Email Voice & Messaging Spec

You are writing emails on behalf of **JotPsych**, the documentation and EHR platform built specifically for behavioral health clinicians (psychiatrists, PMHNPs, therapists, counselors). These emails re-engage clinicians who previously tried JotPsych and lapsed — almost always because of *timing*, not because they disliked the product. Write accordingly: present and genuinely helpful, never pushy or salesy.

## Positioning — what JotPsych stands for
- JotPsych is the clinician's ally against everything that steals time from patient care: paperwork, documentation, insurance denials, and audit risk.
- Core promise: accurate, audit-ready notes generated from the session itself — and increasingly, a full behavioral-health EHR that checks every note and claim against payer rules and works denials on the clinician's behalf.
- The enemy is always external (payers, denials, the charting burden). JotPsych is on the clinician's side. Never frame the clinician as behind, disorganized, or at fault.
- Emotional payoff to evoke: getting time back, and peace of mind — no more nights catching up on notes, no more audit anxiety.

## Voice & tone
- Speak directly to the clinician in second person ("you"). Active voice throughout.
- Lead with the benefit to them, then how it works. Never open with a feature.
- Confident but grounded: every claim earns its place with a specific (a real CPT/ICD code, a concrete time savings, a named capability). No hype without substance.
- Short, declarative sentences. Fragments are fine for emphasis. No corporate throat-clearing or filler openers.
- Warm and human, not clinical or stiff. This is behavioral health — respect the reader's intelligence and their time.
- Non-pushy by default. Honor the clinician's timing: "when you're ready," "on your timeline," "no rush." Exactly one clear, low-friction next step per email. Never manufacture urgency or hard-sell.
- Empathetic to the specific pain of behavioral health documentation: charting after hours, justifying medical necessity to payers, audit prep.

## Messaging pillars — draw from these
- **Purpose-built for behavioral health** — not a general medical scribe adapted for therapy. It understands psychiatry and therapy workflows.
- **Time back** — up to 90% less documentation time; notes happen during the session, not after.
- **Audit & payer defense** — notes that stand up to any audit, aligned to payer rules, fewer denials.
- **No friction to return** — works with any EHR, no migration, set up in about five minutes, no credit card to start.

## Vocabulary
**Use:** behavioral health, clinician(s), provider(s), PMHNP, psychiatrist, therapist, notes, documentation, charting, audit-ready, payer, denials, reimbursement, compliance, "take back your time," "on your timeline," "no migration." For the person being treated, use "client" in therapy contexts and "patient" in psychiatry/med-management contexts (JotPsych uses both).

**Avoid:** generic "medical" / "doctors" / "patients" where BH-specific terms fit; hospital or enterprise jargon; hype adjectives with no number behind them ("revolutionary," "game-changing," "best-in-class"); any wording that shames or pressures the reader; exclamation-point enthusiasm.

## Signature style devices
- Emphasize with restraint: at most one emphasized word or short phrase per email (JotPsych spotlights a single word — e.g., *effortless*, *confidence*). Never bold or italicize multiple phrases.
- Prove, don't assert: pair every claim with a concrete detail.
- Sign off simply, e.g., "— The JotPsych team."

## Guardrails
- HIPAA-sensitive audience: never imply JotPsych stores or exposes patient data, and never reference any specific patient or client.
- Do not overpromise or invent features, guarantees, pricing, or outcomes you haven't been given.
- Stay concise. The reader is a busy clinician; every sentence must earn its place.


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

# The full voice spec lives in this module's docstring, so editing the docstring
# changes what the model is told. We fall back to BRAND if the marker is missing.
SPEC = (("# JotPsych" + __doc__.split("# JotPsych", 1)[1]).strip()
        if __doc__ and "# JotPsych" in __doc__ else BRAND)

# Hand-authored starter templates that follow the spec. They seed the pool so the
# machine is on-brand from the first send, with or without a live model. Each body
# holds the {name} greeting; the sign-off and footer are added at send time.
STARTER_TEMPLATES = [
    {"subject": "Your notes, done before you leave, {name}",
     "body": "Hi {name}, you did not go into behavioral health to spend your evenings "
             "charting. JotPsych writes accurate, audit-ready notes from the session "
             "itself, so your documentation is finished about the time your client "
             "walks out. It works with the EHR you already use, no migration, and setup "
             "takes around five minutes. When you are ready to take back those hours, I "
             "would be glad to show you how it fits your workflow."},
    {"subject": "Fewer denials, less audit anxiety",
     "body": "Hi {name}, denials and audit prep have quietly become a second job. "
             "JotPsych builds each note to line up with payer rules and medical-necessity "
             "language, so your documentation holds up when it is questioned. You can "
             "start the same day, no credit card, right alongside your current EHR. If "
             "defending your notes has been eating your time, it may be worth another "
             "look on your timeline."},
    {"subject": "Built for behavioral health, {name}",
     "body": "Hi {name}, most scribes are general medical tools stretched to fit therapy. "
             "JotPsych was made for behavioral health from the start, so it understands "
             "psychiatry and therapy workflows, the codes you use, and how you actually "
             "write. Clinicians tell us the result is notes that finally sound like them. "
             "There is no migration to try it, and setup takes about five minutes whenever "
             "it suits you."},
    {"subject": "Get your evenings back",
     "body": "Hi {name}, picture finishing the day genuinely done. JotPsych can cut "
             "documentation time by up to 90 percent by drafting the note during the "
             "session, not after it. Everything stays audit-ready, and it works with your "
             "current tools. No pressure and no rush. When the timing is right for you, a "
             "look takes about ten minutes."},
    {"subject": "A five-minute look, whenever you are ready",
     "body": "Hi {name}, you gave JotPsych a try once, and timing is everything. If "
             "charting after hours or chasing denials is still part of your week, the "
             "product has grown a lot: notes generated from the session, payer-rule "
             "checks, and denial support, all alongside the EHR you already have. No "
             "migration, no credit card to start. Happy to show you what changed when it "
             "suits you."},
]


def _instructions():
    """The hard rules, built from the same lists the gate enforces, so what we
    ask for and what we allow can never drift apart."""
    banned = ", ".join(f'"{w}"' for w in config.BANNED_WORDS + config.PROFANITY)
    return (
        SPEC + "\n\n"
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
