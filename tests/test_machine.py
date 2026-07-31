"""Executable version of TESTS.md. Runs fully offline with the fake hands.

Run:  pytest -q
"""
import os
import random
from datetime import timedelta

import pytest

from outbound import config, db, gate, learn, writer, engine
from outbound.channels import FakeEmail, UNSUB_HEADER
from outbound.llm import FakeLLM
from outbound.sales import FakeSales
from outbound.returns import FakeReturns


# --- helpers ----------------------------------------------------------------

@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.init(c)
    return c


def deps():
    return engine.Deps(FakeEmail(), FakeLLM(), FakeSales(), FakeReturns())


def a_template(con, subject="Hi {name}", body="Hi {name}, worth another look?"):
    return db.add_template(con, subject, body, "seed", alive=True)


def a_contact(con, name="Dr Jo", email="jo@example.com"):
    db.add_contact(con, name, email)
    return db.contact_by_email(con, email)


# --- A. stamps --------------------------------------------------------------

def test_never_is_blocked(con):
    c = a_contact(con)
    db.mark_never(con, c["id"])
    assert db.eligible_contacts(con, 10) == []


def test_none_is_free(con):
    a_contact(con)
    assert len(db.eligible_contacts(con, 10)) == 1


def test_rest_not_expired_is_skipped(con):
    c = a_contact(con)
    db.mark_sent(con, c["id"])  # rests 30 days
    assert db.eligible_contacts(con, 10) == []


def test_rest_expired_is_free(con):
    c = a_contact(con)
    past = db.iso(db.now() - timedelta(days=1))
    con.execute("UPDATE contacts SET stamp='rest', rest_until=? WHERE id=?", (past, c["id"]))
    con.commit()
    assert len(db.eligible_contacts(con, 10)) == 1


# --- B. send behaviour ------------------------------------------------------

def test_send_rests_and_counts_and_writes_row(con):
    a_template(con)
    a_contact(con)
    engine.send_batch(con, deps(), {})
    c = db.contact_by_email(con, "jo@example.com")
    assert c["stamp"] == "rest" and c["times_sent"] == 1 and c["status"] == "contacted"
    assert c["rest_until"] > db.iso(db.now() + timedelta(days=29))  # ~30 days out
    assert db.last_message_for(con, c["id"]) is not None


def test_once_a_month(con):
    a_template(con)
    a_contact(con)
    d = deps()
    engine.send_batch(con, d, {})
    engine.send_batch(con, d, {})  # second round, same day
    assert len(d.channel.outbox) == 1  # not sent twice


# --- C1. gate hard rules ----------------------------------------------------

@pytest.mark.parametrize("bad", ["delve", "leverage", "act now", "click here",
                                 "best in the world", "the only"])
def test_banned_words_refused(bad):
    ok, reason = gate.hard_check(f"Hi there, we {bad} things.")
    assert not ok and "banned" in reason


def test_profanity_refused():
    ok, _ = gate.hard_check("this is damn good")
    assert not ok


def test_em_dash_refused():
    ok, reason = gate.hard_check("Hello — friend")
    assert not ok and "sign" in reason


def test_case_insensitive():
    assert not gate.hard_check("We DELVE in")[0]
    assert not gate.hard_check("We Delve in")[0]


def test_not_only_but_also_refused():
    ok, _ = gate.hard_check("Not only fast but also cheap")
    assert not ok


def test_too_long_refused():
    ok, reason = gate.hard_check("x" * (config.MAX_BODY_CHARS + 1))
    assert not ok and "long" in reason


def test_clean_message_passes_layer1():
    ok, reason = gate.hard_check("Hi Jo, notes still running late? Worth a look.")
    assert ok and reason is None


def test_reason_names_the_hit():
    ok, reason = gate.hard_check("we leverage synergy")
    assert "leverage" in reason


