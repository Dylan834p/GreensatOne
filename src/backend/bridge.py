import serial.tools.list_ports
import json
import sqlite3
import os
from datetime import datetime, timedelta, date
import time

USE_SIM = False
# Make this True to use simulated data

if USE_SIM:
    try:
        from sim_hardware import FakeSerial as Serial
    except ImportError:
        import serial
        Serial = serial.Serial
else:
    import serial
    Serial = serial.Serial

# --- CONFIGURATION ---
PORT_USB = 'COM5'
BAUDRATE = 115200
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'greensat.db')

RAW_RETENTION_HOURS = 48
VACUUM_HOUR = 3  # 03h00

# Console colors
C_RESET = "\033[0m"
C_PINK = "\033[95m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_BOLD = "\033[1m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"

# ----------------------------
# Time helpers
# ----------------------------
def floor_to_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)

def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# ----------------------------
# DB setup + queries
# ----------------------------
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
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
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
    # Summary tables
    cur.execute(f"CREATE TABLE IF NOT EXISTS hourly_history (time_label TEXT PRIMARY KEY, {HOURLY_COLS})")
    cur.execute(f"CREATE TABLE IF NOT EXISTS daily_history  (time_label TEXT PRIMARY KEY, {HOURLY_COLS})")

    # Helpful indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mesures_datetime ON mesures(date_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hourly_time     ON hourly_history(time_label)")
    conn.commit()

def load_last_hour_start(conn: sqlite3.Connection) -> datetime:
    """
    Returns the next hour start that still needs processing.
    Strategy:
      - If hourly_history has rows: last_hour_start = max(time_label) + 1 hour
      - Else: last_hour_start = floor(now)  (start clean; no backfill)
    """
    cur = conn.cursor()
    cur.execute("SELECT MAX(time_label) FROM hourly_history")
    row = cur.fetchone()
    if row and row[0]:
        last = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        return last + timedelta(hours=1)
    return floor_to_hour(datetime.now())

def insert_raw(conn: sqlite3.Connection, data: dict, now: datetime) -> bool:
    try:
        cur = conn.cursor()
        
        temp = data.get("temp_c", data.get("temp", 0))
        hum  = data.get("humidity", data.get("hum", 0))
        gas  = data.get("gas_pct", 0)
        lux  = data.get("lux", 0)
        pres = data.get("pressure_hpa", data.get("press", 0))
        
        air_pct = round(100.0 - float(gas), 1)

        cur.execute("""
            INSERT INTO mesures (date_time, temp, hum, gas_pct, lux, press, air_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fmt(now),
            temp,
            hum,
            gas,
            lux,
            pres,
            air_pct
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"{C_RED}❌ DB insert error: {e}{C_RESET}")
        return False

def aggregate_hour(conn: sqlite3.Connection, start: datetime, end: datetime):
    """
    Aggregate raw mesures rows in [start, end) into hourly_history.
    Inserts only if there is at least 1 sample (HAVING COUNT(*) > 0).
    """
    cur = conn.cursor()
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
          ? AS time_label,
          MIN(temp), MAX(temp), AVG(temp),
          MIN(hum),  MAX(hum),  AVG(hum),
          MIN(lux),  MAX(lux),  AVG(lux),
          MIN(gas_pct), MAX(gas_pct), AVG(gas_pct),
          MIN(press), MAX(press), AVG(press),
          MIN(air_pct), MAX(air_pct), AVG(air_pct),
          COUNT(*)
        FROM mesures
        WHERE date_time >= ?
          AND date_time <  ?
        HAVING COUNT(*) > 0
    """, (fmt(start), fmt(start), fmt(end)))
    conn.commit()

def aggregate_day_from_hourly(conn: sqlite3.Connection, day_start: datetime, day_end: datetime):
    """
    Aggregate hourly_history rows in [day_start, day_end) into daily_history.
    day_start/day_end should be midnight boundaries.
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
          substr(?, 1, 10) AS time_label,
          MIN(temp_min), MAX(temp_max), AVG(temp_avg),
          MIN(hum_min),  MAX(hum_max),  AVG(hum_avg),
          MIN(lux_min),  MAX(lux_max),  AVG(lux_avg),
          MIN(gas_min),  MAX(gas_max),  AVG(gas_avg),
          MIN(press_min), MAX(press_max), AVG(press_avg),
          MIN(air_min),  MAX(air_max),  AVG(air_avg),
          SUM(sample_count)
        FROM hourly_history
        WHERE time_label >= ?
          AND time_label <  ?
        HAVING SUM(sample_count) > 0
    """, (fmt(day_start), fmt(day_start), fmt(day_end)))
    conn.commit()

