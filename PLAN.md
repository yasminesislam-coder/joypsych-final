# JotPsych Outbound Machine — Plan

Written in Simplified Technical English. Short sentences. Simple words.

## 1. What we build

An outbound machine.

You give it a list: names, emails, phone numbers.
The machine reaches out to win back people who tried JotPsych and left.
It runs on its own. You check it about one hour a month.

## 2. The five requirements

1. **Real.** The machine sends and receives through a real email API/MCP.
   Give it a real list, and it goes live tomorrow. (Email only for v1. SMS is out, see below.)
2. **It gives the human a dashboard.** Hot leads go to sales at once, on their own.
   The human just watches a dashboard for the health of the machine, about one hour a month.
3. **Trusted quality gate.** Every message passes a check before it leaves.
   The check is good enough to send under the company name with nobody watching.
4. **Metrics, learning, and receipts.** It shows what it did, how it got better, and what it earned.
5. **Taste.** The machine knows what is on-brand. It refuses off-brand messages before it sends them.

## 3. The loop

The machine works in rounds. One round does this:

1. Sweep for new replies, and check the returns feed. Update the rows.
2. Route replies now. A stop word sets `never`. An interested reply goes to sales at once (mocked). A return sets status `returned`.
3. Pick a contact. Obey the stamp first.
4. Choose a template. Start uniform, then favor winners.
5. Fill the `{name}` slot. Pure Python. No claimed facts.
6. Run the quality gate. If it fails, rewrite once, then skip.
7. Send the message through a real API/MCP.
8. Write the result to the database.
9. Learn (genetic algorithm): score templates, favor winners, breed new ones, always add true random, drop losers.

The dashboard is separate from the loop. The human opens it any time to watch the machine's health.

## 4. The rules (never break these)

1. Read the contact row first.
2. Obey the stamp before any action.
   - **none** — the contact is free to receive a message.
   - **rest** — do not touch before `rest_until`.
   - **never** — the contact said stop. Do not contact again, ever.
3. Check the `never` stamp first, every time.
4. When in doubt, do not send.
5. **Once a month, maximum.** After a send, set `rest_until` to 30 days later.
   The machine cannot pick the contact before that date.
6. **Unsubscribe means never.** When a contact says stop, set the `never` stamp.
   A `never` contact never receives a message again.
7. **No cap.** The machine keeps emailing, once a month, until the person unsubscribes.
8. **Fail closed.** If the LLM judge errors or times out, the gate refuses. It never passes by accident.
9. **Rewrite cap.** On a gate fail, the machine rewrites once. If it fails again, skip. Never loop.

## 4b. Stamp definitions

Three stamps: **none, rest, never.**

| stamp | meaning | what sets it | does it clear? |
|-------|---------|--------------|----------------|
| **none** | Free. The machine may contact this person. | The start state for every contact. | It is the default. |
| **rest** | Resting. Do not contact before `rest_until`. | A send. Set `rest_until` = today + 30 days. | Yes. When `rest_until` passes, the person is free. |
| **never** | Blocked forever. The person refused. | An unsubscribe link, or a "stop" word in a reply. | No. This never clears. |

**No cap.** The machine keeps emailing, once a month, until the person unsubscribes.
Only `never` stops it for good.

**The selector reads a stamp in this order:**
1. `never`? → Block. Stop here.
2. `rest` and `rest_until` in the future? → Skip today.
3. Else (`none`, or `rest` expired) → Eligible.

`never` is first, always.

## 5. Database schema

We use SQLite. One file. No server.

### Table: contacts
One row per person.

| column      | type    | meaning                                  |
|-------------|---------|------------------------------------------|
| id              | integer  | the key                                  |
| name            | text     | the person's name                        |
| email           | text     | the email address                        |
| phone           | text     | the phone number                         |
| stamp           | text     | none / rest / never                      |
| rest_until      | date     | do not touch before this date            |
| times_sent      | integer  | count of messages sent                   |
| status          | text     | dormant / contacted / replied / returned |
| replied_at      | datetime | when they first replied with interest    |
| unsubscribed_at | datetime | when they became `never`                 |

