"""All the knobs in one place. Change these, not the logic."""
import os

# --- storage ---
DB_PATH = os.environ.get("OUTBOUND_DB", "outbound.db")

# --- the once-a-month rule ---
REST_DAYS = 30          # after a send, rest this many days before the next
SENDS_PER_ROUND = 50    # how many emails one round may send
DAILY_SEND_CAP = 200    # hard ceiling per day, whatever the rounds ask for
BOUNCE_BREAK = 10       # if one sweep sees more than this many dead addresses, halt sends

# --- the score (learning) ---
RETURN_WEIGHT = 10      # a return counts like this many replies
MIN_SENDS_TO_DROP = 30  # never judge a template dead before this many sends
DROP_FRACTION = 0.5     # drop a template scoring below this share of the best
TOP_K = 3               # how many winners breed each cycle
RANDOM_PER_CYCLE = 1    # true-random templates added each cycle (never zero)

# --- the gate ---
MAX_BODY_CHARS = 900    # an email body longer than this is refused

# Layer 1 hard rules. Pure Python, no model. Whole-word match, case-insensitive.
BANNED_WORDS = [
    # AI cliches
    "delve", "leverage", "seamless", "elevate", "unlock", "tapestry",
    "in today's fast-paced world", "navigate the landscape", "supercharge",
    "revolutionize", "game-changer", "cutting-edge", "at the end of the day",
    "furthermore", "moreover", "in conclusion", "that said", "when it comes to",
    # spam
    "act now", "limited time", "risk-free", "click here", "buy now",
    "100% free", "guarantee",
    # overclaims
    "best in the world", "the only", "never fails",
]
# Matched as raw substrings (word boundaries do not apply to punctuation).
BANNED_SIGNS = ["—", "!!!", "#1"]  # em dash, triple bang, number-one claim
PROFANITY = ["damn", "hell", "crap", "shit", "fuck", "ass", "bastard"]

# --- inbound ---
STOP_WORDS = ["stop", "unsubscribe", "remove me", "opt out", "opt-out"]
AUTO_REPLY_MARKERS = ["out of office", "automatic reply", "auto-reply",
                      "away from my desk", "on vacation", "delivery failure",
                      "undeliverable"]

# --- sign-off (we always add this; the model never signs) ---
SIGNOFF = "Thanks,\nThe JotPsych Team"

# --- compliance (CAN-SPAM) ---
MAILING_ADDRESS = os.environ.get(
    "OUTBOUND_ADDRESS",
    "JotPsych, 123 Placeholder St, San Francisco, CA 94105",  # replace before go-live
)

# --- kill switch ---
# Create this file to halt the machine. Delete it to resume. A human's stop button.
KILL_FILE = os.environ.get("OUTBOUND_KILL_FILE", "KILL")

# --- providers (real hands). Empty = use the fake hand. ---
POSTMARK_TOKEN = os.environ.get("POSTMARK_TOKEN", "")
POSTMARK_STREAM = os.environ.get("POSTMARK_STREAM", "outbound")
FROM_EMAIL = os.environ.get("OUTBOUND_FROM", "hello@jotpsych.com")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("OUTBOUND_MODEL", "claude-sonnet-5")