# Scunthorpe: a banned word inside a real name must not trip on word boundary.
def test_word_boundary_spares_names():
    assert gate.hard_check("Hi Dr Grass, hello")[0] is True    # 'ass' inside Grass
    assert gate.hard_check("what an ass")[0] is False          # standalone 'ass'


# --- C2. judge + fail closed ------------------------------------------------

def test_judge_passes_clean():
    ok, _ = gate.check("Worth a look", "Hi {name}, notes still late?", FakeLLM())
    assert ok


def test_judge_fails_offbrand():
    ok, _ = gate.check("Hi", "[[offbrand]] buy now friend", FakeLLM())
    assert not ok


def test_fail_closed_on_judge_error():
    class Boom:
        def complete(self, p): raise RuntimeError("down")
    ok, reason = gate.judge("s", "clean body", Boom())
    assert not ok and "error" in reason


# --- D. replies and unsubscribe ---------------------------------------------

def test_suppression_sets_never(con):
    a_template(con); c = a_contact(con)
    d = deps(); d.channel.suppressed = ["jo@example.com"]
    engine.sweep(con, d)
    assert db.contact_by_email(con, "jo@example.com")["stamp"] == "never"


def test_stop_word_reply_sets_never_and_timestamps(con):
    a_template(con); a_contact(con)
    d = deps(); d.channel.inbox = [{"email": "jo@example.com", "text": "please STOP"}]
    engine.sweep(con, d)
    c = db.contact_by_email(con, "jo@example.com")
    assert c["stamp"] == "never" and c["unsubscribed_at"] is not None
    assert d.sales.handoffs == []  # a stop never goes to sales


def test_positive_reply_is_hot_lead_to_sales(con):
    a_template(con); c = a_contact(con)
    engine.send_batch(con, deps(), {})  # so there is a last message
    d = deps(); d.channel.inbox = [{"email": "jo@example.com", "text": "yes, show me"}]
    engine.sweep(con, d)
    c = db.contact_by_email(con, "jo@example.com")
    assert c["status"] == "replied" and c["replied_at"] is not None
    assert len(d.sales.handoffs) == 1


def test_auto_reply_is_ignored(con):
    a_template(con); a_contact(con)
    d = deps(); d.channel.inbox = [{"email": "jo@example.com", "text": "Out of office until Monday"}]
    s = engine.sweep(con, d)
    assert s["ignored"] == 1 and d.sales.handoffs == []


def test_bounce_sets_never(con):
    a_contact(con)
    d = deps(); d.channel.bounced = ["jo@example.com"]
    engine.sweep(con, d)
    assert db.contact_by_email(con, "jo@example.com")["stamp"] == "never"


def test_return_recorded_and_credited(con):
    tid = a_template(con); c = a_contact(con)
    engine.send_batch(con, deps(), {})
    d = deps(); d.returns.returned = ["jo@example.com"]
    engine.sweep(con, d)
    assert db.contact_by_email(con, "jo@example.com")["status"] == "returned"
    t = con.execute("SELECT returns FROM templates WHERE id=?", (tid,)).fetchone()
    assert t["returns"] == 1


# --- E. learning ------------------------------------------------------------

def test_start_uniform(con):
    a_template(con, body="A {name}")
    a_template(con, body="B {name}")
    scores = [learn.score(t) for t in db.alive_templates(con)]
    assert scores[0] == scores[1]  # no data -> equal


def test_score_uses_both():
    reply = {"replies": 1, "returns": 0, "sends": 10}
    ret = {"replies": 0, "returns": 1, "sends": 10}
    assert learn.score(ret) > learn.score(reply)  # a return outweighs a reply


def test_favor_winners(con):
    good = a_template(con, body="good {name}")
    bad = a_template(con, body="bad {name}")
    con.execute("UPDATE templates SET sends=100, replies=40 WHERE id=?", (good,))
    con.execute("UPDATE templates SET sends=100, replies=1 WHERE id=?", (bad,))
    con.commit()
    random.seed(0)
    picks = [learn.pick(db.alive_templates(con))["id"] for _ in range(200)]
    assert picks.count(good) > picks.count(bad)


