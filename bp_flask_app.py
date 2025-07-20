import os
import psycopg2
import csv
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, flash
from blood_pressure_tracker import BloodPressureTracker
from bp_flask_utils import HTML_ADD_FORM, HTML_TABLE, HTML_STATS, HTML_CSV_FORM, HTML_EDIT_FORM


# Initialize Flask app and tracker before any route definitions
app = Flask(__name__)
# secret_key is required for Flask session management and flash messages (used for CSV upload feedback)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'bpsecret')
tracker = BloodPressureTracker()

def get_reading_by_id(reading_id):
    conn = psycopg2.connect(**tracker.pg_config)
    cur = conn.cursor()
    cur.execute("SELECT id, date, systolic, diastolic, pulse FROM blood_pressure WHERE id = %s", (reading_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {'id': row[0], 'date': row[1].strftime('%Y-%m-%d %H:%M:%S'), 'systolic': row[2], 'diastolic': row[3], 'pulse': row[4]}
    return None

@app.route('/edit/<int:reading_id>', methods=['GET', 'POST'])
def edit_reading(reading_id):
    reading = get_reading_by_id(reading_id)
    if not reading:
        return "Reading not found", 404
    if request.method == 'POST':
        try:
            systolic = int(request.form['systolic'])
            diastolic = int(request.form['diastolic'])
            pulse_input = request.form.get('pulse', '').strip()
            pulse = int(pulse_input) if pulse_input else None
            date = request.form.get('date', '').strip()
            if not date:
                date = reading['date']
            valid = 0 < systolic < 300 and 0 < diastolic < 200
            if pulse is not None:
                valid = valid and 0 < pulse < 250
            if valid:
                conn = psycopg2.connect(**tracker.pg_config)
                cur = conn.cursor()
                cur.execute("UPDATE blood_pressure SET date=%s, systolic=%s, diastolic=%s, pulse=%s WHERE id=%s",
                            (date, systolic, diastolic, pulse, reading_id))
                conn.commit()
                cur.close()
                conn.close()
                return redirect(url_for('index'))
            else:
                return "Invalid values. Please enter realistic measurements.", 400
        except Exception:
            return "Please enter valid numbers.", 400
    return render_template_string(HTML_EDIT_FORM, reading=reading)

@app.route('/delete/<int:reading_id>', methods=['GET'])
def delete_reading(reading_id):
    conn = psycopg2.connect(**tracker.pg_config)
    cur = conn.cursor()
    cur.execute("DELETE FROM blood_pressure WHERE id = %s", (reading_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))


app = Flask(__name__)
# secret_key is required for Flask session management and flash messages (used for CSV upload feedback)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'bpsecret')
tracker = BloodPressureTracker()

@app.route('/load_csv', methods=['GET', 'POST'])
def load_csv():
    """Upload and import a CSV file of readings."""
    if request.method == 'POST':
        if 'csvfile' not in request.files:
            flash('No file part')
            return render_template_string(HTML_CSV_FORM)
        file = request.files['csvfile']
        if file.filename == '':
            flash('No selected file')
            return render_template_string(HTML_CSV_FORM)

        count = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name
        file.save(tmp_path)
        with open(tmp_path, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                date_str = row[0].strip()
                bp = row[1].strip()
                if '/' not in bp:
                    continue
                try:
                    systolic, diastolic = map(int, bp.split('/'))
                    dt = datetime.strptime(date_str, "%m/%d/%y")
                    date_fmt = dt.strftime("%Y-%m-%d %H:%M:%S")
                    if 0 < systolic < 300 and 0 < diastolic < 200:
                        tracker.add_reading(systolic, diastolic, None, date_fmt)
                        count += 1
                except Exception as e:
                    continue
        os.unlink(tmp_path)
        flash(f"Loaded {count} readings from CSV file.")
        return redirect(url_for('index'))
    return render_template_string(HTML_CSV_FORM)

@app.route('/')
def index():
    """Show all readings in a table."""
    readings = tracker._load_data()
    # Add id to each reading for edit/delete links
    conn = psycopg2.connect(**tracker.pg_config)
    cur = conn.cursor()
    cur.execute("SELECT id FROM blood_pressure ORDER BY date DESC")
    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    for i, r in enumerate(readings):
        r['id'] = ids[i] if i < len(ids) else None
    return render_template_string(HTML_TABLE, readings=readings)

@app.route('/add', methods=['GET', 'POST'])
def add():
    """Form to add a new reading."""
    if request.method == 'POST':
        try:
            systolic = int(request.form['systolic'])
            diastolic = int(request.form['diastolic'])
            pulse_input = request.form.get('pulse', '').strip()
            pulse = int(pulse_input) if pulse_input else None
            date = request.form.get('date', '').strip()
            if not date:
                date = None
            valid = 0 < systolic < 300 and 0 < diastolic < 200
            if pulse is not None:
                valid = valid and 0 < pulse < 250
            if valid:
                tracker.add_reading(systolic, diastolic, pulse, date)
                return redirect(url_for('index'))
            else:
                return "Invalid values. Please enter realistic measurements.", 400
        except Exception:
            return "Please enter valid numbers.", 400
    return render_template_string(HTML_ADD_FORM)

@app.route('/stats')
def stats():
    """Show statistics for all readings."""
    readings = tracker._load_data()
    if not readings:
        return "No readings available for statistics.", 400
    stats = tracker.calculate_stats(readings)
    return render_template_string(HTML_STATS, stats=stats)

@app.route('/api/readings')
def api_readings():
    """Return all readings as JSON."""
    readings = tracker._load_data()
    return jsonify(readings)

@app.route('/api/add', methods=['POST'])
def api_add():
    """Add a reading via JSON API."""
    data = request.get_json()
    try:
        systolic = int(data['systolic'])
        diastolic = int(data['diastolic'])
        pulse = int(data['pulse']) if 'pulse' in data and data['pulse'] not in (None, '') else None
        date = data.get('date', None)
        if not date:
            date = None
        valid = 0 < systolic < 300 and 0 < diastolic < 200
        if pulse is not None:
            valid = valid and 0 < pulse < 250
        if valid:
            tracker.add_reading(systolic, diastolic, pulse, date)
            return jsonify({'status': 'success'}), 201
        else:
            return jsonify({'error': 'Invalid values'}), 400
    except Exception:
        return jsonify({'error': 'Invalid input'}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
