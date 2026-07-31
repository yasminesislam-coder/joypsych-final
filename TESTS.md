# Test List — JotPsych Outbound Machine

Written in Simplified Technical English.
Each test says: the setup, the action, and the correct result.
We prove the machine is safe before it sends under the company name.

## A. Stamps and rules (who may be contacted)

1. **never is blocked.** A contact has stamp `never`. The machine must not pick the contact.
2. **rest not expired is skipped.** `rest_until` is in the future. The machine must skip the contact today.
3. **rest expired is free.** `rest_until` is in the past. The machine may pick the contact.
4. **none is free.** A contact has stamp `none`. The machine may pick the contact.
5. **never is checked first.** A contact is both eligible and `never`. The machine must obey `never`.
6. **no cap.** A contact was sent to many times and never unsubscribed. The machine may still pick the contact, once the rest expires.

## B. Send behavior (the once-a-month rule)

7. **Rest after send.** The machine sends a message. It sets `rest_until` to today + 30 days.
8. **Count after send.** The machine sends a message. It adds 1 to `times_sent`.
9. **Once a month.** A contact was sent to 10 days ago. The machine must not send again today.
10. **A message row is written.** After a send, one row exists in `messages` with the contact, the template, the body, `status = sent`, and `sent_at`.

## C. The gate (brand safety)

The gate has two layers:
- **Layer 1 — hard rules.** Pure Python. A banned-word list. No LLM. Runs first, every time. Fast and deterministic.
- **Layer 2 — the LLM judge.** Only for the soft question: "does this sound like JotPsych, not a robot?"

### C1. Bad words — Layer 1 (pure Python, no API)

The gate holds a banned-word list. If a message contains any banned word, the gate fails it.
The match is case-insensitive. These tests run in plain Python. They are fast and always run.

11. **AI clichés are refused.** A message with any of these fails:
    "delve", "leverage", "seamless", "elevate", "unlock", "tapestry", "in today's fast-paced world",
    "navigate the landscape", "supercharge", "revolutionize", "game-changer", "cutting-edge", "at the end of the day".
12. **Spam words are refused.** A message with any of these fails:
    "act now", "limited time", "risk-free", "click here", "buy now", "100% free", "guarantee", "!!!".
13. **Overclaims are refused.** A message with any of these fails:
    "best in the world", "#1", "the only", "never fails".
14. **Swear words are refused.** A message with any profanity fails. The gate holds a profanity list.
15. **The em dash is refused.** A message that contains the em dash character fails. We do not use it.
16. **Other AI tells are refused.** A message with these patterns fails:
    "not only ... but also", "that said", "when it comes to", "in conclusion", "furthermore", "moreover".
17. **Case does not matter.** "DELVE", "Delve", and "delve" all fail.
18. **Clean message passes Layer 1.** A message with no banned word and no banned sign passes to Layer 2.
19. **The reason names the hit.** A failed message reports which banned word or sign it hit.

### C2. Voice and length (Layer 2 and limits)

20. **Too long is refused.** A message is longer than the limit. The gate fails it.
21. **Off-brand is refused.** A message does not sound like JotPsych. The judge fails it.
22. **Good message passes.** An on-brand, human, short message. The gate passes it.

### C3. What happens after a fail

23. **A refused message is not sent.** The gate fails a message. The machine must not call `send()`.
24. **A refused message is logged.** The machine writes a `messages` row with `status = blocked` and a `block_reason`.
25. **Fail closed.** The LLM judge errors or times out. The gate refuses. It never passes by accident.
26. **Rewrite cap.** The gate fails a message. The machine rewrites once. If it fails again, it skips. It never loops.

## D. Replies and unsubscribe

