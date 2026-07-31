"""The dashboard. Read only. It never sends.

Reads the three tables and reports the health of the machine. This is the
human's one hour a month: watch these numbers, act only if something looks wrong.
"""
from . import db, learn


def build(con):
    templates = db.all_templates(con)
    alive = [t for t in templates if t["alive"] and t["gate_reason"] is None]
    blocked = [t for t in templates if t["gate_reason"]]

    total_sends = sum(t["sends"] for t in templates)
    total_replies = sum(t["replies"] for t in templates)
    total_returns = sum(t["returns"] for t in templates)

    contacts = db.all_contacts(con)
    never = [c for c in contacts if c["stamp"] == "never"]
    eligible = db.eligible_contacts(con, 10_000)

    # "Top" means proven, not optimistic. Rank templates that have real data;
    # fall back to the whole pool only before anything has been sent.
    tried = [t for t in alive if t["sends"] > 0]
    top = sorted(tried or alive, key=learn.score, reverse=True)[:5]

    origins = {}
    for t in alive:
        origins[t["origin"]] = origins.get(t["origin"], 0) + 1

    block_reasons = {}
    for t in blocked:
        key = (t["gate_reason"] or "").split(":")[0]
        block_reasons[key] = block_reasons.get(key, 0) + 1

    def rate(n, d):
        return round(n / d, 4) if d else 0.0

    return {
        "top_templates": [
            {"id": t["id"], "origin": t["origin"], "sends": t["sends"],
             "replies": t["replies"], "returns": t["returns"],
             "score": round(learn.score(t), 3), "subject": t["subject"]}
            for t in top
        ],
        "success": {
            "sends": total_sends,
            "reply_rate": rate(total_replies, total_sends),
            "return_rate": rate(total_returns, total_sends),
        },
        "volume": {"sends": total_sends, "replies": total_replies,
                   "returns": total_returns, "unsubscribes": len(never)},
        "unsubscribe_rate": rate(len(never), total_sends),
        "gate_health": {"blocked": len(blocked), "reasons": block_reasons},
        "pool_health": {"eligible": len(eligible), "total_contacts": len(contacts),
                        "unsubscribed": len(never)},
        "diversity": {"alive": len(alive), "origins": origins},
    }


def render(con):
    d = build(con)
    lines = ["=== Outbound machine dashboard ===", ""]
    s = d["success"]
    lines.append(f"Sends: {s['sends']}   reply rate: {s['reply_rate']}   "
                 f"return rate: {s['return_rate']}")
    v = d["volume"]
    lines.append(f"Volume: {v['sends']} sent, {v['replies']} replies, "
                 f"{v['returns']} returns, {v['unsubscribes']} unsubscribed")
    lines.append(f"Unsubscribe rate: {d['unsubscribe_rate']}")
    g = d["gate_health"]
    lines.append(f"Gate: {g['blocked']} blocked  {g['reasons']}")
    p = d["pool_health"]
    lines.append(f"Pool: {p['eligible']} eligible of {p['total_contacts']} contacts")
    lines.append(f"Diversity: {d['diversity']['alive']} alive  {d['diversity']['origins']}")
    lines.append("")
    lines.append("Top templates:")
    for t in d["top_templates"]:
        lines.append(f"  [{t['id']}] {t['origin']:9} score={t['score']:<6} "
                     f"sends={t['sends']} replies={t['replies']} returns={t['returns']}"
                     f"  | {t['subject']}")
    return "\n".join(lines)
