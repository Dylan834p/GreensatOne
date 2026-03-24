import sqlite3
import os,sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from shared.config import DB_PATH

RAW_RETENTION_HOURS = 48
RUN_VACUUM = True

HOURLY_COLS = (
    "temp_min, temp_max, temp_avg, "
    "hum_min, hum_max, hum_avg, "
    "lux_min, lux_max, lux_avg, "
    "gas_min, gas_max, gas_avg, "
    "press_min, press_max, press_avg, "
    "sample_count, device_id INTEGER NOT NULL"
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
        device_id INTEGER
    )''')
    
    cur.execute(f"CREATE TABLE IF NOT EXISTS hourly_history (time_label TEXT NOT NULL, {HOURLY_COLS}, PRIMARY KEY(time_label, device_id))")
    cur.execute(f"CREATE TABLE IF NOT EXISTS daily_history (time_label TEXT NOT NULL, {HOURLY_COLS}, PRIMARY KEY(time_label, device_id))")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_mesures_datetime ON mesures(date_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hourly_time ON hourly_history(time_label)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_daily_time ON daily_history(time_label)")

    conn.commit()

def repair_hourly(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO hourly_history (
          time_label,
          device_id,
          temp_min, temp_max, temp_avg,
          hum_min, hum_max, hum_avg,
          lux_min, lux_max, lux_avg,
          gas_min, gas_max, gas_avg,
          press_min, press_max, press_avg,
          sample_count
        )
        SELECT
          strftime('%Y-%m-%d %H:00:00', date_time) AS hr,
          device_id,
          MIN(temp), MAX(temp), AVG(temp),
          MIN(hum), MAX(hum), AVG(hum),
          MIN(lux), MAX(lux), AVG(lux),
          MIN(gas_pct), MAX(gas_pct), AVG(gas_pct),
          MIN(press), MAX(press), AVG(press),
          COUNT(*)
        FROM mesures
        WHERE date_time < datetime('now','start of hour')
        GROUP BY hr, device_id
        HAVING COUNT(*) > 0
    """)
    conn.commit()

    cur.execute("""
        SELECT COUNT(*)
        FROM hourly_history
        WHERE time_label < datetime('now','start of hour')
    """)
    return cur.fetchone()[0]

def repair_daily(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO daily_history (
          time_label,
          device_id,
          temp_min, temp_max, temp_avg,
          hum_min, hum_max, hum_avg,
          lux_min, lux_max, lux_avg,
          gas_min, gas_max, gas_avg,
          press_min, press_max, press_avg,
          sample_count
        )
        SELECT
          strftime('%Y-%m-%d', time_label) AS dy,
          device_id,
          MIN(temp_min), MAX(temp_max), AVG(temp_avg),
          MIN(hum_min), MAX(hum_max), AVG(hum_avg),
          MIN(lux_min), MAX(lux_max), AVG(lux_avg),
          MIN(gas_min), MAX(gas_max), AVG(gas_avg),
          MIN(press_min), MAX(press_max), AVG(press_avg),
          SUM(sample_count)
        FROM hourly_history
        WHERE time_label < datetime('now','start of day')
        GROUP BY dy, device_id
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
    iso = conn.isolation_level
    try:
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.isolation_level = iso

def main():
    conn = open_db()
    try:
        ensure_schema(conn)
        repair_hourly(conn)
        repair_daily(conn)
        prune_raw(conn, RAW_RETENTION_HOURS)
        if RUN_VACUUM:
            vacuum(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()