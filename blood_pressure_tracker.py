import pandas as pd
from datetime import datetime
import psycopg2
from typing import Optional, Dict, Any

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

    def _load_data(self):
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

    def _create_pg_table(self):
        """
        Create the blood_pressure table in PostgreSQL if it does not exist.
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS blood_pressure (
                    id SERIAL PRIMARY KEY,
                    date TIMESTAMP,
                    systolic INTEGER,
                    diastolic INTEGER,
                    pulse INTEGER NULL
                )
            ''')
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error creating table: {e}")

    def _save_to_postgres(self, reading: dict):
        """
        Save a single reading to the PostgreSQL database.
        Args:
            reading (dict): A dictionary with keys 'date', 'systolic', 'diastolic', 'pulse'.
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO blood_pressure (date, systolic, diastolic, pulse) VALUES (%s, %s, %s, %s)",
                (reading['date'], reading['systolic'], reading['diastolic'], reading.get('pulse', None))
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error saving to PostgreSQL: {e}")

    def add_reading(self, systolic: int, diastolic: int, pulse: Optional[int] = None, date: Optional[str] = None):
        """
        Add a new reading and save to PostgreSQL.
        Args:
            systolic (int): Systolic blood pressure value.
            diastolic (int): Diastolic blood pressure value.
            pulse (int, optional): Pulse rate value.
            date (str, optional): Date/time string for the reading. Defaults to current date/time.
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        reading = {
            'date': date,
            'systolic': systolic,
            'diastolic': diastolic
        }
        if pulse is not None:
            reading['pulse'] = pulse
        self._save_to_postgres(reading)

    def view_readings(self):
        """
        Display all readings in a tabular format.
        """
        readings = self._load_data()
        if not readings:
            print("\nNo readings found.")
            return
        df = pd.DataFrame(readings)
        print("\nYour Blood Pressure Readings:")
        print(df.to_string(index=False))

    def get_statistics(self):
        """
        Display statistics (average, max, min) for all readings.
        """
        readings = self._load_data()
        if not readings:
            print("\nNo readings available for statistics.")
            return
        df = pd.DataFrame(readings)
        stats = {
            'Systolic': {
                'Average': df['systolic'].mean(),
                'Max': df['systolic'].max(),
                'Min': df['systolic'].min()
            },
            'Diastolic': {
                'Average': df['diastolic'].mean(),
                'Max': df['diastolic'].max(),
                'Min': df['diastolic'].min()
            },
            'Pulse': {
                'Average': df['pulse'].mean(),
                'Max': df['pulse'].max(),
                'Min': df['pulse'].min()
            }
        }
        print("\nStatistics:")
        for measure, values in stats.items():
            print(f"\n{measure}:")
            for stat, value in values.items():
                print(f"{stat}: {value:.1f}")

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

