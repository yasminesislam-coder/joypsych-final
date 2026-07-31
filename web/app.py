"""The website. Two tabs: upload contacts, and the health dashboard.

Localhost only for v1. No authentication. See the SECURITY TODO in the README
before hosting this anywhere.

Run:  python3 web/app.py   then open http://127.0.0.1:5001
(Port 5001 avoids the macOS AirPlay Receiver, which squats on 5000.)
"""
import csv
import io
import json
import os
import re
import sys
import tempfile
import uuid

# make the `outbound` package importable no matter where we launch from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, flash, redirect, render_template, request, url_for

from outbound import db, dashboard

app = Flask(__name__)
app.secret_key = "localhost-dev-only"  # only used for flash messages; localhost only

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def open_db():
    con = db.connect()
    db.init(con)
    return con


# --- pending-upload storage (survives the preview -> confirm hop) ------------

def _pending_path(token):
    return os.path.join(tempfile.gettempdir(), f"outbound_upload_{token}.json")


def _save_pending(token, rows):
    with open(_pending_path(token), "w") as f:
        json.dump(rows, f)


def _load_pending(token):
    try:
        with open(_pending_path(token)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _clear_pending(token):
    try:
        os.remove(_pending_path(token))
    except OSError:
        pass


def _status_label(c):
    if c["stamp"] == "never":
        return "unsubscribed"
    if c["stamp"] == "rest" and c["rest_until"] and c["rest_until"] > db.iso(db.now()):
        return f"resting until {c['rest_until'][:10]}"
    return c["status"]


# --- routes -----------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("dashboard_view"))


@app.route("/dashboard")
def dashboard_view():
    con = open_db()
    return render_template(
        "dashboard.html",
        d=dashboard.build(con),
        trends_json=json.dumps(dashboard.trends(con)),
    )


@app.route("/upload", methods=["GET"])
def upload_form():
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload_preview():
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("Choose a CSV file first.")
        return redirect(url_for("upload_form"))

    text = f.stream.read().decode("utf-8", errors="replace")
    con = open_db()
    new, existing, invalid = [], [], []
    seen = set()

    for raw in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        email = row.get("email", "").lower()
        name, phone = row.get("name", ""), row.get("phone", "")
        if not EMAIL_RE.match(email):
            invalid.append({"name": name, "email": row.get("email", ""),
                            "reason": "bad or missing email"})
            continue
        if email in seen:
            invalid.append({"name": name, "email": email, "reason": "duplicate row in file"})
            continue
        seen.add(email)
        c = db.contact_by_email(con, email)
        if c:
            existing.append({"name": name or c["name"], "email": email,
                             "status": _status_label(c)})
        else:
            new.append({"name": name, "email": email, "phone": phone})

    token = uuid.uuid4().hex
    _save_pending(token, {"new": new, "existing": len(existing), "invalid": len(invalid)})
    return render_template("preview.html", new=new, existing=existing,
                           invalid=invalid, token=token)


@app.route("/confirm", methods=["POST"])
def confirm():
    token = request.form.get("token", "")
    data = _load_pending(token)
    rows = data.get("new", [])
    con = open_db()
    for r in rows:
        db.add_contact(con, r["name"], r["email"], r.get("phone", ""))
    _clear_pending(token)

    msg = f"Added {len(rows)} new contacts. {data.get('existing', 0)} were already " \
          "in the system and were skipped, so their unsubscribe and cooldown state " \
          "is preserved."
    if data.get("invalid"):
        msg += f" {data['invalid']} invalid rows were ignored."
    flash(msg)
    return redirect(url_for("dashboard_view"))


if __name__ == "__main__":
    # localhost only. Do not bind to 0.0.0.0 until auth + HTTPS are added.
    port = int(os.environ.get("OUTBOUND_WEB_PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True)
