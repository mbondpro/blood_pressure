"""
Module: bp_flask_app

Flask web application for the Blood Pressure Tracker project.
Provides routes for adding, editing, deleting, viewing, and importing blood pressure readings.
Uses BloodPressureTracker for data management and bp_flask_utils for HTML templates.
"""

import os
import io
import tempfile
from datetime import datetime, timedelta
import csv
import base64
import psycopg2
from flask import (
    Flask,
    request,
    jsonify,
    render_template_string,
    redirect,
    url_for,
    flash,
)
import matplotlib
import matplotlib.pyplot as plt

from blood_pressure_tracker import BloodPressureTracker
from bp_flask_utils import (
    HTML_ADD_FORM,
    HTML_TABLE,
    HTML_STATS,
    HTML_CSV_FORM,
    HTML_EDIT_FORM,
)

matplotlib.use("Agg")

# Initialize Flask app and tracker before any route definitions
app = Flask(__name__)
# secret_key is required for Flask session management and flash messages (used for CSV upload feedback)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "bpsecret")
tracker = BloodPressureTracker()


def get_reading_by_id(reading_id):
    """Retrieve a single reading by its ID from the database."""
    conn = psycopg2.connect(**tracker.pg_config)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, date AT TIME ZONE 'America/New_York' as date, systolic, diastolic, pulse "
        "FROM blood_pressure WHERE id = %s",
        (reading_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "id": row[0],
            "date": row[1].strftime("%Y-%m-%d %H:%M:%S"),
            "systolic": row[2],
            "diastolic": row[3],
            "pulse": row[4],
        }
    return None


@app.route("/edit/<int:reading_id>", methods=["GET", "POST"])
def edit_reading(reading_id):
    """Edit an existing blood pressure reading."""
    reading = get_reading_by_id(reading_id)
    if not reading:
        return "Reading not found", 404
    if request.method == "POST":
        try:
            systolic = int(request.form["systolic"])
            diastolic = int(request.form["diastolic"])
            pulse_input = request.form.get("pulse", "").strip()
            pulse = int(pulse_input) if pulse_input else None
            date = request.form.get("date", "").strip()
            if not date:
                date = reading["date"]
            valid = 0 < systolic < 300 and 0 < diastolic < 200
            if pulse is not None:
                valid = valid and 0 < pulse < 250
            if valid:
                conn = psycopg2.connect(**tracker.pg_config)
                cur = conn.cursor()
                cur.execute(
                    "UPDATE blood_pressure SET date=%s, systolic=%s, diastolic=%s, pulse=%s WHERE id=%s",
                    (date, systolic, diastolic, pulse, reading_id),
                )
                conn.commit()
                cur.close()
                conn.close()
                return redirect(url_for("index"))
            return "Invalid values. Please enter realistic measurements.", 400
        except (ValueError, psycopg2.Error):
            return "Please enter valid numbers.", 400
    return render_template_string(HTML_EDIT_FORM, reading=reading)


