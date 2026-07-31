"""The genetic algorithm. Score, pick, breed, add random, drop.

Slow on purpose. Reply rates are tiny and noisy, so we smooth every rate and
refuse to kill a template before it has real data. Better to waste a few sends
than to kill a good template on luck.
"""
import random

from . import config, db, gate, writer


def _smoothed(hits, sends):
    """Laplace smoothing. With no data every template scores the same, so the
    first cycle is uniform, exactly as intended."""
    return (hits + 1) / (sends + 2)


def score(t):
    reply_rate = _smoothed(t["replies"], t["sends"])
    return_rate = _smoothed(t["returns"], t["sends"])
    return reply_rate + config.RETURN_WEIGHT * return_rate


def pick(templates):
    """Weighted random by score. Winners are chosen more; nobody is starved."""
    weights = [score(t) for t in templates]
    return random.choices(templates, weights=weights, k=1)[0]


def birth(con, llm, subject, body, origin):
    """Create one template, judged once at the gate. Passing = alive.
    Failing = stored dead with its reason, so the dashboard can show gate health."""
    ok, reason = gate.check(subject, body, llm)
    return db.add_template(con, subject, body, origin, alive=ok, gate_reason=reason)


def seed(con, llm, n=None):
    """Fill an empty pool with the hand-authored, spec-compliant starters."""
    for t in writer.STARTER_TEMPLATES:
        birth(con, llm, t["subject"], t["body"], "seed")


def evolve(con, llm):
    """One cycle: breed off winners, always add true random, drop losers."""
    alive = db.alive_templates(con)
    if not alive:
        seed(con, llm)
        return
    winners = sorted(alive, key=score, reverse=True)[: config.TOP_K]

    # breed off winners
    if len(winners) >= 2:
        s, b, o = writer.generate(llm, "crossover", winners)
        birth(con, llm, s, b, o)
    s, b, o = writer.generate(llm, "mutation", winners[:1])
    birth(con, llm, s, b, o)

    # always inject true random (the slice that never closes)
    for _ in range(config.RANDOM_PER_CYCLE):
        s, b, o = writer.generate(llm, "random")
        birth(con, llm, s, b, o)

    # drop losers, but only ones with enough data, and never the whole pool
    drop_losers(con)


def drop_losers(con):
    alive = db.alive_templates(con)
    if len(alive) <= 1:
        return
    best = max(score(t) for t in alive)
    survivors = len(alive)
    for t in sorted(alive, key=score):  # weakest first
        if survivors <= 1:
            break
        if t["sends"] >= config.MIN_SENDS_TO_DROP and score(t) < config.DROP_FRACTION * best:
            db.set_alive(con, t["id"], False)
            survivors -= 1
