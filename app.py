"""
app.py  —  ReconTool Flask application
In-memory file processing. No files saved to disk.

Local run:
    python app.py
    Open http://127.0.0.1:5000

Render.com deploy:
    Build command:  pip install -r requirements.txt
    Start command:  gunicorn app:app
"""

from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash)

from ingestion.loader import load_from_bytes, get_date_range
from modules.engine import compute_dashboard, build_actionables, CHANNELS

app = Flask(__name__)
app.secret_key = "recon-secret-change-in-prod"

ALLOWED_EXT = {".csv", ".xlsx", ".xls"}


def _allowed(filename: str) -> bool:
    from pathlib import Path
    return Path(filename).suffix.lower() in ALLOWED_EXT


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Upload / landing page."""
    error = session.pop("upload_error", None)
    return render_template("index.html", error=error)


@app.route("/upload", methods=["POST"])
def upload():
    """Receive file, process in-memory, store result in session."""
    f = request.files.get("file")

    if not f or not f.filename:
        session["upload_error"] = "No file selected."
        return redirect(url_for("index"))

    if not _allowed(f.filename):
        session["upload_error"] = "Unsupported file type. Please upload CSV or Excel."
        return redirect(url_for("index"))

    try:
        file_bytes = f.read()
        df         = load_from_bytes(file_bytes, f.filename)
        date_range = get_date_range(df)
        data       = compute_dashboard(df, date_range)

        # Store computed data in session (JSON-serialisable)
        session["dashboard_data"] = data
        session["filename"]       = f.filename

    except Exception as exc:
        session["upload_error"] = str(exc)
        return redirect(url_for("index"))

    return redirect(url_for("dashboard"))


@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Render the dashboard from session-stored computed data."""
    data     = session.get("dashboard_data")
    filename = session.get("filename")

    if not data:
        return redirect(url_for("index"))

    active_channel = request.args.get("channel", CHANNELS[0])
    if active_channel not in data["channels"]:
        active_channel = CHANNELS[0]

    channel_data = data["channels"][active_channel]
    actionables  = []
    if channel_data["totalOrders"] > 0:
        actionables = build_actionables(channel_data["overall"], active_channel)

    return render_template(
        "dashboard.html",
        data=data,
        active_channel=active_channel,
        actionables=actionables,
        filename=filename,
    )


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  ReconTool")
    print("  ─────────────────────────────────")
    print("  http://127.0.0.1:5000")
    print("  Ctrl+C to stop\n")
    app.run(debug=True, port=5000)
