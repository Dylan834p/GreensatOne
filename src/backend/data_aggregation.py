import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'greensat.db')

def get_brackets():
    t = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    return [
        ("Yesterday", t - timedelta(days=1), t, 1),
        ("Last Week", t - timedelta(days=7), t - timedelta(days=1), 15),
        ("Last Month", t - timedelta(days=30), t - timedelta(days=7), 30),
        ("Last 2 Months", t - timedelta(days=60), t - timedelta(days=30), 60),
        ("Remaining Year", t - timedelta(days=365), t - timedelta(days=60), 60),
        ("Historical", datetime.min, t - timedelta(days=365), 180),
    ]

def rebuild_and_align():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. Create a Master Temp Table to hold the new "Final" dataset
        cursor.execute("DROP TABLE IF EXISTS final_sync")
        cursor.execute("""
            CREATE TABLE final_sync (
                date_time TEXT,
                temp REAL, hum REAL, gaz_pct REAL, 
                lux REAL, press REAL, air_pct REAL
            )
        """)

        # 2. Process each bracket and push aggregated data into final_sync
        brackets = get_brackets()
        processed_intervals = []

        for label, start, end, interval in brackets:
            start_str = start.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end.strftime("%Y-%m-%d %H:%M:%S")
            interval_sec = interval * 60
            processed_intervals.append((start_str, end_str))

            print(f"Aggregating {label}...")
            cursor.execute("""
                INSERT INTO final_sync
                SELECT 
                    datetime((strftime('%s', date_time) / ?) * ?, 'unixepoch'),
                    AVG(temp), AVG(hum), AVG(gaz_pct), AVG(lux), AVG(press), AVG(air_pct)
                FROM mesures
                WHERE date_time >= ? AND date_time < ?
                GROUP BY 1
            """, (interval_sec, interval_sec, start_str, end_str))

        # 3. Grab the data that WASN'T in any bracket (e.g., Today's raw data and the 2mo-1yr gap)
        # This ensures we don't lose the high-res data we want to keep.
        print("Preserving remaining high-resolution data...")
        where_clause = " AND ".join([f"(date_time < '{s}' OR date_time >= '{e}')" for s, e in processed_intervals])
        cursor.execute(f"INSERT INTO final_sync SELECT date_time, temp, hum, gaz_pct, lux, press, air_pct FROM mesures WHERE {where_clause}")

        # 4. TRUNCATE AND ALIGN
        # We drop the original table and recreate it to reset the ID counter
        print("Rebuilding table to align IDs...")
        cursor.execute("DROP TABLE mesures")
        cursor.execute("""
            CREATE TABLE mesures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_time TEXT,
                temp REAL, hum REAL, gaz_pct REAL,
                lux REAL, press REAL, air_pct REAL
            )
        """)

        # 5. Move data back (ordered by date so IDs are chronological)
        cursor.execute("""
            INSERT INTO mesures (date_time, temp, hum, gaz_pct, lux, press, air_pct)
            SELECT * FROM final_sync ORDER BY date_time ASC
        """)

        # Cleanup
        cursor.execute("DROP TABLE final_sync")
        conn.commit()
        
        print("Optimization complete. Vacuuming disk space...")
        cursor.execute("VACUUM")
        print("Success! IDs are now sequential and data is aggregated.")

    except Exception as e:
        conn.rollback()
        print(f"Failed to rebuild: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    rebuild_and_align()