# JotPsych Outbound Machine

## TL;DR

A self-running email machine that wins back clinicians who tried JotPsych and left.

You feed it a list of names and emails. It writes outreach, checks every message
against a strict brand gate, sends it, watches what comes back, and **teaches
itself** which emails work using a genetic algorithm. Hot replies go straight to
sales. Unsubscribes are honored forever. A human spends about an hour a month
reading a dashboard, not babysitting.

- **Runs itself.** One command per round. A kill switch and volume caps keep it safe.
- **Improves itself.** Winning templates breed new templates. No human rewrites anything.
- **Protects the brand.** A two-layer gate refuses anything that smells like AI, spam, or profanity, and every send is judged before it ships.
- **Proves impact.** Every return traces back to the exact template that earned it.
- **Ships today.** Real logic behind swappable seams. Runs fully offline with fakes now; set two API keys to go live on Postmark + Claude.

```bash
python3 main.py demo        # seeds fake data, runs 3 cycles offline, prints the dashboard
pytest -q                   # 41 tests, all offline
```

---

## The problem

Thousands of clinicians tried JotPsych and did not convert. The timing was wrong:
a competitor was already in place, the practice was not in enough pain yet, or a
contract had a year left. They did not say "no forever." They said "not now."

This machine taps them on the shoulder again, politely, on a slow rhythm, and
gets better at it every cycle.

## The five requirements, and how they are met

| Requirement | How |
|---|---|
| 1. Real, deployable tomorrow | Real logic behind seams (`channels.py`, `llm.py`). Fakes by default, Postmark + Claude when keys are set. |
| 2. Tells the human what to do | A read-only dashboard (`dashboard.py`): top templates, rates over time, gate and pool health. |
| 3. Trusted quality gate | Two layers (`gate.py`): pure-Python banned words, then an LLM brand judge. Judged once at birth, fail-closed. |
| 4. Metrics, learning, receipts | The genetic algorithm (`learn.py`) plus full attribution: a return joins back to one template. |
| 5. Taste, refuses off-brand | The gate refuses AI cliches, spam, overclaims, profanity, and the em dash before anything ships. |

## How it works: the loop

One round (`engine.run_round`):

1. **Sweep inbound first.** Read unsubscribes, bounces, replies, and the returns feed.
2. **Route them.** A stop word or bounce sets `never`. An interested reply goes to sales now. A return is recorded and credited.
3. **Send.** Pick eligible contacts, pick a template by score, fill the name, append the CAN-SPAM footer, send, and write the receipt.

A **cycle** (`engine.run_cycle`) is a round plus one turn of the genetic algorithm.

## The rules (never broken)

- Read the contact row first. Obey its stamp before acting.
- **Stamps:** `none` (free), `rest` (wait until `rest_until`), `never` (blocked forever).
- `never` is checked first, always. When in doubt, do not send.
- **Once a month.** After a send, the contact rests 30 days.
- **No cap on tries.** The machine keeps emailing, monthly, until the person unsubscribes.
- **Fail closed.** If the judge errors, the gate refuses.

## The genetic algorithm

Each template is one animal in a herd. Its fitness is one score built from both numbers:

```
score = smoothed(reply_rate) + RETURN_WEIGHT * smoothed(return_rate)
```

Every cycle: **start uniform**, then **favor winners** with more sends, **breed**
new templates by crossover and mutation off the winners, **always inject one true
random** template made from scratch, and **drop losers**. Two safety valves stop
it selecting on noise: rates are smoothed (Laplace), and no template is dropped
before `MIN_SENDS_TO_DROP`. The pool never fully dies.

The model writes templates. It does **not** write each send. Each send is a
template with the `{name}` slot filled, in pure Python.

## The gate

- **Layer 1, hard rules.** Pure Python, no model. Banned words (whole-word,
  case-insensitive so real surnames are safe), banned signs (em dash, `!!!`,
  `#1`), and a length limit. Fast, deterministic, always runs.
- **Layer 2, the judge.** An LLM asks the soft question: does this sound like
  JotPsych, not a robot? Run **once when a template is born** and cached. Send
  time never calls a model.

## Architecture: real logic, swappable seams

The brain never talks to the outside world directly. It talks through seams. Swap
a fake for a real provider and the brain does not change.

```
outbound/
  config.py     all the knobs and word lists
  db.py         SQLite, three tables, all reads/writes
  llm.py        model seam        FakeLLM  | RealLLM (Claude)
  channels.py   email seam        FakeEmail | PostmarkEmail
  sales.py      handoff seam      FakeSales (mock CRM)
  returns.py    returns feed seam FakeReturns (mock product data)
  gate.py       the two-layer quality gate
  writer.py     fill {name} + footer; generate templates
  learn.py      the genetic algorithm
  engine.py     the loop (sweep, route, send)
  dashboard.py  the read-only health report
main.py         CLI
tests/          41 offline tests
PLAN.md         the design, in Simplified Technical English
TESTS.md        the behavior spec, 60 cases
```

## Data model (three tables)

