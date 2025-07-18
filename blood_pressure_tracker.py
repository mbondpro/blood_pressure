from datetime import datetime
import psycopg2
from typing import Optional, Dict, Any, List

from bp_flask_utils import get_pgpassword

class BloodPressureTracker:
    def __init__(self):
        """
        Initialize the tracker and set up database configs.
        """
        self.pg_enabled = True
        self.pg_config: Dict[str, Any] = {
            'host': 'db',  # Docker service name for PostgreSQL
            'port': 5432,
            'database': 'bp_tracker',
            'user': 'postgres',
            'password': get_pgpassword()  # Function to retrieve the password from a secure source
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
            cur.execute("SELECT date, systolic, diastolic, pulse FROM blood_pressure ORDER BY date DESC")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [
                {'date': str(row[0]), 'systolic': row[1], 'diastolic': row[2], 'pulse': row[3] if row[3] is not None else None}
                for row in rows
            ]
        except Exception as e:
            print(f"Error loading from PostgreSQL: {e}")
            return []

    def calculate_stats(self, readings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Optional[float]]]:
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
        for key in ['systolic', 'diastolic', 'pulse']:
            values = get_values(key)
            if values:
                stats[key.capitalize()] = {
                    'Average': sum(values) / len(values),
                    'Max': max(values),
                    'Min': min(values)
                }
            else:
                stats[key.capitalize()] = {
                    'Average': None,
                    'Max': None,
                    'Min': None
                }
        return stats

    def _create_pg_table(self):
        """
        Create the blood_pressure table in PostgreSQL if it does not exist.
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blood_pressure (
                    id SERIAL PRIMARY KEY,
                    date TIMESTAMP,
                    systolic INTEGER NOT NULL,
                    diastolic INTEGER NOT NULL,
                    pulse INTEGER
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error creating table in PostgreSQL: {e}")

    def add_reading(self, systolic: int, diastolic: int, pulse: Optional[int], date: Optional[str]):
        """
        Add a new reading to the PostgreSQL database.
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cur = conn.cursor()

            datetime_format = "%Y-%m-%d %H:%M:%S"
            date_format = "%Y-%m-%d"
            dt_formats = [datetime_format, date_format]
            date_str = ''
            if date:
                for fmt in dt_formats:
                    try:
                        # Try to parse and reformat date string
                        dt = datetime.strptime(date, fmt)
                        date_str = dt.strftime(fmt)
                        break
                    except ValueError:
                        continue
            if not date_str:
                # If parsing fails or no date, fall back to now
                date_str = datetime.now().strftime(datetime_format)

            cur.execute(
                "INSERT INTO blood_pressure (date, systolic, diastolic, pulse) VALUES (%s, %s, %s, %s)",
                (date_str, systolic, diastolic, pulse)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error adding reading to PostgreSQL: {e}")

    def view_readings(self):
        """
        Display all readings in a tabular format.
        """
        readings = self._load_data()
        if not readings:
            print("\nNo readings found.")
            return
        print("\nYour Blood Pressure Readings:")
        header = ["Date", "Systolic", "Diastolic", "Pulse"]
        print("{:<20} {:<10} {:<10} {:<10}".format(*header))
        print("-" * 54)
        for r in readings:
            print("{:<20} {:<10} {:<10} {:<10}".format(
                r['date'],
                r['systolic'],
                r['diastolic'],
                r['pulse'] if r['pulse'] is not None else ""
            ))

    def get_statistics(self):
        """
        Display statistics (average, max, min) for all readings.
        """
        readings = self._load_data()
        if not readings:
            print("\nNo readings available for statistics.")
            return
        def get_values(key):
            return [r[key] for r in readings if r[key] is not None]
        stats = {}
        for key in ['systolic', 'diastolic', 'pulse']:
            values = get_values(key)
            if values:
                stats[key.capitalize()] = {
                    'Average': sum(values) / len(values),
                    'Max': max(values),
                    'Min': min(values)
                }
            else:
                stats[key.capitalize()] = {
                    'Average': None,
                    'Max': None,
                    'Min': None
                }
        print("\nStatistics:")
        for measure, values in stats.items():
            print(f"\n{measure}:")
            for stat, value in values.items():
                if value is not None:
                    print(f"{stat}: {value:.1f}")
                else:
                    print(f"{stat}: N/A")

def main_menu(tracker):
    while True:
        print("\nBlood Pressure Tracker")
        print("1. Add new reading")
        print("2. View all readings")
        print("3. View statistics")
        print("4. Toggle PostgreSQL saving (currently: {} )".format('ON' if tracker.pg_enabled else 'OFF'))
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            try:
                systolic = int(input("Enter systolic pressure (top number): "))
                diastolic = int(input("Enter diastolic pressure (bottom number): "))
                pulse_input = input("Enter pulse rate (optional, press Enter to skip): ").strip()
                pulse = int(pulse_input) if pulse_input else None
                date = input("Enter date/time (YYYY-MM-DD HH:MM:SS) or leave blank for now: ").strip()
                if not date:
                    date = None
                valid = 0 < systolic < 300 and 0 < diastolic < 200
                if pulse is not None:
                    valid = valid and 0 < pulse < 250
                if valid:
                    tracker.add_reading(systolic, diastolic, pulse, date)
                    print("Reading added successfully!")
                else:
                    print("Invalid values. Please enter realistic measurements.")
            except ValueError:
                print("Please enter valid numbers.")
                
        elif choice == '2':
            tracker.view_readings()
            
        elif choice == '3':
            tracker.get_statistics()
            
        elif choice == '4':
            tracker.enable_postgres(not tracker.pg_enabled)
        elif choice == '5':
            print("Thank you for using Blood Pressure Tracker!")
            break
            
        else:
            print("Invalid choice. Please try again.")

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

