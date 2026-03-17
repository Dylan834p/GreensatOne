import sqlite3
import threading
from datetime import datetime
threads = []

DB_PATH = 'greensat.db'

# --- Aggregation and Maintenance Scripts ---

def db_manager():
    """
    Background worker that handles schema maintenance and scheduled aggregations.
    Runs once at startup, then triggers every hour on the hour.
    """
    print("🔧 DB Manager: Starting maintenance thread...")
    
    while True:
        now = datetime.now()
        
        # 2. Trigger at the top of every hour (Minute 0)
        # We also check seconds < 10 to ensure we don't miss the window 
        # but don't run it multiple times in the same minute.
        if now.minute == 0:
            print(f"🕒 DB Manager: Running scheduled tasks for {now.strftime('%Y-%m-%d %H:00')}...")
            try:
                with open_db() as conn:
                    aggregate_hours(conn)
                    aggregate_days(conn)
                    prune_raw(conn)
                    
                    # Optional: Vacuum once a day at midnight
                    if now.hour == 0:
                        print("🧹 DB Manager: Running daily VACUUM...")
                        maybe_vacuum(conn)
                        
                print("✅ DB Manager: Maintenance complete.")
            except Exception as e:
                print(f"❌ DB Manager Error: {e}")
            
            # Sleep for 61 seconds to ensure we exit the minute 0 window
            time.sleep(61)
        else:
            # Sleep and check every 30 seconds to stay responsive
            time.sleep(30)
# Helpers

def open_db():
    """Helper to create a thread-safe connection with reasonable timeouts."""
    conn = sqlite3.connect(DB_PATH, timeout=20)
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

def ensure_schema(conn: sqlite3.Connection):
    """
    Initializes the database schema based on the provided specifications.
    
    Architecture:
    - mesures: Raw telemetry with auto-incrementing ID.
    - hourly_history: Aggregated data with a composite Primary Key 
      on (time_label, device_id) to support UPSERT operations.
    - daily_history: Same structure as hourly, optimized for long-term storage.
    """
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
            device_id INTEGER NOT NULL,
        )
    """)

    # Definition for history tables (Hourly and Daily)
    # Both use the same column structure but different time grain
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

    # 2. Hourly History Table
    cur.execute(f"CREATE TABLE IF NOT EXISTS hourly_history ({history_columns})")

    # 3. Daily History Table
    cur.execute(f"CREATE TABLE IF NOT EXISTS daily_history ({history_columns})")

    # 4. Performance Indexes
    # Crucial for the strftime filters in the aggregation scripts
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mesures_dt ON mesures(date_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hourly_dt ON hourly_history(time_label)")

    conn.commit()

    return True