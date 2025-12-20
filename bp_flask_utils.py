"""
bp_flask_utils.py

This module contains HTML templates and utility functions for the Blood Pressure Tracker Flask web application.
All HTML code for forms, tables, and statistics is stored here to keep the Flask app code clean and maintainable.
Includes:
- HTML templates for add, edit, table, statistics, and CSV upload forms
- Utility function for securely retrieving the PostgreSQL password from Docker secrets or environment variables
"""

# os import removed; prefer reading PGPASSWORD from environment where needed

HTML_ADD_FORM = """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Add Blood Pressure Reading</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 10px; }
    form { max-width: 400px; margin: auto; padding: 16px; background: #f9f9f9; border-radius: 8px; }
    input[type=number], input[type=text], input[type=file] { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; }
    input[type=submit] { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; font-size: 16px; margin-top: 8px; }
    h2 { text-align: center; }
    h3 { text-align: center; margin-top: 24px; color: #555; }
    .divider { text-align: center; margin: 20px 0; color: #999; font-weight: bold; }
    a { display: block; text-align: center; margin-top: 16px; color: #007bff; text-decoration: none; }
    .flash-message { text-align: center; padding: 10px; margin: 10px auto; max-width: 400px; background: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; }
    @media (max-width: 600px) {
      form { padding: 8px; }
      h2 { font-size: 1.2em; }
    }
  </style>
</head>
<body>
<h2>Add Blood Pressure Reading</h2>
<a href="/">Back to readings</a>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    {% for message in messages %}
      <div class="flash-message">{{ message }}</div>
    {% endfor %}
  {% endif %}
{% endwith %}

<form method=post action="/add" enctype="multipart/form-data">
  <h3>Upload Photo of BP Monitor</h3>
  <label for="bp_image">Blood Pressure Monitor Image:</label>
  <input type=file name=bp_image id=bp_image accept="image/*" capture="environment"><br>
  <input type=submit value="Upload and Process Image">
  
  <div class="divider">OR</div>
  
  <h3>Enter Manually</h3>
  Systolic: <input type=number name=systolic><br>
  Diastolic: <input type=number name=diastolic><br>
  Pulse (optional): <input type=number name=pulse><br>
  Date (YYYY-MM-DD HH:MM:SS, optional): <input type=text name=date><br>
  <input type=submit value="Add Manually">
</form>
</body>
</html>
"""


HTML_PREVIEW_FORM = """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Preview Extracted Reading</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 10px; }
    .container { max-width: 600px; margin: auto; padding: 16px; background: #f9f9f9; border-radius: 8px; }
    input[type=number], input[type=text] { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; }
    input[type=submit], button { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; font-size: 16px; margin-top: 8px; }
    img { display:block; margin: 8px auto; max-width:100%; height:auto; border:1px solid #ddd; }
    .row { display:flex; gap:8px; }
    .col { flex:1 }
  </style>
</head>
<body>
<div class="container">
  <h2>Preview Extracted Reading</h2>
  <p>Confirm or edit the extracted values before saving.</p>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for message in messages %}
        <div class="flash-message" style="text-align:center; padding:10px; margin:10px auto; max-width:560px; background:#d4edda; color:#155724; border:1px solid #c3e6cb; border-radius:4px;">{{ message }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  <div style="text-align:center;"><img src="data:image/jpeg;base64,{{ image_data }}" alt="Uploaded image"/></div>
  <form method=post action="/add/confirm">
    Systolic: <input type=number name=systolic value="{{ systolic }}" required><br>
    Diastolic: <input type=number name=diastolic value="{{ diastolic }}" required><br>
    Pulse (optional): <input type=number name=pulse value="{{ pulse if pulse is not none else '' }}"><br>
    Date (YYYY-MM-DD HH:MM:SS, optional): <input type=text name=date value="{{ date if date is not none else '' }}"><br>
    <input type=hidden name="_preview" value="1">
    <input type=submit value="Save Reading">
  </form>
  <form method=get action="/add">
    <button type="submit" style="background:#6c757d;">Cancel</button>
  </form>
</div>
</body>
</html>
"""


HTML_EDIT_FORM = """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Edit Reading</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 10px; }
    form { max-width: 400px; margin: auto; padding: 16px; background: #f9f9f9; border-radius: 8px; }
    input[type=number], input[type=text] { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; }
    input[type=submit] { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; font-size: 16px; }
    h2 { text-align: center; }
    a { display: block; text-align: center; margin-top: 16px; color: #007bff; text-decoration: none; }
  </style>
</head>
<body>
<h2>Edit Blood Pressure Reading</h2>
<a href="/">Back to readings</a>
<form method=post>
  Systolic: <input type=number name=systolic value="{{ reading['systolic'] }}" required><br>
  Diastolic: <input type=number name=diastolic value="{{ reading['diastolic'] }}" required><br>
  Pulse (optional): <input type=number name=pulse value="{{ reading['pulse'] if reading['pulse'] is not none else '' }}"><br>
  Date: <input type=text name=date value="{{ reading['date'] }}" required><br>
  <input type=submit value="Save Changes">
</form>
</body>
</html>
"""


