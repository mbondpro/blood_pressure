
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

- **Python:** 3.11+ (3.8+ may work, but newer is recommended)
- **Web framework:** Flask
- **Database driver:** psycopg2-binary (or psycopg2)
- **Image processing:** Pillow
- **Configuration:** python-dotenv (for loading a local `.env` during development)
- **Plotting:** matplotlib
- **AI client (optional):** anthropic — required only if using the `ClaudeProcessor` image parsing flow
- **Testing (dev):** pytest
- **Timezone data (recommended):** tzdata — some OS Python builds require tzdata for full zoneinfo support; alternatively tests include lightweight fallbacks

Install runtime requirements with:

```bash
pip install -r requirements.txt
```


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
2. Add your database password to the `.env` file as `PGPASSWORD` (example included).
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
- The password is provided via the `.env` file using the `PGPASSWORD` variable. The compose files read `.env` (or you can export `PGPASSWORD` in your shell).

## Design & Implementation

- **Timezone handling:** All datetimes are stored in the database as UTC-aware timestamps. The application exposes a site timezone configured via the `TIMEZONE` environment variable (default: `America/New_York`). Helper functions parse naive user input as the site timezone and convert to UTC before persisting.
- **Image upload & AI-assisted extraction:** The web UI accepts photos of blood-pressure monitor screens. EXIF datetime extraction is attempted and an optional AI-assisted extractor (`ClaudeProcessor`) parses systolic, diastolic, pulse, and a best-guess timestamp. The extraction is shown on a preview page for user confirmation prior to saving.
- **Prompt caching:** The `ClaudeProcessor` uses Anthropic's prompt caching feature to significantly reduce token usage when processing images. Images sent to Claude include `cache_control` metadata, allowing Claude to cache the image data on their servers and reuse it for subsequent requests, reducing costs for repeated or similar processing.
- **Storage & schema:** Readings are persisted to PostgreSQL in a `blood_pressure` table using a timestamptz-compatible column. The code uses `psycopg2` and passes tz-aware `datetime` objects to the DB.
- **Configuration & secrets:** Runtime configuration is read from environment variables (loaded via `python-dotenv` in development). Do not commit real secrets — set `ANTHROPIC_API_KEY`, `PGPASSWORD`, and other keys via your environment or a local `.env` file. Compose files read `PGPASSWORD` from `.env`.
- **Logging & quality:** The project uses structured `logging` (no ad-hoc prints) and follows linting rules (`pylint`) to maintain code quality.
- **Testing:** Unit tests use `pytest`. `tests/test_timezones.py` verifies timezone parsing/storage/display behavior and uses lightweight monkeypatches for `psycopg2` and `zoneinfo` where appropriate.
- **Deployment:** Docker Compose (`docker-compose.yml`, `docker-compose-dev.yml`) is configured to use an `.env` file and environment variables for secrets and configuration.

Developer notes:

- Run tests:

```bash
source .venv/Scripts/activate
pytest
```
