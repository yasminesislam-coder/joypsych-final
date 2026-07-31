"""The loop. One round ties everything together and obeys the rules.

A round:
  1. Sweep inbound first: unsubscribes, bounces, replies, returns.
  2. Route them: stop -> never, interested -> sales, return -> returned.
  3. Send: pick eligible contacts, pick a template, fill the name, send, record.
A cycle = a round plus one turn of the genetic algorithm (learn.evolve).

Safety: a kill file halts everything. A daily cap and a bounce breaker bound the
volume. The gate already judged every live template at birth, so no model runs
here; sending is pure Python.
"""
import os
from dataclasses import dataclass

from . import config, db, learn
from .channels import get_channel
from .llm import get_llm
from .returns import get_returns
from .sales import get_sales
from .writer import make_email


@dataclass
class Deps:
    channel: object
    llm: object
    sales: object
    returns: object


def default_deps():
    return Deps(get_channel(), get_llm(), get_sales(), get_returns())


def killed():
    return os.path.exists(config.KILL_FILE)


def _is_stop(text):
    low = (text or "").lower()
    return any(w in low for w in config.STOP_WORDS)


def _is_auto(text):
    low = (text or "").lower()
    return any(w in low for w in config.AUTO_REPLY_MARKERS)


def sweep(con, deps):
    """Read everything inbound and update the rows. Returns a small summary."""
    summary = {"unsubscribed": 0, "bounced": 0, "replied": 0, "returned": 0, "ignored": 0}

    # unsubscribes (Postmark suppression list) -> never
    for email in deps.channel.fetch_unsubscribes():
        c = db.contact_by_email(con, email)
        if c:
            db.mark_never(con, c["id"])
            summary["unsubscribed"] += 1

    # bounces (dead addresses) -> never, so we never email them again
    bounces = deps.channel.fetch_bounces()
    for email in bounces:
        c = db.contact_by_email(con, email)
        if c:
            db.mark_never(con, c["id"])
            summary["bounced"] += 1

    # replies -> stop word unsubscribes, auto-replies are ignored, rest go to sales
    for r in deps.channel.fetch_replies():
        c = db.contact_by_email(con, r["email"])
        if not c:
            continue
        if _is_stop(r["text"]):
            db.mark_never(con, c["id"])
            summary["unsubscribed"] += 1
            continue
        if _is_auto(r["text"]):
            summary["ignored"] += 1
            continue
        # a real, interested reply
        msg = db.last_message_for(con, c["id"])
        if msg:
            db.record_reply(con, msg["id"], r["text"])
            db.bump_template(con, msg["template_id"], "replies")
        db.mark_replied(con, c["id"])
        deps.sales.notify(c, r["text"])
        summary["replied"] += 1

    # returns (product event) -> returned, credit the template that reached them
    for email in deps.returns.check():
        c = db.contact_by_email(con, email)
        if not c:
            continue
        db.mark_returned(con, c["id"])
        msg = db.last_message_for(con, c["id"])
        if msg:
            db.bump_template(con, msg["template_id"], "returns")
        summary["returned"] += 1

    summary["bounce_break"] = len(bounces) > config.BOUNCE_BREAK
    return summary


def send_batch(con, deps, summary):
    """Send to eligible contacts, within the caps."""
    if summary.get("bounce_break"):
        summary["sent"] = 0
        summary["halted"] = "bounce breaker"
        return summary

    room = config.DAILY_SEND_CAP - db.sent_today(con)
    limit = max(0, min(config.SENDS_PER_ROUND, room))
    templates = db.alive_templates(con)
    if not templates or limit == 0:
        summary["sent"] = 0
        return summary

    sent = 0
    for contact in db.eligible_contacts(con, limit):
        t = learn.pick(templates)
        subject, body, unsub = make_email(t, contact)
        deps.channel.send(contact["email"], subject, body, unsub)
        db.add_message(con, contact["id"], t["id"], subject, body)
        db.mark_sent(con, contact["id"])
        db.bump_template(con, t["id"], "sends")
        sent += 1
    summary["sent"] = sent
    return summary


def run_round(con, deps=None):
    deps = deps or default_deps()
    if killed():
        return {"halted": "kill switch"}
    summary = sweep(con, deps)
    return send_batch(con, deps, summary)


def run_cycle(con, deps=None):
    """A round, then one turn of the genetic algorithm."""
    deps = deps or default_deps()
    summary = run_round(con, deps)
    if not summary.get("halted"):
        learn.evolve(con, deps.llm)
    return summary
