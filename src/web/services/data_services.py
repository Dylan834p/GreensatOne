import sqlite3
from datetime import datetime
import time
from shared.config import DB_PATH
threads = []

# --- Aggregation and Maintenance Scripts ---

import time
from datetime import datetime, timedelta

def db_manager():
    """
    Handles schema maintenance and hourly aggregations.
    Execution occurs immediately upon startup and synchronizes to the next hour.
    """
    initial_run = True

    while True:
        now = datetime.now()

        if not initial_run:
            # Calculate seconds until the next hour
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            sleep_duration = (next_hour - now).total_seconds()
            time.sleep(sleep_duration)
            now = datetime.now()
        
        try:
            with open_db() as conn:
                aggregate_hours(conn)
                aggregate_days(conn)
                prune_raw(conn)
                
                if now.hour == 0:
                    maybe_vacuum(conn)
        except Exception as e:
            # Log error to stderr; avoid terminating the thread
            print(f"Database maintenance failure at {now}: {e}")
        
        initial_run = False

# Helpers

def open_db():
    """Helper to create a thread-safe connection with reasonable timeouts."""
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def prune_raw(conn: sqlite3.Connection):
    """
    Enforces data retention policies via age-based deletion.
    
    Logic:
    1. Mesures: Deletes raw rows older than 48 hours to save space.
    2. Hourly: Deletes summarized hours older than 90 days.
    3. Sequence: This must run AFTER aggregation to ensure data is summarized 
       before it is purged.
    """
    conn.execute("DELETE FROM mesures WHERE date_time < datetime('now', '-48 hours')")
    conn.execute("DELETE FROM hourly_history WHERE time_label < datetime('now', '-90 days')")
    conn.commit()

def maybe_vacuum(conn: sqlite3.Connection):
    """
    Rebuilds the database file to reclaim unused space and defragment the schema.
    
    Note: Requires autocommit mode (isolation_level = None) because VACUUM 
    cannot run inside an active transaction.
    """
    try:
        conn.isolation_level = None
        conn.execute("VACUUM")
    except sqlite3.OperationalError as e:
        print(f"Vacuum failed: {e}")
    finally:
        conn.isolation_level = ""


def aggregate_hours(conn: sqlite3.Connection):
    """
    Summarizes raw 'mesures' into 1-hour windows stored in 'hourly_history'.
    
    Logic:
    1. Grouping: Uses strftime to truncate 'date_time' to the start of its hour.
    2. Boundaries: Only processes data where the hour has fully concluded 
       (date_time < current hour) to avoid summarizing incomplete buckets.
    3. Idempotency: Uses UPSERT (ON CONFLICT DO UPDATE). If new data arrives 
       for an hour already summarized, it recalculates and overwrites the 
       existing row, ensuring total accuracy for late-arriving packets.
    """
    sql = """
        INSERT INTO hourly_history (
            time_label, device_id, 
            temp_min, temp_max, temp_avg,
            hum_min, hum_max, hum_avg,
            lux_min, lux_max, lux_avg,
            gas_min, gas_max, gas_avg,
            press_min, press_max, press_avg,
            sample_count
        )
        SELECT 
            strftime('%Y-%m-%d %H:00:00', date_time) as hour_bucket,
            device_id,
            MIN(temp), MAX(temp), AVG(temp),
            MIN(hum), MAX(hum), AVG(hum),
            MIN(lux), MAX(lux), AVG(lux),
            MIN(gas_pct), MAX(gas_pct), AVG(gas_pct),
            MIN(press), MAX(press), AVG(press),
            COUNT(*)
        FROM mesures
        WHERE date_time < strftime('%Y-%m-%d %H:00:00', 'now')
        GROUP BY hour_bucket, device_id
        ON CONFLICT(time_label, device_id) DO UPDATE SET
            temp_min = excluded.temp_min, temp_max = excluded.temp_max, temp_avg = excluded.temp_avg,
            hum_min = excluded.hum_min, hum_max = excluded.hum_max, hum_avg = excluded.hum_avg,
            lux_min = excluded.lux_min, lux_max = excluded.lux_max, lux_avg = excluded.lux_avg,
            gas_min = excluded.gas_min, gas_max = excluded.gas_max, gas_avg = excluded.gas_avg,
            press_min = excluded.press_min, press_max = excluded.press_max, press_avg = excluded.press_avg,
            sample_count = excluded.sample_count;
    """
    conn.execute(sql)
    conn.commit()

