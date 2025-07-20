"""
bp_flask_utils.py

This module contains HTML templates and utility functions for the Blood Pressure Tracker Flask web application.
All HTML code for forms, tables, and statistics is stored here to keep the Flask app code clean and maintainable.
Includes:
- HTML templates for add, edit, table, statistics, and CSV upload forms
- Utility function for securely retrieving the PostgreSQL password from Docker secrets or environment variables
"""

import os

HTML_ADD_FORM = """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Add Blood Pressure Reading</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 10px; }
    form { max-width: 400px; margin: auto; padding: 16px; background: #f9f9f9; border-radius: 8px; }
    input[type=number], input[type=text] { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; }
    input[type=submit] { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; font-size: 16px; }
    h2 { text-align: center; }
    a { display: block; text-align: center; margin-top: 16px; color: #007bff; text-decoration: none; }
    @media (max-width: 600px) {
      form { padding: 8px; }
      h2 { font-size: 1.2em; }
    }
  </style>
</head>
<body>
<h2>Add Blood Pressure Reading</h2>
<a href="/">Back to readings</a>
<form method=post action="/add">
  Systolic: <input type=number name=systolic required><br>
  Diastolic: <input type=number name=diastolic required><br>
  Pulse (optional): <input type=number name=pulse><br>
  Date (YYYY-MM-DD HH:MM:SS, optional): <input type=text name=date><br>
  <input type=submit value=Add>
</form>
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
  Date: <input type=text name=date value="{{ reading['date'] }}" required><br>
  Systolic: <input type=number name=systolic value="{{ reading['systolic'] }}" required><br>
  Diastolic: <input type=number name=diastolic value="{{ reading['diastolic'] }}" required><br>
  Pulse (optional): <input type=number name=pulse value="{{ reading['pulse'] if reading['pulse'] is not none else '' }}"><br>
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
<table>
<tr><th>Date</th><th>Systolic</th><th>Diastolic</th><th>Pulse</th></tr>
{% for r in readings %}
<tr><td>{{ r['date'] }}</td><td>{{ r['systolic'] }}</td><td>{{ r['diastolic'] }}</td><td>{{ r['pulse'] if r['pulse'] is not none else '' }}</td></tr>
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
<table>
<tr><th>Measure</th><th>Average</th><th>Max</th><th>Min</th></tr>
{% for measure, values in stats.items() %}
<tr><td>{{ measure }}</td><td>{{ values['Average']|round(1) if values['Average'] is not none else '' }}</td><td>{{ values['Max'] if values['Max'] is not none else '' }}</td><td>{{ values['Min'] if values['Min'] is not none else '' }}</td></tr>
{% endfor %}
</table>
</body>
</html>
"""


def get_pgpassword():
    """
    Retrieve the PostgreSQL password from a Docker secret file or environment variable.
    Returns:
        str or None: The password string if found, else None.
    """
    pgpassword_file = os.environ.get("PGPASSWORD_FILE")
    if pgpassword_file and os.path.exists(pgpassword_file):
        with open(pgpassword_file, encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get("PGPASSWORD")
