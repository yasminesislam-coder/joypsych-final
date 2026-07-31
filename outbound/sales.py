"""The sales handoff seam. A hot lead must not wait for month end.

FakeSales records the handoff in memory (out of scope for v1). A real deploy
swaps in a CRM call. The brain does not change.
"""


class FakeSales:
    def __init__(self):
        self.handoffs = []  # {"email","name","reply"}

    def notify(self, contact, reply_text):
        self.handoffs.append({
            "email": contact["email"],
            "name": contact["name"],
            "reply": reply_text,
        })


def get_sales():
    return FakeSales()
