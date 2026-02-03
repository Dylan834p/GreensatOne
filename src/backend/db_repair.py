import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "greensat.db")

RAW_RETENTION_HOURS = 48
RUN_VACUUM = True  # set False if you don't want vacuum each run

HOURLY_COLS = (
    "temp_min, temp_max, temp_avg, "
    "hum_min, hum_max, hum_avg, "
    "lux_min, lux_max, lux_avg, "
    "gas_min, gas_max, gas_avg, "
    "press_min, press_max, press_avg, "
    "air_min, air_max, air_avg, "
    "sample_count"
)

def open_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn

def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS mesures (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        date_time TEXT, 
        temp REAL, 
        hum REAL, 
        lux REAL, 
        gas_pct REAL, 
        press REAL, 
        air_pct REAL
    )''')
    # Ensure summary tables exist (matches your bridge structure)
    cur.execute(f"CREATE TABLE IF NOT EXISTS hourly_history (time_label TEXT PRIMARY KEY, {HOURLY_COLS})")
    cur.execute(f"CREATE TABLE IF NOT EXISTS daily_history  (time_label TEXT PRIMARY KEY, {HOURLY_COLS})")

    # Helpful indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mesures_datetime ON mesures(date_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hourly_time     ON hourly_history(time_label)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_daily_time      ON daily_history(time_label)")

    conn.commit()

def repair_hourly(conn: sqlite3.Connection) -> int:
    """
    Rebuild/refresh hourly_history for all COMPLETED hours present in raw data.
    Excludes the current (incomplete) hour.
    Idempotent: INSERT OR REPLACE.
    Returns number of hourly rows written/updated.
    """
    cur = conn.cursor()

    # This builds hour summaries for every hour that has any raw rows, but only for closed hours
    cur.execute("""
        INSERT OR REPLACE INTO hourly_history (
          time_label,
          temp_min, temp_max, temp_avg,
          hum_min, hum_max, hum_avg,
          lux_min, lux_max, lux_avg,
          gas_min, gas_max, gas_avg,
          press_min, press_max, press_avg,
          air_min, air_max, air_avg,
          sample_count
        )
        SELECT
          strftime('%Y-%m-%d %H:00:00', date_time) AS hr,
          MIN(temp), MAX(temp), AVG(temp),
          MIN(hum),  MAX(hum),  AVG(hum),
          MIN(lux),  MAX(lux),  AVG(lux),
          MIN(gas_pct), MAX(gas_pct), AVG(gas_pct),
          MIN(press), MAX(press), AVG(press),
          MIN(air_pct), MAX(air_pct), AVG(air_pct),
          COUNT(*)
        FROM mesures
        WHERE date_time < datetime('now','start of hour')  -- exclude current hour
        GROUP BY hr
        HAVING COUNT(*) > 0
    """)
    conn.commit()

    # How many hourly rows exist for closed hours in raw? (approx measure of work)
    cur.execute("""
        SELECT COUNT(*)
        FROM hourly_history
        WHERE time_label < datetime('now','start of hour')
    """)
    return cur.fetchone()[0]

def repair_daily(conn: sqlite3.Connection) -> int:
    """
    Rebuild/refresh daily_history for all COMPLETED days present in hourly_history.
    Excludes today (incomplete day).
    Idempotent: INSERT OR REPLACE.
    Returns number of daily rows written/updated.
    """
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO daily_history (
          time_label,
          temp_min, temp_max, temp_avg,
          hum_min, hum_max, hum_avg,
          lux_min, lux_max, lux_avg,
          gas_min, gas_max, gas_avg,
          press_min, press_max, press_avg,
          air_min, air_max, air_avg,
          sample_count
        )
        SELECT
          strftime('%Y-%m-%d', time_label) AS dy,
          MIN(temp_min), MAX(temp_max), AVG(temp_avg),
          MIN(hum_min),  MAX(hum_max),  AVG(hum_avg),
          MIN(lux_min),  MAX(lux_max),  AVG(lux_avg),
          MIN(gas_min),  MAX(gas_max),  AVG(gas_avg),
          MIN(press_min), MAX(press_max), AVG(press_avg),
          MIN(air_min),  MAX(air_max),  AVG(air_avg),
          SUM(sample_count)
        FROM hourly_history
        WHERE time_label < datetime('now','start of day')   -- exclude today
        GROUP BY dy
        HAVING SUM(sample_count) > 0
    """)
    conn.commit()

    cur.execute("""
        SELECT COUNT(*)
        FROM daily_history
        WHERE time_label < date('now')
    """)
    return cur.fetchone()[0]

def prune_raw(conn: sqlite3.Connection, retention_hours: int) -> int:
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM mesures")
    before = cur.fetchone()[0]

    cur.execute(
        "DELETE FROM mesures WHERE date_time < datetime('now', ?)",
        (f"-{retention_hours} hours",)
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM mesures")
    after = cur.fetchone()[0]

    return before - after

def vacuum(conn: sqlite3.Connection):
    # VACUUM can't run inside a transaction
    iso = conn.isolation_level
    try:
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.isolation_level = iso

def main():
    print(f"🔧 DB repair started: {DB_PATH}")
    print(f"   Now: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = open_db()
    try:
        ensure_schema(conn)

        # 1) Repair hourly from raw (completed hours only)
        hourly_count = repair_hourly(conn)
        print(f"✅ Hourly repaired (rows present for closed hours): {hourly_count}")

        # 2) Repair daily from hourly (completed days only)
        daily_count = repair_daily(conn)
        print(f"✅ Daily repaired (rows present for closed days): {daily_count}")

        # 3) Prune raw back to retention
        deleted = prune_raw(conn, RAW_RETENTION_HOURS)
        print(f"🧹 Raw pruned: deleted {deleted} row(s) older than {RAW_RETENTION_HOURS}h")

        # 4) Optional vacuum
        if RUN_VACUUM:
            print("🧹 VACUUM...")
            vacuum(conn)
            print("✅ VACUUM done.")

        print("✅ DB repair complete.")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
