"""The returns feed seam. Where a "return" comes from.

A reply arrives on email. A return does not: it is a product event (the person
signed up or logged back in). FakeReturns lets a test or demo declare who came
back. A real deploy queries product data and matches by email.
"""


class FakeReturns:
    def __init__(self):
        self.returned = []  # emails to report as returned on the next check

    def check(self):
        out, self.returned = self.returned, []
        return out


def get_returns():
    return FakeReturns()
