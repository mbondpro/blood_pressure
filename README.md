
# Blood Pressure Tracker

A simple command-line and web application to track your daily blood pressure readings. Now supports CSV import, edit/delete in the web UI, and improved code quality/linting.


## Features

- Add daily blood pressure readings (systolic, diastolic, and optional pulse)
- View all recorded readings
- View statistics (average, maximum, and minimum values)
- Import readings from CSV (CLI and web)
- Edit and delete readings in the web interface
- Data persistence using PostgreSQL
- User-friendly command-line and mobile-friendly web interface
- API endpoints for integration (`/api/readings`, `/api/add`)
- Linting and code quality improvements (pylint)


## Requirements

- Python 3.x
- psycopg2-binary (for PostgreSQL support)
- Flask


## Usage

### Command-Line Application

Run the program using Python:

```bash
python blood_pressure_tracker.py
```

Follow the on-screen menu to:
1. Add new readings
2. View all readings
3. View statistics
4. Toggle PostgreSQL saving (ON/OFF)
5. Import readings from CSV file
6. Exit the program


### Flask Web Application

The Flask app provides a web interface for adding, editing, deleting, and importing blood pressure readings, including a mobile-friendly design.

#### Running with Docker Compose

1. Ensure Docker and Docker Compose are installed.
2. Update `pgpassword.txt` with your desired database password.
3. Start the services:

```bash
docker compose up --build
```

4. Access the web app at [http://localhost:5000](http://localhost:5000) in your browser or mobile device.

#### Features

- Add, edit, and delete readings via web form
- Import readings from CSV via web
- View all readings in a table
- View statistics
- API endpoints for integration (`/api/readings`, `/api/add`)


## Data Storage

All readings are stored in a PostgreSQL database. The table `blood_pressure` will be created automatically if it does not exist.

### PostgreSQL Setup

- The database is configured via Docker Compose and environment variables.
- The password is securely provided via Docker secrets (`pgpassword.txt`).