def aggregate_days(conn: sqlite3.Connection):
    """
    Summarizes 'hourly_history' into 1-day windows stored in 'daily_history'.
    
    Logic:
    1. Source: Reads from the hourly table rather than raw data for performance.
    2. Boundaries: Only summarizes days that have ended (time_label < today's date).
    3. Self-Correction: Uses UPSERT to recalculate daily totals if the underlying 
       hourly records were updated or added after the last daily run.
    """
    sql = """
        INSERT INTO daily_history (
            time_label, device_id,
            temp_min, temp_max, temp_avg,
            hum_min, hum_max, hum_avg,
            lux_min, lux_max, lux_avg,
            gas_min, gas_max, gas_avg,
            press_min, press_max, press_avg,
            sample_count
        )
        SELECT 
            date(time_label) AS day_label,
            device_id,
            MIN(temp_min), MAX(temp_max), AVG(temp_avg),
            MIN(hum_min), MAX(hum_max), AVG(hum_avg),
            MIN(lux_min), MAX(lux_max), AVG(lux_avg),
            MIN(gas_min), MAX(gas_max), AVG(gas_avg),
            MIN(press_min), MAX(press_max), AVG(press_avg),
            SUM(sample_count)
        FROM hourly_history
        WHERE time_label < date('now')
        GROUP BY day_label, device_id
        ON CONFLICT(time_label, device_id) DO UPDATE SET
            temp_min = excluded.temp_min, temp_max = excluded.temp_max, temp_avg = excluded.temp_avg,
            hum_min = excluded.hum_min, hum_max = excluded.hum_max, hum_avg = excluded.hum_avg,
            lux_min = excluded.lux_min, lux_max = excluded.lux_max, lux_avg = excluded.lux_avg,
            gas_min = excluded.gas_min, gas_max = excluded.gas_max, gas_avg = excluded.gas_avg,
            press_min = excluded.press_min, press_max = excluded.press_max, press_avg = excluded.press_avg,
            sample_count = excluded.sample_count;
    """
    conn.execute(sql)
    conn.commit()

# Ensure database layout

def ensure_schema():
    """
    Initializes the database schema using a context manager.
    Returns True if successful, False if an error occurs.
    """
    try:
        with open_db() as conn:
            cur = conn.cursor()

            # 1. Raw Measurements Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mesures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_time TEXT,
                    temp REAL,
                    hum REAL,
                    lux REAL,
                    gas_pct REAL,
                    press REAL,
                    device_id INTEGER NOT NULL
                )
            """)

            # Definition for history tables
            history_columns = """
                time_label TEXT NOT NULL,
                temp_min REAL, temp_max REAL, temp_avg REAL,
                hum_min REAL, hum_max REAL, hum_avg REAL,
                lux_min REAL, lux_max REAL, lux_avg REAL,
                gas_min REAL, gas_max REAL, gas_avg REAL,
                press_min REAL, press_max REAL, press_avg REAL,
                sample_count INTEGER,
                device_id INTEGER NOT NULL,
                PRIMARY KEY (time_label, device_id)
            """

            # 2. History Tables
            cur.execute(f"CREATE TABLE IF NOT EXISTS hourly_history ({history_columns})")
            cur.execute(f"CREATE TABLE IF NOT EXISTS daily_history ({history_columns})")

            # 3. Performance Indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mesures_dt ON mesures(date_time)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_hourly_dt ON hourly_history(time_label)")
            
            conn.commit()
            return True

    except Exception as e:
        print(f"Database initialization failed: {e}")
        return False