27. **Sweep runs first.** Each round, the machine calls `fetch_replies()` and `returns.check()` before it selects a contact.
28. **Stop word sets never.** A reply contains "stop" or "unsubscribe". The machine sets stamp `never`.
29. **Suppression sets never.** The email provider reports an unsubscribe. The machine sets stamp `never`.
30. **Unsubscribe records the time.** When a contact becomes `never`, the machine sets `unsubscribed_at`.
31. **Positive reply is a hot lead.** A contact replies with interest. The machine sets status `replied` and `replied_at`.
32. **Hot lead goes to sales now.** An interested reply calls `sales.notify()` in the same round, not at month end.
33. **Stop does not go to sales.** A stop word sets `never`. It does not call `sales.notify()`.
34. **Return is recorded.** The returns feed reports a contact came back. The machine sets status `returned` and adds 1 to the template `returns`.
35. **Reply time is saved.** A reply updates `reply_at` and `reply_text` on the message row.

## E. Learning (genetic algorithm)

The unit is a template: the whole email, with a `{name}` slot.

36. **Fill the name.** The writer fills `{name}` with the contact name. Pure Python. No model, no claimed facts.
37. **Update adds counts.** A send adds 1 to the template `sends`. A reply adds 1 to `replies`. A return adds 1 to `returns`.
38. **Score uses both.** The score is `reply_rate + (RETURN_WEIGHT × return_rate)`. A return moves the score more than a reply.
39. **Start uniform.** With no scores yet, every template gets an equal share of sends.
40. **Favor winners.** A template with a high score gets a bigger share of sends than a low one.
41. **Crossover breeds a child.** The machine mixes two strong templates into a new `alive` template, origin `crossover`.
42. **Mutation breeds a child.** The machine changes one strong template a little into a new `alive` template, origin `mutation`.
43. **Always try true random.** Every cycle, the machine adds at least one brand new random template, origin `random`, made from scratch, not from winners.
44. **Drop marks a loser.** A template with enough sends and a low score is set `alive = false`.
45. **Dropped is never picked.** A template with `alive = false` is never chosen.
46. **The pool never dies.** After breeding and dropping, at least one template stays alive to send.

## F. Attribution (traceable impact)

47. **Return traces to one template.** A returned contact joins to one message and one template. The trail is complete.
48. **Earnings are countable.** The dashboard counts returns per template and in total.

## G. The dashboard (the human phase)

The dashboard is read only. It never sends.

49. **Top templates are shown.** The dashboard lists the best templates by score, with text and origin.
50. **Success rate over time.** The dashboard shows replies per send and returns per send, per cycle.
51. **Unsubscribe rate over time.** The dashboard shows `never` per send, per cycle, using `unsubscribed_at`.
52. **Volume is shown.** The dashboard shows sends, replies, returns, and hot leads sent to sales, per cycle.
53. **Gate health is shown.** The dashboard counts `blocked` messages and the top `block_reason` values.
54. **Pool health is shown.** The dashboard shows how many contacts are still eligible.
55. **Diversity is shown.** The dashboard shows how many templates are alive and the split of origins.
56. **Read only.** The dashboard never calls `send()`.

## H. The seam (real vs fake hands)

57. **Tests use the fake hand.** Tests run with the fake email sender and fake LLM. No real message is sent.
58. **Swap does not change the brain.** The engine gives the same result with the real hand or the fake hand.
59. **Sales is mocked in tests.** `sales.notify()` records the handoff. No real CRM call.
60. **Returns feed is mocked in tests.** `returns.check()` returns a set list. No real product call.

## I. Compliance (CAN-SPAM, Option B)

61. **Every email has an unsubscribe link.** A sent email contains the Postmark unsubscribe link and a `List-Unsubscribe` header.
62. **Every email has a mailing address.** A sent email contains JotPsych's physical mailing address.
63. **Suppression poll sets never.** A new address on the Postmark suppression list is set to `never` with `unsubscribed_at` on the next round.

## Priority

The safety tests come first. If these fail, the machine must not run:
- Section A (stamps), Section C (gate), Section D (unsubscribe).

These three sections are the promise: safe to send under the company name, unattended.