- **contacts** - one row per person. name, email, phone, stamp, rest_until, times_sent, status, replied_at, unsubscribed_at.
- **templates** - one row per email template. subject, body (with `{name}`), origin, sends, replies, returns, alive, gate_reason.
- **messages** - one row per real send (the receipt). contact_id, template_id, subject, body, sent_at, reply_at, reply_text.

Attribution is one join: a returned contact -> their last message -> the template that earned it.

## Running it

### 1. Prerequisites

- Python 3.9 or newer. Check with `python3 --version`.
- Nothing else for the offline demo: the core uses only the standard library.

### 2. Get the code and (optionally) install extras

From the project root (the folder holding `main.py`):

```bash
# The demo and the machine's core need NO third-party packages.
# Install these only to run the tests or to go live with real providers:
python3 -m pip install -r requirements.txt
```

### 3. Try it offline (no API keys, sends nothing real)

```bash
python3 main.py sim                  # simulated world: prints a fully populated dashboard
python3 main.py demo                 # seed fake data, run 3 cycles, print the dashboard
python3 main.py preview              # generate one template and print the finished email
python3 main.py check-llm            # make one model call, report pass/fail and the gate verdict
python3 -m pytest -q                 # run the offline test suite
```

To just *see* the dashboard with real numbers, run `python3 main.py sim`. It uses a
throwaway in-memory database and does not touch your real data.

`preview` and `check-llm` use the fake LLM until you set `ANTHROPIC_API_KEY`, then
they exercise real Claude. `check-llm` is the quickest way to confirm your key works.

### 4. Run against your own contact list

Prepare a CSV with a header row and columns `name,email,phone` (phone optional).
Then, from the project root:

```bash
python3 main.py init                     # create the SQLite database (outbound.db)
python3 main.py seed-contacts leads.csv  # load your contacts
python3 main.py seed-templates           # fill the starter template pool
python3 main.py cycle 1                  # run one cycle: sweep + send + evolve
python3 main.py dashboard                # read the health report
```

`main.py` with no arguments prints the full command list.

### 5. Go live with real providers

Set environment variables. Any provider left blank falls back to its fake, so you
can switch on one piece at a time. Without `POSTMARK_TOKEN` and `ANTHROPIC_API_KEY`
the machine stays fully in fake mode and sends nothing real.

```bash
export POSTMARK_TOKEN=...        # switches email to real Postmark
export OUTBOUND_FROM=hello@jotpsych.com
export ANTHROPIC_API_KEY=...     # switches the writer/judge to real Claude
export OUTBOUND_ADDRESS="JotPsych, <real physical address>"   # required by CAN-SPAM
# optional: export OUTBOUND_DB=/path/to/outbound.db   to choose where data lives
```

Then run one cycle whenever you want the machine to act. One command per cycle is
the whole operation:

```bash
python3 main.py cycle 1
```

### 6. Run it on a schedule (the "runs itself" part)

Point cron (or any job runner) at the cycle command. Daily at 9am, from the project
root, with keys loaded from a file:

```bash
# crontab -e
0 9 * * *  cd /path/to/project && . ./.env && python3 main.py cycle 1 >> run.log 2>&1
```

The 30-day rest per contact means a daily schedule still emails any one person at
most once a month.

### Stopping it

Create a file named `KILL` in the project root to halt sending immediately. Delete
it to resume.

```bash
touch KILL     # stop
rm KILL        # resume
```

## Safety and compliance

- **Kill switch.** Create a file named `KILL` in the working directory to halt the
  machine instantly. Delete it to resume. This is the human's stop button.
- **Volume caps.** `SENDS_PER_ROUND` and `DAILY_SEND_CAP` bound how much goes out.
- **Bounce breaker.** If one sweep sees more than `BOUNCE_BREAK` dead addresses,
  sending halts for that round.
- **CAN-SPAM.** Every email carries a `List-Unsubscribe` header, a Postmark-hosted
  unsubscribe link, and a physical mailing address.
- **Unsubscribe (Option B).** Postmark hosts the unsubscribe page and suppression
  list. Each round we poll it and set `never`. A stop-word reply is the instant
  safety net. No server of our own.

## What is mocked (out of scope for v1)

- **The sales pipeline.** `sales.notify()` records the handoff in memory. Swap in a real CRM.
- **The returns feed.** `returns.check()` returns a set list. Swap in real product data (match by email).
- **SMS.** Dropped for v1. Cold texting non-consented contacts is a TCPA problem, not a STOP-handling problem. The seam keeps it easy to add once consent exists.

## Tuning

Everything lives in `outbound/config.py`: the 30-day rest, `RETURN_WEIGHT`, the
banned-word lists, the caps, and the mailing address. Change these, not the logic.

## Tests

`pytest -q` runs 41 tests fully offline: stamps, the once-a-month rule, every gate
rule (including the Scunthorpe word-boundary fix), unsubscribe and bounce
handling, the sales handoff, the returns feed, the genetic algorithm, the kill
switch, the bounce breaker, and the CAN-SPAM footer. `TESTS.md` is the plain-language
spec behind them.