HTML_CSV_FORM = """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Load CSV Readings</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 10px; }
    form { max-width: 400px; margin: auto; padding: 16px; background: #f9f9f9; border-radius: 8px; }
    input[type=file] { width: 100%; margin: 8px 0; }
    input[type=submit] { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; font-size: 16px; }
    h2 { text-align: center; }
    a { display: block; text-align: center; margin-top: 16px; color: #007bff; text-decoration: none; }
  </style>
</head>
<body>
<h2>Load Blood Pressure Readings from CSV</h2>
<a href="/">Back to readings</a>
<form method=post enctype=multipart/form-data>
  <input type=file name=csvfile accept=".csv" required><br>
  <input type=submit value="Upload and Import">
</form>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul style="color: green; text-align: center;">
    {% for message in messages %}
      <li>{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
</body>
</html>
"""


HTML_TABLE = """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Blood Pressure Readings</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 10px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    th, td { padding: 8px; text-align: center; border-bottom: 1px solid #ddd; }
    th { background: #007bff; color: white; }
    tr:nth-child(even) { background: #f2f2f2; }
    a { display: inline-block; margin: 8px; color: #007bff; text-decoration: none; }
    @media (max-width: 600px) {
      th, td { padding: 4px; font-size: 0.9em; }
      table { font-size: 0.95em; }
    }
  </style>
</head>
<body>
<h2>Blood Pressure Readings</h2>
<a href="/add">Add New Reading</a> | <a href="/stats">View Statistics</a> | <a href="/load_csv">Load CSV Readings</a>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    <div style="max-width:900px; margin:10px auto; text-align:center;">
      {% for message in messages %}
        <div style="background:#d4edda; color:#155724; border:1px solid #c3e6cb; padding:8px; margin-bottom:6px; border-radius:4px;">{{ message }}</div>
      {% endfor %}
    </div>
  {% endif %}
{% endwith %}
<table>
<tr><th>Date</th><th>Systolic</th><th>Diastolic</th><th>Pulse</th><th>Actions</th></tr>
{% for r in readings %}
<tr>
  <td>{{ r['date'] }}</td>
  <td>{{ r['systolic'] }}</td>
  <td>{{ r['diastolic'] }}</td>
  <td>{{ r['pulse'] if r['pulse'] is not none else '' }}</td>
  <td>
    <a href="{{ url_for('edit_reading', reading_id=r['id']) }}">Edit</a>
    |
    <form method="post" action="{{ url_for('delete_reading', reading_id=r['id']) }}" style="display:inline; margin:0; padding:0;" onsubmit="return confirm('Are you sure you want to delete this reading?');">
      <button type="submit" style="background:none; border:none; padding:0; color:#007bff; cursor:pointer; text-decoration:underline; font: inherit;">Delete</button>
    </form>
  </td>  
</tr>
{% endfor %}
</table>
</body>
</html>
"""

HTML_STATS = """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Statistics</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 10px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    th, td { padding: 8px; text-align: center; border-bottom: 1px solid #ddd; }
    th { background: #007bff; color: white; }
    tr:nth-child(even) { background: #f2f2f2; }
    a { display: block; text-align: center; margin-top: 16px; color: #007bff; text-decoration: none; }
    @media (max-width: 600px) {
      th, td { padding: 4px; font-size: 0.9em; }
      table { font-size: 0.95em; }
    }
  </style>
</head>
<body>
<h2>Statistics</h2>
<p><a href="/">Back to readings</a></p>

<h3>Blood Pressure Over Time</h3>
{% if plot_data %}
  <div style="max-width:900px; margin:auto; text-align:center;">
    <img src="data:image/png;base64,{{ plot_data }}" alt="Blood pressure plot" style="max-width:100%; height:auto; border:1px solid #ddd;"/>
  </div>
{% else %}
  <p>No plot available.</p>
{% endif %}

<h3>Averages</h3>
<table style="max-width:600px; margin:auto;">
  <tr><th>Period</th><th>Systolic (avg)</th><th>Diastolic (avg)</th></tr>
  {% for period, vals in averages.items() %}
  <tr><td>{{ period }}</td><td>{{ vals['Systolic'] if vals['Systolic'] is not none else '' }}</td><td>{{ vals['Diastolic'] if vals['Diastolic'] is not none else '' }}</td></tr>
  {% endfor %}
</table>

<h3>Overall (All Data)</h3>
<table>
<tr><th>Measure</th><th>Average</th><th>Max</th><th>Min</th></tr>
{% for measure, values in stats.items() %}
<tr><td>{{ measure }}</td><td>{{ values['Average']|round(1) if values['Average'] is not none else '' }}</td><td>{{ values['Max'] if values['Max'] is not none else '' }}</td><td>{{ values['Min'] if values['Min'] is not none else '' }}</td></tr>
{% endfor %}
</table>
</body>
</html>
"""
