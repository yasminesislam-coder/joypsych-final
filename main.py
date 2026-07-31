"""Command line for the outbound machine.

    python main.py init                 create the database
    python main.py seed-contacts FILE   load contacts from a CSV (name,email,phone)
    python main.py seed-templates       fill the pool with starter templates
    python main.py run                  one round (sweep + send)
    python main.py cycle [N]            N cycles (round + evolve). Default 1.
    python main.py dashboard            print the health dashboard
    python main.py demo                 seed fake data and run a few cycles offline
    python main.py check-llm            make one model call and report pass/fail
    python main.py preview              generate one template and print the finished email
    python main.py sim                  run a simulated world and print a full dashboard
"""
import csv
import random
import sys

from outbound import config, db, dashboard, engine, learn, writer, gate
from outbound.llm import get_llm, FakeLLM
from outbound.channels import FakeEmail
from outbound.sales import FakeSales
from outbound.returns import FakeReturns


def cmd_init():
    con = db.connect()
    db.init(con)
    print(f"database ready at {config.DB_PATH}")


def cmd_seed_contacts(path):
    con = db.connect(); db.init(con)
    n = 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            db.add_contact(con, row.get("name", ""), row["email"], row.get("phone", ""))
            n += 1
    print(f"loaded {n} contacts")


def cmd_seed_templates():
    con = db.connect(); db.init(con)
    learn.seed(con, get_llm())
    print(f"pool now has {len(db.alive_templates(con))} live templates")


def cmd_run():
    con = db.connect(); db.init(con)
    print(engine.run_round(con))


def cmd_cycle(n=1):
    con = db.connect(); db.init(con)
    for _ in range(int(n)):
        print(engine.run_cycle(con))


def cmd_dashboard():
    con = db.connect(); db.init(con)
    print(dashboard.render(con))


def cmd_check_llm():
    """One model call. Confirms the key works and the reply parses."""
    llm = get_llm()
    kind = "FAKE (offline, no key)" if isinstance(llm, FakeLLM) else f"REAL Claude ({config.LLM_MODEL})"
    print(f"LLM in use: {kind}")
    try:
        subject, body, _ = writer.generate(llm, "random")
    except Exception as e:
        print(f"FAIL: the model call errored: {e}")
        return
    ok, reason = gate.check(subject, body, llm)
    print("call succeeded.")
    print(f"  generated subject: {subject}")
    print(f"  gate verdict: {'PASS' if ok else 'FAIL - ' + str(reason)}")


def cmd_preview():
    """Generate one template and render the finished email a contact would get."""
    llm = get_llm()
    kind = "FAKE" if isinstance(llm, FakeLLM) else "REAL Claude"
    subject, body, origin = writer.generate(llm, "random")
    contact = {"name": "Dr Alex Rivera", "email": "alex@example.com"}
    subj, full_body, _ = writer.make_email({"subject": subject, "body": body}, contact)
    ok, reason = gate.check(subject, body, llm)
    print(f"--- preview ({kind} LLM, origin={origin}) ---")
    print(f"To: {contact['name']} <{contact['email']}>")
    print(f"Subject: {subj}")
    print()
    print(full_body)
    print()
    print(f"[gate: {'PASS' if ok else 'FAIL - ' + str(reason)}]")


def cmd_sim():
    """Run a fake world (some reply, some return, some unsubscribe) so every
    dashboard panel shows real numbers. Uses a throwaway in-memory database."""
    con = db.connect(":memory:"); db.init(con)
    learn.seed(con, FakeLLM(), n=4)
    learn.birth(con, FakeLLM(), "Hi {name}", "we leverage synergy to supercharge", "random")
    for i in range(300):
        db.add_contact(con, f"Dr Person{i}", f"person{i}@example.com")

    d = engine.Deps(FakeEmail(), FakeLLM(), FakeSales(), FakeReturns())
    random.seed(7)
    old = config.SENDS_PER_ROUND
    config.SENDS_PER_ROUND = 30
    for _ in range(5):
        engine.send_batch(con, d, {})
        fresh = con.execute("SELECT c.email FROM messages m JOIN contacts c "
                            "ON c.id=m.contact_id WHERE m.reply_at IS NULL").fetchall()
        inbox, returned, suppressed = [], [], []
        for r in fresh:
            roll = random.random()
            if roll < 0.15:   inbox.append({"email": r["email"], "text": "yes, a demo please"})
            elif roll < 0.20: suppressed.append(r["email"])
            if roll < 0.05:   returned.append(r["email"])
        d.channel.inbox, d.channel.suppressed, d.returns.returned = inbox, suppressed, returned
        engine.sweep(con, d)
        learn.evolve(con, d.llm)
    config.SENDS_PER_ROUND = old

    print(dashboard.render(con))
    print(f"\n(sales received {len(d.sales.handoffs)} hot leads in this simulated run)")


def cmd_demo():
    """Everything offline with fakes: seed people, seed templates, run cycles."""
    con = db.connect(); db.init(con)
    for i in range(1, 41):
        db.add_contact(con, f"Dr Test{i}", f"test{i}@example.com")
    llm = get_llm()
    learn.seed(con, llm)
    for _ in range(3):
        engine.run_cycle(con)
    print(dashboard.render(con))


def main(argv):
    if not argv:
        print(__doc__); return
    cmd, rest = argv[0], argv[1:]
    if cmd == "init": cmd_init()
    elif cmd == "seed-contacts": cmd_seed_contacts(rest[0])
    elif cmd == "seed-templates": cmd_seed_templates()
    elif cmd == "run": cmd_run()
    elif cmd == "cycle": cmd_cycle(rest[0] if rest else 1)
    elif cmd == "dashboard": cmd_dashboard()
    elif cmd == "demo": cmd_demo()
    elif cmd == "check-llm": cmd_check_llm()
    elif cmd == "preview": cmd_preview()
    elif cmd == "sim": cmd_sim()
    else: print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