def prune_raw(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM mesures WHERE date_time < datetime('now', ?)",
        (f"-{RAW_RETENTION_HOURS} hours",)
    )
    conn.commit()

def maybe_vacuum(conn: sqlite3.Connection):
    """
    VACUUM can’t run inside a transaction. Use autocommit mode.
    """
    try:
        conn.isolation_level = None
        conn.execute("VACUUM")
    except sqlite3.OperationalError as e:
        print(f"{C_YELLOW}⚠️ Vacuum failed: {e}{C_RESET}")
    finally:
        conn.isolation_level = ""

# ----------------------------
# UI helpers
# ----------------------------
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def choose_port():
    global PORT_USB
    while True:
        ports = serial.tools.list_ports.comports()
        if not ports:
            print(f"{C_RED}{C_BOLD}No COM ports found! Retrying in 5s...{C_RESET}")
            time.sleep(5)
            continue
            
        if len(ports) == 1:
            PORT_USB = ports[0].device
            return

        print(f"\n{C_CYAN}Multiple COM ports found:{C_RESET}")
        for i, port in enumerate(ports):
            print(f"{i+1}: {port.device} ({port.description})")
        
        try:
            choice = input(f"{C_YELLOW}Choose a port [1-{len(ports)}] (or Enter to refresh): {C_RESET}")
            if not choice: continue
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                PORT_USB = ports[idx].device
                return
        except ValueError:
            print(f"{C_RED}Invalid input.{C_RESET}")

# ----------------------------
# Main loop
# ----------------------------
if __name__ == "__main__":
    clear_screen()
    choose_port()

    # DB open once (outside the connection loop)
    conn = open_db()
    ensure_schema(conn)
    last_hour_start = load_last_hour_start(conn)
    last_vacuum_day: date | None = None

    print(f"{C_GREEN}SQL Bridge Initialized.{C_RESET}")

    while True: # Outer Loop: Handles Reconnections
        try:
            print(f"{C_YELLOW}Connecting to {PORT_USB}...{C_RESET}")
            ser = Serial(PORT_USB, BAUDRATE, timeout=1)
            print(f"{C_GREEN}✅ Connected! Bridge running.{C_RESET}")

            while True: # Inner Loop: Handles Data Processing
                if ser.in_waiting <= 0:
                    time.sleep(0.1)
                    continue

                line = ser.readline().decode("utf-8", errors="ignore").strip()
                
                if not (line.startswith("{") and line.endswith("}")):
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if "error" in data:
                    print(f"{C_RED}⚠️ Pico Sensor Error: {data['error']}{C_RESET}")
                    continue

                now = datetime.now()
                print(line)
                # Save Data
                if insert_raw(conn, data, now):
                    print(f"{C_GREEN}📥 [{now.strftime('%H:%M:%S')}] Telemetry Stored")

                # Aggregation & Rollover
                current_hour_start = floor_to_hour(now)
                if current_hour_start > last_hour_start:
                    while last_hour_start < current_hour_start:
                        start = last_hour_start
                        end = start + timedelta(hours=1)
                        aggregate_hour(conn, start, end)
                        if end.hour == 0:
                            aggregate_day_from_hourly(conn, end - timedelta(days=1), end)
                        last_hour_start = end
                    prune_raw(conn)

                # Maintenance
                if now.hour == VACUUM_HOUR and last_vacuum_day != now.date():
                    maybe_vacuum(conn)
                    last_vacuum_day = now.date()

        except (Serial.SerialException, OSError) as e:
            print(f"{C_RED}🔌 Disconnected: {e}{C_RESET}")
            print(f"{C_YELLOW}Retrying connection in 5 seconds...{C_RESET}")
            try: ser.close() 
            except: pass
            time.sleep(5)
            # Re-scan ports in case the COM number changed after replugging
            choose_port() 

        except KeyboardInterrupt:
            print(f"\n{C_YELLOW}Stopping SQL Bridge...{C_RESET}")
            break
        except Exception as e:
            print(f"{C_RED}💥 Unexpected Error: {e}{C_RESET}")
            time.sleep(5)

    conn.close()
    print(f"{C_CYAN}Bridge Shutdown.{C_RESET}")