@app.route("/delete/<int:reading_id>", methods=["POST"])
def delete_reading(reading_id):
    """Delete a blood pressure reading by its ID. Accepts POST only for safety."""
    conn = psycopg2.connect(**tracker.pg_config)
    cur = conn.cursor()
    cur.execute("DELETE FROM blood_pressure WHERE id = %s", (reading_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:reading_id>", methods=["GET"])
def delete_reading_get(reading_id):
    """Return 405 for GET requests to the delete endpoint to discourage accidental deletes."""
    return ("Method Not Allowed", 405)


@app.route("/load_csv", methods=["GET", "POST"])
def load_csv():
    """Upload and import a CSV file of readings."""
    if request.method == "POST":
        if "csvfile" not in request.files:
            flash("No file part")
            return render_template_string(HTML_CSV_FORM)
        file = request.files["csvfile"]
        if file.filename == "":
            flash("No selected file")
            return render_template_string(HTML_CSV_FORM)

        count = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name
        file.save(tmp_path)
        with open(tmp_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                date_str = row[0].strip()
                bp = row[1].strip()
                if "/" not in bp:
                    continue
                try:
                    systolic, diastolic = map(int, bp.split("/"))
                    dt = datetime.strptime(date_str, "%m/%d/%y")
                    date_fmt = dt.strftime("%Y-%m-%d %H:%M:%S")
                    if 0 < systolic < 300 and 0 < diastolic < 200:
                        tracker.add_reading(systolic, diastolic, None, date_fmt)
                        count += 1
                except (ValueError, IndexError):
                    continue
        os.unlink(tmp_path)
        flash(f"Loaded {count} readings from CSV file.")
        return redirect(url_for("index"))
    return render_template_string(HTML_CSV_FORM)


@app.route("/")
def index():
    """Display all readings in a table."""
    readings = tracker.get_all_readings()
    # Add id to each reading for edit/delete links
    conn = psycopg2.connect(**tracker.pg_config)
    cur = conn.cursor()
    cur.execute("SELECT id FROM blood_pressure ORDER BY date DESC")
    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    for i, r in enumerate(readings):
        r["id"] = ids[i] if i < len(ids) else None
    return render_template_string(HTML_TABLE, readings=readings)


@app.route("/add", methods=["GET", "POST"])
def add():
    """Add a new blood pressure reading."""
    if request.method == "POST":
        try:
            systolic = int(request.form["systolic"])
            diastolic = int(request.form["diastolic"])
            pulse_input = request.form.get("pulse", "").strip()
            pulse = int(pulse_input) if pulse_input else None
            date = request.form.get("date", "").strip()
            if not date:
                date = None
            valid = 0 < systolic < 300 and 0 < diastolic < 200
            if pulse is not None:
                valid = valid and 0 < pulse < 250
            if valid:
                tracker.add_reading(systolic, diastolic, pulse, date)
                return redirect(url_for("index"))
            return "Invalid values. Please enter realistic measurements.", 400
        except (ValueError, psycopg2.Error):
            return "Please enter valid numbers.", 400
    return render_template_string(HTML_ADD_FORM)


@app.route("/stats")
def stats():
    """Show statistics for all readings."""
    readings = tracker.get_all_readings()
    if not readings:
        return "No readings available for statistics.", 400
    # Parse dates and sort readings
    parsed = []
    for r in readings:
        try:
            dt = datetime.strptime(r["date"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # try date-only
            dt = datetime.strptime(r["date"], "%Y-%m-%d")
        parsed.append({**r, "date_dt": dt})
    parsed.sort(key=lambda x: x["date_dt"])

    # Calculate averages over past 7,14,30,90 days
    now = datetime.now()
    periods = [7, 14, 30, 90]
    averages = {}
    for days in periods:
        since = now - timedelta(days=days)
        subset = [p for p in parsed if p["date_dt"] >= since]
        if subset:
            s_vals = [p["systolic"] for p in subset if p["systolic"] is not None]
            d_vals = [p["diastolic"] for p in subset if p["diastolic"] is not None]
            averages[f"Last {days} days"] = {
                "Systolic": round(sum(s_vals) / len(s_vals), 1) if s_vals else None,
                "Diastolic": round(sum(d_vals) / len(d_vals), 1) if d_vals else None,
            }
        else:
            averages[f"Last {days} days"] = {"Systolic": None, "Diastolic": None}

    # Also include overall stats for compatibility
    calculated_stats = tracker.calculate_stats(readings)

    # Build a plot for systolic and diastolic over time
    dates = [p["date_dt"] for p in parsed]
    systolic_vals = [p["systolic"] for p in parsed]
    diastolic_vals = [p["diastolic"] for p in parsed]

    plot_data = None
    if dates:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(dates, systolic_vals, label="Systolic", color="#d9534f")
        ax.plot(dates, diastolic_vals, label="Diastolic", color="#0275d8")
        ax.set_xlabel("Date")
        ax.set_ylabel("Pressure (mm Hg)")
        ax.set_title("Blood Pressure Over Time")
        ax.legend()
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        plot_data = base64.b64encode(buf.read()).decode("ascii")

    return render_template_string(
        HTML_STATS, stats=calculated_stats, averages=averages, plot_data=plot_data
    )


@app.route("/api/readings")
def api_readings():
    """Return all readings as JSON."""
    readings = tracker.get_all_readings()
    return jsonify(readings)


@app.route("/api/add", methods=["POST"])
def api_add():
    """Add a reading via JSON API."""
    data = request.get_json()
    try:
        systolic = int(data["systolic"])
        diastolic = int(data["diastolic"])
        pulse = (
            int(data["pulse"])
            if "pulse" in data and data["pulse"] not in (None, "")
            else None
        )
        date = data.get("date", None)
        if not date:
            date = None
        valid = 0 < systolic < 300 and 0 < diastolic < 200
        if pulse is not None:
            valid = valid and 0 < pulse < 250
        if valid:
            tracker.add_reading(systolic, diastolic, pulse, date)
            return jsonify({"status": "success"}), 201
        return jsonify({"error": "Invalid values"}), 400
    except (ValueError, psycopg2.Error):
        return jsonify({"error": "Invalid input"}), 400


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