`replied_at` and `unsubscribed_at` give the dashboard a clock, so it can show rates over time.

### Table: templates
One row per email template. This table learns.
A template is the whole email, with `{name}` as the only fill slot.
We know only name, email, and phone. We never claim a fact we do not have.

| column   | type    | meaning                                 |
|----------|---------|-----------------------------------------|
| id       | integer | the key                                 |
| text     | text    | the email, with the `{name}` slot       |
| origin   | text    | random / crossover / mutation           |
| sends    | integer | how many we sent                        |
| replies  | integer | how many replied                        |
| returns  | integer | how many came back                      |
| alive    | boolean | true = in use, false = dropped          |

Making an email is simple: fill the `{name}` slot. Pure Python. No model at send time.

### Table: messages
One row per attempt. This is the receipt.

| column       | type     | meaning                            |
|--------------|----------|------------------------------------|
| id           | integer  | the key                            |
| contact_id   | integer  | who we sent to (→ contacts.id)     |
| template_id  | integer  | which template (→ templates.id)    |
| body         | text     | the text we made                   |
| status       | text     | sent / blocked                     |
| block_reason | text     | why the gate refused, if blocked   |
| sent_at      | datetime | when we sent it, if sent           |
| reply_at     | datetime | when they replied, if any          |
| reply_text   | text     | what they said back                |

Every attempt gets a row. A blocked attempt has `status = blocked`, a `block_reason`, and no `sent_at`.
This gives the dashboard its gate health, and keeps the full receipt.
The dashboard reads these three tables. We store no extra table.

## 5b. The genetic algorithm (learning)

Each template is one animal in a herd. Its fitness is a score built from both numbers.
The machine runs six moves. No person rewrites code.

**1. Start uniform.**
With no scores yet, every template gets an equal share of sends. A fair start.

**2. Score.**
We use both numbers, replies and returns, in one score:

    score = reply_rate + (RETURN_WEIGHT × return_rate)

- `reply_rate` = replies / sends. It moves fast, so the machine learns early.
- `return_rate` = returns / sends. It is the real prize, so it is weighted heavy.
- `RETURN_WEIGHT` is a knob in `config.py` (for example 10). A return counts like ten replies.

Early on, returns are near zero, so replies drive the learning. A fast start.
Later, returns grow and take over the score, so the herd aims at real customers.

**3. Select by fitness.**
A template with a higher score gets a bigger share of the next round.
A weak one shrinks. This is the "sent more" for winners.

**4. Breed off winners.**
- **Crossover.** Take two strong templates. Mix them into a child. Origin `crossover`.
- **Mutation.** Take one strong template. Change it a little. Origin `mutation`.
- Children join the herd and get a fair trial.

**5. Always inject true random.**
Every cycle, add at least one brand new random template, made from scratch. Origin `random`.
This slice never closes. It stops the herd from going stale.
It keeps a real chance to beat today's best.

**6. Drop losers.**
A template with enough sends and a low score is set `alive = false`. It is never picked again.
At least one template always stays alive.

The model (Claude) is used for three jobs only: make the first templates, breed new ones, and make the true random ones.
It is not used to write each send. Each send is a template with the `{name}` slot filled.

## 6. Attribution

A contact returns → find their message row → find the template row.
One join gives the full trail: who came back, from which message, from which template.

## 6a. Unsubscribe (Option B, no server)

This path is safety critical. It must never fail. So we lean on Postmark for it.

- **Every email carries the unsubscribe.** Each email has a `List-Unsubscribe` header and a visible unsubscribe link, both hosted by Postmark. Each email also carries JotPsych's physical mailing address. This meets CAN-SPAM.
- **A click suppresses at Postmark.** When a person unsubscribes, Postmark adds the address to its suppression list. Postmark then refuses to deliver to it, so even a stray send cannot reach them.
- **We poll to stay in sync.** Each round, the machine reads the Postmark suppression list. Any new address is set to stamp `never` with `unsubscribed_at`.
- **Safety net.** A reply with a stop word also sets `never` at once, without waiting for the poll.

No server. Postmark hosts the page. We only poll.

