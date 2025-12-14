"""
Module: blood_pressure_tracker

Implements the BloodPressureTracker class for managing blood pressure readings, including:
- Data persistence (JSON or database)
- Input validation
- Statistical analysis (pure Python)
- CSV import
- Command-line interface integration
"""

# pylint: disable=R0801


import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
import logging
import psycopg2
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env when running CLI
load_dotenv()

# Site timezone for display/parsing when a timezone is not provided
SITE_TZ = os.environ.get("TIMEZONE", "America/New_York")


class BloodPressureTracker:
    """
    Class for managing blood pressure readings, including data persistence, validation, statistics, and CSV import.
    Handles all database operations and provides a command-line interface for user interaction.
    """

    def get_all_readings(self) -> List[Dict[str, Any]]:
        """
        Retrieve all blood pressure readings from the database.
        Returns:
            List[Dict[str, Any]]: List of reading dictionaries.
        """
        return self._load_data()

    # Handles blood pressure data management, including add/edit/delete, validation, statistics, and persistence.
    def __init__(self):
        """
        Initialize the BloodPressureTracker instance and set up PostgreSQL configuration.
        """
        self.pg_enabled = True
        self.pg_config: Dict[str, Any] = {
            "host": "db",  # Docker service name for PostgreSQL
            "port": 5432,
            "database": "bp_tracker",
            "user": "postgres",
            "password": os.environ.get("PGPASSWORD"),
        }
        self._create_pg_table()

    def _load_data(self) -> List[Dict[str, Any]]:
        """
        Load readings from the PostgreSQL database.
        Returns:
            list: List of readings (dict) loaded from the database.
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cur = conn.cursor()
            cur.execute(
                "SELECT date, systolic, diastolic, pulse FROM blood_pressure ORDER BY date DESC"
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()

            results: List[Dict[str, Any]] = []
            for row in rows:
                raw_dt = row[0]
                if raw_dt is None:
                    date_str = ""
                else:
                    # Ensure we have an aware datetime. If naive, assume UTC.
                    if raw_dt.tzinfo is None:
                        raw_dt = raw_dt.replace(tzinfo=ZoneInfo("UTC"))
                    # Convert to site timezone for display
                    local_dt = raw_dt.astimezone(ZoneInfo(SITE_TZ))
                    date_str = local_dt.strftime("%Y-%m-%d %H:%M:%S %z")

                results.append(
                    {
                        "date": date_str,
                        "systolic": row[1],
                        "diastolic": row[2],
                        "pulse": row[3] if row[3] is not None else None,
                    }
                )
            return results
        except (psycopg2.Error, KeyError, ValueError) as e:
            logger.exception("Error loading from PostgreSQL: %s", e)
            return []

    def load_csv(self, csv_path: str):
        """
        Load readings from a CSV file with format 'date, systolic/diastolic'.
        Date format: mm/dd/yy
        Example row: 07/20/25, 120/80
        """
        count = 0
        with open(csv_path, "r", newline="", encoding="utf-8") as csvfile:
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
                    # Convert mm/dd/yy to yyyy-mm-dd
                    dt = datetime.strptime(date_str, "%m/%d/%y")
                    date_fmt = dt.strftime("%Y-%m-%d %H:%M:%S")
                    if 0 < systolic < 300 and 0 < diastolic < 200:
                        self.add_reading(systolic, diastolic, None, date_fmt)
                        count += 1
                except (ValueError, IndexError) as e:
                    logger.warning("Skipping row due to error: %s (%s)", row, e)
        logger.info("Loaded %d readings from %s.", count, csv_path)

    def calculate_stats(
        self, readings: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Calculate statistics (average, max, min) for systolic, diastolic, and pulse.
        Args:
            readings: List of readings as dicts.
        Returns:
            Dictionary with stats for each measurement.
        """

        def get_values(key):
            vals = [r[key] for r in readings if r[key] is not None]
            return vals

        stats = {}
        for key in ["systolic", "diastolic", "pulse"]:
            values = get_values(key)
            if values:
                stats[key.capitalize()] = {
                    "Average": sum(values) / len(values),
                    "Max": max(values),
                    "Min": min(values),
                }
            else:
                stats[key.capitalize()] = {"Average": None, "Max": None, "Min": None}
        return stats

    def _create_pg_table(self):
        """
        Create the blood_pressure table in PostgreSQL if it does not exist.
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blood_pressure (
                    id SERIAL PRIMARY KEY,
                    date TIMESTAMPZ,
                    systolic INTEGER NOT NULL,
                    diastolic INTEGER NOT NULL,
                    pulse INTEGER
                )
            """
            )
            conn.commit()
            cur.close()
            conn.close()
        except psycopg2.Error as e:
            logger.exception("Error creating table in PostgreSQL: %s", e)

    def add_reading(
        self, systolic: int, diastolic: int, pulse: Optional[int], date: Optional[str]
    ):
        """
        Add a new reading to the PostgreSQL database.
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cur = conn.cursor()

            # Parse provided date (if any) and store as UTC-aware timestamp
            dt_utc = None
            if date:
                # Try common formats including ISO
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

                if parsed is not None:
                    # If parsed lacks tzinfo, assume site timezone
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=ZoneInfo(SITE_TZ))
                    dt_utc = parsed.astimezone(ZoneInfo("UTC"))

            if dt_utc is None:
                dt_utc = datetime.now(tz=ZoneInfo("UTC"))

            cur.execute(
                "INSERT INTO blood_pressure (date, systolic, diastolic, pulse) VALUES (%s, %s, %s, %s)",
                (dt_utc, systolic, diastolic, pulse),
            )
            conn.commit()
            cur.close()
            conn.close()
        except psycopg2.Error as e:
            logger.exception("Error adding reading to PostgreSQL: %s", e)

    def view_readings(self):
        """
        Display all readings in a tabular format.
        """
        readings = self._load_data()
        if not readings:
            logger.info("\nNo readings found.")
            return
        logger.info("\nYour Blood Pressure Readings:")
        header = ["Date", "Systolic", "Diastolic", "Pulse"]
        logger.info("%s %s %s %s", f"{header[0]:<20}", f"{header[1]:<10}", f"{header[2]:<10}", f"{header[3]:<10}")
        logger.info("%s", "-" * 54)
        for r in readings:
            logger.info(
                "%s %s %s %s",
                f"{r['date']:<20}",
                f"{r['systolic']:<10}",
                f"{r['diastolic']:<10}",
                f"{r['pulse'] if r['pulse'] is not None else '':<10}",
            )

    def get_statistics(self):
        """
        Display statistics (average, max, min) for all readings.
        """
        readings = self._load_data()
        if not readings:
            logger.info("\nNo readings available for statistics.")
            return

        def get_values(key):
            return [r[key] for r in readings if r[key] is not None]

        stats = {}
        for key in ["systolic", "diastolic", "pulse"]:
            values = get_values(key)
            if values:
                stats[key.capitalize()] = {
                    "Average": sum(values) / len(values),
                    "Max": max(values),
                    "Min": min(values),
                }
            else:
                stats[key.capitalize()] = {"Average": None, "Max": None, "Min": None}
        logger.info("\nStatistics:")
        for measure, values in stats.items():
            logger.info("\n%s:", measure)
            for stat, value in values.items():
                if value is not None:
                    logger.info("%s: %.1f", stat, value)
                else:
                    logger.info("%s: N/A", stat)


def add_new_reading(tracker):
    """Prompt user to add a new reading."""
    try:
        systolic = int(input("Enter systolic pressure (top number): "))
        diastolic = int(input("Enter diastolic pressure (bottom number): "))
        pulse_input = input(
            "Enter pulse rate (optional, press Enter to skip): "
        ).strip()
        pulse = int(pulse_input) if pulse_input else None
        date = input(
            "Enter date/time (YYYY-MM-DD HH:MM:SS) or leave blank for now: "
        ).strip()
        if not date:
            date = None
        valid = 0 < systolic < 300 and 0 < diastolic < 200
        if pulse is not None:
            valid = valid and 0 < pulse < 250
        if valid:
            tracker.add_reading(systolic, diastolic, pulse, date)
            logger.info("Reading added successfully!")
        else:
            logger.info("Invalid values. Please enter realistic measurements.")
    except ValueError:
        logger.info("Please enter valid numbers.")


def load_csv_readings(tracker):
    """Prompt user to load readings from a CSV file."""
    path = input("Enter path to CSV file: ").strip()
    tracker.load_csv(path)


def main_menu(tracker):
    """
    Command-line interface main menu loop for user interaction.
    Args:
        tracker (BloodPressureTracker): The main tracker instance for managing readings.
    """
    menu_actions = {
        "1": lambda: add_new_reading(tracker),
        "2": tracker.view_readings,
        "3": tracker.get_statistics,
        "4": lambda: tracker.enable_postgres(not tracker.pg_enabled),
        "5": lambda: load_csv_readings(tracker),
        "6": lambda: logger.info("Thank you for using Blood Pressure Tracker!"),
    }

    while True:
        logger.info("\nBlood Pressure Tracker")
        logger.info("1. Add new reading")
        logger.info("2. View all readings")
        logger.info("3. View statistics")
        logger.info(
            "4. Toggle PostgreSQL saving (currently: %s )",
            "ON" if tracker.pg_enabled else "OFF",
        )
        logger.info("5. Load readings from CSV file")
        logger.info("6. Exit")

        choice = input("\nEnter your choice (1-6): ")

        if choice in menu_actions:
            if choice == "6":
                menu_actions[choice]()
                break
            menu_actions[choice]()
        else:
            logger.info("Invalid choice. Please try again.")


def main():
    """
    Main loop for the command-line interface.
    Variables:
        tracker (BloodPressureTracker): The main tracker instance for managing readings.
    """
    tracker = BloodPressureTracker()

    main_menu(tracker)


if __name__ == "__main__":
    main()
