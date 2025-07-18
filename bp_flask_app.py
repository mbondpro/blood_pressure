from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from blood_pressure_tracker import BloodPressureTracker
from bp_flask_utils import HTML_FORM, HTML_TABLE, HTML_STATS


app = Flask(__name__)
tracker = BloodPressureTracker()

@app.route('/')
def index():
    """Show all readings in a table."""
    readings = tracker._load_data()
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
    return render_template_string(HTML_FORM)

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