## 6b. Inbound to sales (immediate)

A hot lead must not wait for month end.

When the sweep finds an interested reply, the machine calls `sales.notify(contact, reply)` at once.
This hands the lead to sales in the same round.
For now `sales.notify()` is mocked. It writes the handoff to a log or a simple table.
Later we swap it for a real CRM or a real inbox. The brain does not change.

A stop word does not go to sales. It sets `never`.

## 6d. The returns feed (where a "return" comes from)

A reply arrives on email. A **return** does not. A return is a product event:
the person signed up or logged back in to JotPsych.

So the machine reads a second seam each round: `returns.check()`.
It answers one question: which contacts came back since last time?
For now `returns.check()` is mocked. Later we swap it for real product data (match by email). The brain does not change.

When the feed reports a contact came back, the machine sets status `returned` and adds 1 to that template's `returns`.

## 6c. The dashboard (the human phase)

The human does not chase leads. Sales does that. The human watches the health of the machine.
The dashboard reads the three tables and shows:

- **Top templates.** The best emails by score. Read the winning text and its origin.
- **Success rate over time.** Replies per send, and returns per send, per cycle. Is it going up?
- **Unsubscribe rate over time.** `never` per send, per cycle. Is it going up? A warning sign.
- **Volume.** Sends, replies, returns, and hot leads sent to sales, per cycle.
- **Gate health.** How many messages the gate refused, and the top reasons.
- **Pool health.** How many contacts are still eligible. Low means "add more names".
- **Diversity.** How many templates are alive, and the split of origins (random, crossover, mutation).

The dashboard is read only. It never sends. It is safe to open any time.

## 7. What we do NOT build (no overengineering)

- No model training. Learning = keep winners + breed new + drop losers.
- No heavy web app. The dashboard is simple.
- No extra table for the dashboard. We read the three tables.
- No real CRM yet. Sales handoff is mocked behind the seam.

## 8. Stack and APIs

| part | choice | jobs |
|------|--------|------|
| Language | Python | — |
| Database | SQLite | one file, no server |
| Email | Postmark | send, read replies, suppression list |
| LLM | Anthropic Claude | make templates, judge templates |
| New templates | Auto | the machine uses them at once; each template is judged once at birth |

**SMS is out for v1.** Cold texting people who did not consent is likely illegal in the US (TCPA),
no matter how well we handle STOP. A dormant trial list is not consent.
The seam keeps SMS easy to add later, once consent exists.

The seam (`channels.py`, `llm.py`) hides these providers.
We can swap any provider later. The brain does not change.

Replies come by polling, not webhooks. Each round, `fetch_replies()` asks the provider for new replies.

## 9b. The website (v1)

A thin face over the machine. Two tabs. Flask, server-rendered, shares the same
`outbound.db`. The website never sends: sending stays on the scheduler.

**Tab 1 - Upload contacts.** Upload a CSV, then preview, then confirm.
- The preview sorts every row into three groups: **new** (will add), **already in
  system** (skip, shown with their status), and **invalid** (skip).
- Confirm adds only the new rows. Existing contacts are never touched, so a
  `never` or a resting contact keeps their state. This protects unsubscribe and
  cooldown. It falls out of the unique-email insert-or-ignore, and the preview
  makes it visible.

**Tab 2 - Dashboard.** Read only.
- Numbers: the cards from `dashboard.build`.
- Trends over time: reply rate and unsubscribe rate per week, volume per week,
  built from the timestamps (`sent_at`, `reply_at`, `unsubscribed_at`, `returned_at`).
- Best performing templates: the top table.

**One schema add:** `contacts.returned_at`, so returns can be charted over time.

**Security:** localhost only for v1. TODO before hosting: add authentication and
put it behind HTTPS. It holds PII (names, emails, phones) and business metrics.

**Files (new):** `web/app.py`, `web/templates/*.html`, `web/static/style.css`.
Everything else is reused.

## 9. Next steps

1. Write the test list. Prove correct behavior for each situation.
2. Write the code, guided by the tests.
3. Wire the real APIs/MCPs for send and receive.
