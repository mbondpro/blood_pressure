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
from zoneinfo import ZoneInfo
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
from PIL import Image
from PIL.ExifTags import TAGS
from dotenv import load_dotenv

from blood_pressure_tracker import BloodPressureTracker
from claude_processor import ClaudeProcessor
from bp_flask_utils import (
    HTML_ADD_FORM,
    HTML_TABLE,
    HTML_STATS,
    HTML_CSV_FORM,
    HTML_EDIT_FORM,
    HTML_PREVIEW_FORM,
)

matplotlib.use("Agg")

# Load environment variables from .env if present
load_dotenv()

# Site-wide timezone (used for display and parsing when timezone not provided)
SITE_TZ = os.environ.get("TIMEZONE", "America/New_York")


def is_image_file(f) -> bool:
    """Return True if uploaded file looks like an image (filename or mimetype)."""
    try:
        if getattr(f, "filename", None):
            return True
        mimetype = getattr(f, "mimetype", "") or ""
        return mimetype.startswith("image/")
    except (AttributeError, TypeError):
        return False


def parse_to_utc(date: str | None) -> datetime:
    """Parse a date string and return a UTC-aware datetime.

    If parsing fails or `date` is None/empty, returns current UTC time.
    If parsed datetime has no tzinfo, assume `SITE_TZ`.
    """
    if not date:
        return datetime.now(tz=ZoneInfo("UTC"))

    parse_formats = [
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%y",
    ]
    parsed = None
    for fmt in parse_formats:
        try:
            parsed = datetime.strptime(date, fmt)
            break
        except ValueError:
            continue

    if parsed is None:
        return datetime.now(tz=ZoneInfo("UTC"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(SITE_TZ))
    return parsed.astimezone(ZoneInfo("UTC"))


# Initialize Flask app and tracker before any route definitions
app = Flask(__name__)
# secret_key is required for Flask session management and flash messages
# Require `FLASK_SECRET_KEY` to be set in the environment (do not use a hardcoded default).
secret = os.environ.get("FLASK_SECRET_KEY")
if not secret:
    raise RuntimeError(
        "FLASK_SECRET_KEY environment variable is not set. Set it in your environment or .env before starting the app."
    )
app.secret_key = secret
tracker = BloodPressureTracker()
claude_processor = ClaudeProcessor()


def build_bp_plot(parsed: list) -> str | None:
    """Build a base64-encoded PNG plot for systolic/diastolic values.

    Args:
        parsed: List of readings dicts that include a `date_dt` datetime and
            numeric `systolic` and `diastolic` fields.

    Returns:
        A base64-encoded PNG data URI fragment (without the data: prefix),
        or `None` if there is no data to plot.
    """
    # Filter to only include readings from the past year
    if parsed and parsed[0].get("date_dt"):
        # Use timezone from first reading for consistency
        tz = parsed[0]["date_dt"].tzinfo
        one_year_ago = datetime.now(tz=tz) - timedelta(days=365)
        parsed = [p for p in parsed if p["date_dt"] >= one_year_ago]
    
    dates = [p["date_dt"] for p in parsed]
    if not dates:
        return None

    systolic_vals = [p["systolic"] for p in parsed]
    diastolic_vals = [p["diastolic"] for p in parsed]

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
    return base64.b64encode(buf.read()).decode("ascii")


def extract_image_datetime(image_path: str) -> str | None:
    """Extract datetime from image EXIF data if available.

    Args:
        image_path: Path to the image file.

    Returns:
        Datetime string in format 'YYYY-MM-DD HH:MM:SS' or None if not available.
    """
    try:
        image = Image.open(image_path)
        exif_data = image.getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag in ("DateTime", "DateTimeOriginal"):
                    # EXIF datetime format is typically "YYYY:MM:DD HH:MM:SS"
                    dt_str = str(value).replace(":", "-", 2)  # Replace first two colons
                    return dt_str
    except (AttributeError, KeyError, OSError):
        pass
    return None


def get_reading_by_id(reading_id):
    """Retrieve a single reading by its ID from the database."""
    conn = psycopg2.connect(**tracker.pg_config)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, date, systolic, diastolic, pulse FROM blood_pressure WHERE id = %s",
        (reading_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        raw_dt = row[1]
        if raw_dt is None:
            date_str = ""
        else:
            if raw_dt.tzinfo is None:
                raw_dt = raw_dt.replace(tzinfo=ZoneInfo("UTC"))
            local_dt = raw_dt.astimezone(ZoneInfo(SITE_TZ))
            date_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "id": row[0],
            "date": date_str,
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
                # Parse provided date and convert to UTC-aware datetime for storage
                dt_utc = parse_to_utc(date)

                conn = psycopg2.connect(**tracker.pg_config)
                cur = conn.cursor()
                cur.execute(
                    "UPDATE blood_pressure SET date=%s, systolic=%s, diastolic=%s, pulse=%s WHERE id=%s",
                    (dt_utc, systolic, diastolic, pulse, reading_id),
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
def delete_reading_get(_reading_id):
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
def add():  # pylint: disable=too-many-branches
    """Add a new blood pressure reading manually or via image upload."""
    response = None
    if request.method == "POST":
        # Check if image was uploaded
        image_file = request.files.get("bp_image")

        if image_file and is_image_file(image_file):

            # Save to temporary file
            file_ext = os.path.splitext(image_file.filename or "")[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp_path = tmp.name

            try:
                image_file.save(tmp_path)

                # Resize uploaded image before submitting to Claude to reduce upload size
                try:
                    resized_tmp = claude_processor.resize_image(tmp_path, max_dim=1000)
                except Exception:
                    # fallback to original if resizing fails
                    resized_tmp = tmp_path

                # Extract data from image using Claude (use resized_tmp)
                bp_data = claude_processor.process_bp_image(resized_tmp)

                systolic = int(bp_data["systolic"])
                diastolic = int(bp_data["diastolic"])
                pulse = int(bp_data["pulse"]) if bp_data.get("pulse") else None

                # Try to get timestamp from Claude response, then EXIF, then use current time
                date = bp_data.get("timestamp")
                if not date:
                    date = extract_image_datetime(tmp_path)
                # Prepare preview: show the image and prefilled values for confirmation
                try:
                    with open(tmp_path, "rb") as _f:
                        image_b64 = base64.b64encode(_f.read()).decode("ascii")
                except OSError:
                    image_b64 = ""

                # Render preview page (user can edit values before saving)
                response = render_template_string(
                    HTML_PREVIEW_FORM,
                    image_data=image_b64,
                    systolic=systolic,
                    diastolic=diastolic,
                    pulse=pulse,
                    date=date,
                )

            except (ValueError, OSError) as e:
                flash(f"Error processing image: {str(e)}")
                response = render_template_string(HTML_ADD_FORM)
            finally:
                # Clean up temporary files
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except OSError:
                    pass
                try:
                    if 'resized_tmp' in locals() and resized_tmp != tmp_path and os.path.exists(resized_tmp):
                        os.unlink(resized_tmp)
                except OSError:
                    pass

        # Manual entry (original code)
        if response is None:
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
    if response is not None:
        return response
    return render_template_string(HTML_ADD_FORM)


@app.route("/stats")
def stats():
    """Show statistics for all readings."""
    readings = tracker.get_all_readings()
    if not readings:
        return "No readings available for statistics.", 400
    # Parse dates into timezone-aware datetimes (site timezone) and sort
    parsed = []
    for r in readings:
        date_str = r.get("date") or ""
        try:
            # parse_to_utc handles multiple formats and returns a UTC-aware datetime
            dt_utc = parse_to_utc(date_str)
        except Exception:
            dt_utc = datetime.now(tz=ZoneInfo("UTC"))
        # convert to site timezone for display/aggregation
        local_dt = dt_utc.astimezone(ZoneInfo(SITE_TZ))
        parsed.append({**r, "date_dt": local_dt})
    parsed.sort(key=lambda x: x["date_dt"])

    # Calculate averages over past 7,14,30,90 days (use site-local now)
    now = datetime.now(tz=ZoneInfo(SITE_TZ))
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
    plot_data = build_bp_plot(parsed)

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


@app.route("/add/confirm", methods=["POST"])
def add_confirm():
    """Save a reading submitted from the preview form."""
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
            flash("Reading saved")
            return redirect(url_for("index"))
        flash("Invalid values. Please correct them and try again.")
        return redirect(url_for("add"))
    except (ValueError, psycopg2.Error):
        flash("Please enter valid numbers.")
        return redirect(url_for("add"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
