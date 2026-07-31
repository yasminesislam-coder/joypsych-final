"""The email seam. Send, and read what comes back.

FakeEmail records everything in memory, so tests and demos send nothing real.
PostmarkEmail is the real hand. Swap one for the other; the brain is unchanged.

Every send carries the CAN-SPAM footer (built in writer.py) and a
List-Unsubscribe header, so unattended sending stays legal.
"""
from . import config


UNSUB_HEADER = "List-Unsubscribe"


class FakeEmail:
    def __init__(self):
        self.outbox = []           # every sent email, as a dict
        self.inbox = []            # replies to hand back: {"email","text"}
        self.suppressed = []       # emails that unsubscribed at the provider
        self.bounced = []          # dead addresses

    def send(self, to, subject, body, unsub_link):
        self.outbox.append({
            "to": to, "subject": subject, "body": body,
            "headers": {UNSUB_HEADER: f"<{unsub_link}>"},
        })

    def fetch_replies(self):
        out, self.inbox = self.inbox, []
        return out

    def fetch_unsubscribes(self):
        out, self.suppressed = self.suppressed, []
        return out

    def fetch_bounces(self):
        out, self.bounced = self.bounced, []
        return out


class PostmarkEmail:
    """Real hand. Uses Postmark for sending, suppressions, and bounces."""
    BASE = "https://api.postmarkapp.com"

    def __init__(self):
        import requests
        self.requests = requests
        self.headers = {
            "X-Postmark-Server-Token": config.POSTMARK_TOKEN,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def send(self, to, subject, body, unsub_link):
        self.requests.post(
            f"{self.BASE}/email",
            json={
                "From": config.FROM_EMAIL,
                "To": to,
                "Subject": subject,
                "TextBody": body,
                "MessageStream": config.POSTMARK_STREAM,
                "Headers": [{"Name": UNSUB_HEADER, "Value": f"<{unsub_link}>"}],
            },
            headers=self.headers,
            timeout=20,
        )

    def fetch_replies(self):
        # Postmark delivers inbound by webhook. A real deploy stores those to a
        # table and reads them here. Left empty for the polling skeleton.
        return []

    def fetch_unsubscribes(self):
        url = f"{self.BASE}/message-streams/{config.POSTMARK_STREAM}/suppressions/dump"
        try:
            r = self.requests.get(url, headers=self.headers, timeout=20).json()
            return [s["EmailAddress"] for s in r.get("Suppressions", [])]
        except Exception:
            return []

    def fetch_bounces(self):
        try:
            r = self.requests.get(f"{self.BASE}/bounces?count=500&offset=0",
                                  headers=self.headers, timeout=20).json()
            return [b["Email"] for b in r.get("Bounces", []) if b.get("Inactive")]
        except Exception:
            return []


def unsub_link_for(email):
    """Postmark hosts the unsubscribe page (Option B). No server of our own."""
    return f"https://unsubscribe.postmarkapp.com/{config.POSTMARK_STREAM}?e={email}"


def get_channel():
    return PostmarkEmail() if config.POSTMARK_TOKEN else FakeEmail()
