"""The database. Three tables. SQLite, one file, no server.

contacts   - one row per person (the notebook page)
templates  - one row per email template (this table learns)
messages   - one row per real send (the receipt)
"""
import sqlite3
from datetime import datetime, timedelta

from . import config


def now():
    return datetime.now()


def iso(dt):
    return dt.isoformat(timespec="seconds") if dt else None


def connect(path=None):
    con = sqlite3.connect(path or config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY,
    name            TEXT,
    email           TEXT UNIQUE,
    phone           TEXT,
    stamp           TEXT DEFAULT 'none',      -- none / rest / never
    rest_until      TEXT,                     -- do not touch before this
    times_sent      INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'dormant',   -- dormant/contacted/replied/returned
    replied_at      TEXT,
    unsubscribed_at TEXT
);

CREATE TABLE IF NOT EXISTS templates (
    id          INTEGER PRIMARY KEY,
    subject     TEXT,
    body        TEXT,                         -- holds the {name} slot
    origin      TEXT,                         -- seed/random/crossover/mutation
    sends       INTEGER DEFAULT 0,
    replies     INTEGER DEFAULT 0,
    returns     INTEGER DEFAULT 0,
    alive       INTEGER DEFAULT 1,
    gate_reason TEXT,                         -- null = passed the gate at birth
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    contact_id  INTEGER REFERENCES contacts(id),
    template_id INTEGER REFERENCES templates(id),
    subject     TEXT,
    body        TEXT,
    sent_at     TEXT,
    reply_at    TEXT,
    reply_text  TEXT
);
"""


def init(con):
    con.executescript(SCHEMA)
    con.commit()


# --- contacts ---------------------------------------------------------------

def add_contact(con, name, email, phone=""):
    con.execute(
        "INSERT OR IGNORE INTO contacts (name, email, phone) VALUES (?,?,?)",
        (name, email, phone),
    )
    con.commit()


def eligible_contacts(con, limit):
    """Free to contact: not `never`, and not resting."""
    return con.execute(
        """SELECT * FROM contacts
           WHERE stamp != 'never'
             AND (rest_until IS NULL OR rest_until <= ?)
           ORDER BY times_sent ASC, id ASC
           LIMIT ?""",
        (iso(now()), limit),
    ).fetchall()


def all_contacts(con):
    return con.execute("SELECT * FROM contacts").fetchall()


def contact_by_email(con, email):
    return con.execute(
        "SELECT * FROM contacts WHERE lower(email) = lower(?)", (email,)
    ).fetchone()


def mark_never(con, contact_id):
    con.execute(
        "UPDATE contacts SET stamp='never', unsubscribed_at=? WHERE id=? "
        "AND stamp != 'never'",
        (iso(now()), contact_id),
    )
    con.commit()


def mark_sent(con, contact_id):
    rest = iso(now() + timedelta(days=config.REST_DAYS))
    con.execute(
        """UPDATE contacts
           SET stamp='rest', rest_until=?, times_sent=times_sent+1,
               status=CASE status WHEN 'dormant' THEN 'contacted' ELSE status END
           WHERE id=?""",
        (rest, contact_id),
    )
    con.commit()


def mark_replied(con, contact_id):
    con.execute(
        "UPDATE contacts SET status='replied', replied_at=? WHERE id=? "
        "AND status != 'returned'",
        (iso(now()), contact_id),
    )
    con.commit()


def mark_returned(con, contact_id):
    con.execute("UPDATE contacts SET status='returned' WHERE id=?", (contact_id,))
    con.commit()


def sent_today(con):
    start = iso(now().replace(hour=0, minute=0, second=0, microsecond=0))
    row = con.execute(
        "SELECT COUNT(*) c FROM messages WHERE sent_at >= ?", (start,)
    ).fetchone()
    return row["c"]


# --- templates --------------------------------------------------------------

def add_template(con, subject, body, origin, alive=True, gate_reason=None):
    cur = con.execute(
        """INSERT INTO templates (subject, body, origin, alive, gate_reason, created_at)
           VALUES (?,?,?,?,?,?)""",
        (subject, body, origin, 1 if alive else 0, gate_reason, iso(now())),
    )
    con.commit()
    return cur.lastrowid


def alive_templates(con):
    return con.execute(
        "SELECT * FROM templates WHERE alive=1 AND gate_reason IS NULL"
    ).fetchall()


def all_templates(con):
    return con.execute("SELECT * FROM templates").fetchall()


def bump_template(con, template_id, field):
    assert field in ("sends", "replies", "returns")
    con.execute(f"UPDATE templates SET {field}={field}+1 WHERE id=?", (template_id,))
    con.commit()


def set_alive(con, template_id, alive):
    con.execute("UPDATE templates SET alive=? WHERE id=?", (1 if alive else 0, template_id))
    con.commit()


# --- messages ---------------------------------------------------------------

def add_message(con, contact_id, template_id, subject, body):
    cur = con.execute(
        """INSERT INTO messages (contact_id, template_id, subject, body, sent_at)
           VALUES (?,?,?,?,?)""",
        (contact_id, template_id, subject, body, iso(now())),
    )
    con.commit()
    return cur.lastrowid


def last_message_for(con, contact_id):
    return con.execute(
        "SELECT * FROM messages WHERE contact_id=? ORDER BY sent_at DESC LIMIT 1",
        (contact_id,),
    ).fetchone()


def record_reply(con, message_id, text):
    con.execute(
        "UPDATE messages SET reply_at=?, reply_text=? WHERE id=?",
        (iso(now()), text, message_id),
    )
    con.commit()
