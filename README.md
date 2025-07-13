# Blood Pressure Tracker

A simple command-line application to track your daily blood pressure readings.

## Features

- Add daily blood pressure readings (systolic, diastolic, and pulse)
- View all recorded readings
- View statistics (average, maximum, and minimum values)
- Data persistence using JSON and CSV file storage
- Optional saving to a PostgreSQL database

## Requirements

- Python 3.x
- pandas
- tabulate
- psycopg2-binary (for PostgreSQL support)

## Usage

Run the program using Python:

```bash
python blood_pressure_tracker.py
```

Follow the on-screen menu to:
1. Add new readings
2. View all readings
3. View statistics
4. Toggle PostgreSQL saving (ON/OFF)
5. Exit the program

## Data Storage

If PostgreSQL saving is enabled, readings are also saved to the configured database.

### PostgreSQL Setup

- Edit the `pg_config` dictionary in `blood_pressure_tracker.py` to match your database settings.
- The table `blood_pressure` will be created automatically if it does not exist.