def test_drop_loser_only_with_data(con):
    good = a_template(con); bad = a_template(con)
    con.execute("UPDATE templates SET sends=100, replies=50 WHERE id=?", (good,))
    con.execute("UPDATE templates SET sends=100, replies=0 WHERE id=?", (bad,))
    con.commit()
    learn.drop_losers(con)
    alive_ids = [t["id"] for t in db.alive_templates(con)]
    assert good in alive_ids and bad not in alive_ids


def test_pool_never_dies(con):
    only = a_template(con)
    con.execute("UPDATE templates SET sends=100, replies=0 WHERE id=?", (only,))
    con.commit()
    learn.drop_losers(con)
    assert len(db.alive_templates(con)) >= 1


def test_ga_improves_over_cycles(con, monkeypatch):
    """The whole point: against a world that replies to one template and ignores
    the other, the machine shifts sends to the winner and drops the loser."""
    monkeypatch.setattr(config, "MIN_SENDS_TO_DROP", 5)
    monkeypatch.setattr(config, "SENDS_PER_ROUND", 20)
    monkeypatch.setattr(config, "DAILY_SEND_CAP", 10_000)
    good = a_template(con, subject="good {name}", body="good {name}")
    bad = a_template(con, subject="bad {name}", body="bad {name}")
    for i in range(200):
        db.add_contact(con, f"P{i}", f"p{i}@x.com")

    d = deps()
    random.seed(1)
    for _ in range(6):
        engine.send_batch(con, d, {})
        # the world: everyone who got the good template replies; nobody else does
        pending = con.execute(
            "SELECT c.email FROM messages m JOIN contacts c ON c.id=m.contact_id "
            "WHERE m.template_id=? AND m.reply_at IS NULL", (good,)).fetchall()
        d.channel.inbox = [{"email": r["email"], "text": "yes please"} for r in pending]
        engine.sweep(con, d)

    g = con.execute("SELECT * FROM templates WHERE id=?", (good,)).fetchone()
    b = con.execute("SELECT * FROM templates WHERE id=?", (bad,)).fetchone()
    assert g["replies"] > 0 and b["replies"] == 0
    assert learn.score(g) > learn.score(b)      # the winner scores higher
    learn.drop_losers(con)
    alive_ids = [t["id"] for t in db.alive_templates(con)]
    assert good in alive_ids and bad not in alive_ids  # loser culled, winner kept


def test_evolve_breeds_and_keeps_random(con):
    learn.seed(con, FakeLLM(), n=3)
    before = len(db.all_templates(con))
    learn.evolve(con, FakeLLM())
    after = db.all_templates(con)
    assert len(after) > before
    assert any(t["origin"] == "random" for t in after)


# --- gate at birth, dashboard, safety --------------------------------------

def test_dashboard_reports_all_panels(con):
    from outbound import dashboard
    t1 = db.add_template(con, "A {name}", "A {name}", "seed", alive=True)
    t2 = db.add_template(con, "B {name}", "B {name}", "random", alive=True)
    db.add_template(con, "bad", "we leverage x", "random", alive=False,
                    gate_reason="banned word: 'leverage'")
    con.execute("UPDATE templates SET sends=100, replies=10, returns=2 WHERE id=?", (t1,))
    con.execute("UPDATE templates SET sends=100, replies=1,  returns=0 WHERE id=?", (t2,))
    con.commit()
    for i in range(3):
        db.add_contact(con, f"C{i}", f"c{i}@x.com")
    db.add_contact(con, "Gone", "gone@x.com")
    db.mark_never(con, db.contact_by_email(con, "gone@x.com")["id"])

    d = dashboard.build(con)
    assert d["top_templates"][0]["id"] == t1                       # winner ranked first
    assert d["top_templates"][0]["subject"] == "A {name}"          # shows the text
    assert d["success"]["reply_rate"] == round(11 / 200, 4)        # 11 replies / 200 sends
    assert d["success"]["return_rate"] == round(2 / 200, 4)
    assert d["volume"] == {"sends": 200, "replies": 11, "returns": 2, "unsubscribes": 1}
    assert d["unsubscribe_rate"] == round(1 / 200, 4)
    assert d["gate_health"]["blocked"] == 1
    assert "banned word" in d["gate_health"]["reasons"]            # reason grouped
    assert d["pool_health"] == {"eligible": 3, "total_contacts": 4, "unsubscribed": 1}
    assert d["diversity"]["alive"] == 2
    assert d["diversity"]["origins"] == {"seed": 1, "random": 1}
    # top templates must be proven (sent), not optimistic newcomers
    db.add_template(con, "New {name}", "New {name}", "random", alive=True)  # sends=0
    assert all(t["sends"] > 0 for t in dashboard.build(con)["top_templates"])


