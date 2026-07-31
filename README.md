# JotPsych Outbound Machine

## TL;DR

This machine wins back clinicians who tried JotPsych and left.

You give it a list of names and emails. It writes outreach, checks each email against
a strict brand gate, sends it, and reads what comes back. It teaches itself which
emails work. Good replies go to sales. Unsubscribes are honored forever. A human
watches a dashboard about one hour a month.

A scheduler (cron) runs one command on a timer. That command sends the next batch.
The machine sends nothing real until you set `POSTMARK_TOKEN`. The website never
sends. It only uploads contacts and shows the dashboard.

## Run it yourself

You need Python 3.9 or newer. Check it: `python3 --version`.

**1. Get the code.**

```bash
git clone https://github.com/yasminesislam-coder/joypsych-final.git
cd joypsych-final
```

**2. See it run offline.** This uses fake data. It sends no real email.

```bash
python3 main.py demo
```

**3. Open the website.** This is the two-tab app: a dashboard and an upload page.

```bash
python3 -m pip install flask
python3 main.py seed-demo        # fill the dashboard with mock data
python3 web/app.py               # then open http://127.0.0.1:5001
```

On the site, the **Dashboard** tab shows the numbers, the charts, and the best emails.
The **Upload** tab loads a CSV. Try `demo/leads_batch1.csv`, then `demo/leads_batch2.csv`.

**4. Run the tests.**

```bash
python3 -m pytest -q
```

Other commands: `python3 main.py preview` prints one email. `python3 main.py sim`
prints a full dashboard. Run `python3 main.py` with no argument to list every command.

## What it does

- **Runs itself.** Cron runs one cycle on a timer. A kill switch and caps keep it safe.
- **Improves itself.** Winning templates breed new templates. No person rewrites code.
- **Protects the brand.** A two-layer gate refuses AI-sounding, spammy, or off-brand email.
- **Proves impact.** Every return traces back to the template that earned it.
- **Ships today.** Real logic sits behind swappable seams. Set two keys to go live.

For the full design, see [PLAN.md](PLAN.md). For the behavior spec, see [TESTS.md](TESTS.md).

## Run it against your list

Give it a CSV with a header row and columns `name,email,phone` (phone optional).

```bash
python3 main.py init                     # create the database (demo.db)
python3 main.py seed-contacts leads.csv  # load your contacts
python3 main.py seed-templates           # add the starter templates
python3 main.py cycle 1                  # sweep replies, send a batch, then learn
python3 main.py dashboard                # print the health report
```

## The website

A small Flask app with two tabs. It shares the same database. Step 3 above shows how
to run it.

- **Upload.** Load a CSV, then review, then confirm. The review shows new contacts,
  contacts already in the system, and invalid rows. Existing contacts are always
  skipped, so their unsubscribe and cooldown state stays safe.
- **Dashboard.** It shows the health numbers, weekly trend charts, and the best
  templates in full. It is read only. It never sends.

> **Security TODO before hosting.** The website is localhost only and has no login.
> It holds names, emails, and phones. Do not put it on a network as is. Add a login
> and HTTPS first.

## How email is sent

There is no always-on sender. Email goes out only when a cycle runs. Cron runs cycles.

```
cron  ->  python3 main.py cycle 1  ->  sweep inbound  ->  send batch  ->  learn
```

- **The email channel is a seam.** With no `POSTMARK_TOKEN`, it is a fake. It records
  the email and sends nothing. With the token set, it posts each email to Postmark.
- **Each contact rests 30 days after a send.** So a daily cron emails one person at
  most once a month.
- **The website never sends.** No click can trigger an email.

## Go live

Set the providers, then install the scheduler.

```bash
export POSTMARK_TOKEN=...        # real email send and suppression list
export OUTBOUND_FROM=hello@jotpsych.com
export OUTBOUND_ADDRESS="JotPsych, <real physical address>"   # required by CAN-SPAM
export ANTHROPIC_API_KEY=...     # real writing and judging (fake without it)
```

```bash
# crontab -e  (run one cycle each morning)
0 9 * * *  cd /path/to/project && . ./.env && python3 main.py cycle 1 >> run.log 2>&1
```

## Safety

- **Kill switch.** Create a file named `KILL` in the project root to stop sending.
  Delete it to resume.
- **Caps.** `SENDS_PER_ROUND` and `DAILY_SEND_CAP` limit how much goes out.
- **Bounce breaker.** Too many dead addresses in one sweep halts the round.
- **CAN-SPAM.** Every email carries an unsubscribe link, a `List-Unsubscribe` header,
  and a physical address.
- **Unsubscribe.** Postmark hosts the unsubscribe page and suppression list. Each
  round we read that list and set the contact to `never`. A stop-word reply also
  sets `never` at once.

## What is mocked

- **Sales handoff.** `sales.notify()` records the lead. Swap in a real CRM later.
- **Returns feed.** `returns.check()` returns a set list. Swap in real product data.
- **SMS.** Out for v1. Cold texting without consent is a legal problem (TCPA).

## Config

All the knobs live in [outbound/config.py](outbound/config.py): the 30-day rest,
`RETURN_WEIGHT`, the banned-word lists, the caps, and the mailing address. Change
these, not the logic.

## Tests

```bash
python3 -m pytest -q
```

The tests run fully offline. They cover the stamps, the once-a-month rule, the gate,
unsubscribe and bounce handling, the sales handoff, the returns feed, the genetic
algorithm, the dashboard, the kill switch, and the CAN-SPAM footer.