def test_dashboard_render_is_a_string(con):
    from outbound import dashboard
    a_template(con)
    assert isinstance(dashboard.render(con), str)


def test_birth_stores_blocked_reason(con):
    learn.birth(con, FakeLLM(), "Hi", "we leverage synergy", "seed")
    blocked = [t for t in db.all_templates(con) if t["gate_reason"]]
    assert blocked and not blocked[0]["alive"]


def test_kill_switch_halts(con, tmp_path, monkeypatch):
    kill = tmp_path / "KILL"; kill.write_text("x")
    monkeypatch.setattr(config, "KILL_FILE", str(kill))
    a_template(con); a_contact(con)
    out = engine.run_round(con, deps())
    assert out.get("halted") == "kill switch"


def test_bounce_breaker_halts_sends(con, monkeypatch):
    a_template(con); a_contact(con)
    monkeypatch.setattr(config, "BOUNCE_BREAK", 0)
    d = deps(); d.channel.bounced = ["x@example.com", "y@example.com"]
    out = engine.run_round(con, d)
    assert out.get("halted") == "bounce breaker" and d.channel.outbox == []


# --- I. compliance + hygiene ------------------------------------------------

def test_email_has_footer_and_unsub_header(con):
    a_template(con); c = a_contact(con)
    d = deps()
    engine.send_batch(con, d, {})
    mail = d.channel.outbox[0]
    assert config.MAILING_ADDRESS in mail["body"]
    assert "Unsubscribe:" in mail["body"]
    assert UNSUB_HEADER in mail["headers"]


def test_signoff_added_and_greeting_uses_recipient_name(con):
    db.add_template(con, "Hi {name}", "Hi {name}, worth another look?", "seed", alive=True)
    c = a_contact(con, name="Alex", email="alex@example.com")
    subject, body, _ = writer.make_email(
        {"subject": "Hi {name}", "body": "Hi {name}, worth another look?"}, c)
    assert body.startswith("Hi Alex,")          # recipient's name, at the start
    assert "The JotPsych Team" in body           # our fixed sign-off
    assert "[" not in body                       # no placeholder ever


def test_bracket_placeholder_refused():
    ok, reason = gate.hard_check("Hi Alex, thanks.\n\nBest,\n[Your Name]")
    assert not ok and "placeholder" in reason


def test_name_hygiene_blank_and_odd():
    assert writer.clean_name("") == "there"
    assert writer.clean_name("  ") == "there"
    assert writer.clean_name("Jo!!!") == "Jo"
    assert writer.clean_name("Dr. Alex Kim") == "Dr"


def test_demo_runs_end_to_end(con):
    for i in range(10):
        db.add_contact(con, f"Dr T{i}", f"t{i}@example.com")
    learn.seed(con, FakeLLM())
    d = engine.Deps(FakeEmail(), FakeLLM(), FakeSales(), FakeReturns())
    engine.run_cycle(con, d)
    assert d.channel.outbox  # something went out
