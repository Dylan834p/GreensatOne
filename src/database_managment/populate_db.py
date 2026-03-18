import sqlite3
import os
import random
import math
from datetime import datetime, timedelta
from shared.config import DB_PATH

def get_sim_val(current_date, device_id=0):
    """
    Generates realistic sensor data. 
    Uses device_id to create unique 'micro-climates' for each device.
    """
    day_of_year = current_date.timetuple().tm_yday
    hour = current_date.hour + current_date.minute / 60.0
    
    # Each device gets a slight unique bias based on its ID
    dev_bias = (device_id * 1.2) - 2.0 
    
    season_temp = -math.cos((day_of_year - 20) / 365 * 2 * math.pi) * 10 
    daily_temp = -math.cos(((hour - 4) / 24) * 2 * math.pi) * 5
    temp = 15 + season_temp + daily_temp + dev_bias + random.uniform(-1, 1)
    
    if 6 <= hour <= 21:
        sun_angle = math.sin(((hour - 6) / 15) * math.pi)
        lux = max(0, 1000 * sun_angle + (device_id * 10) + random.uniform(-50, 50))
    else:
        lux = 0
        
    hum = max(20, min(100, 60 - (daily_temp * 2) - dev_bias + random.uniform(-5, 5)))
    press = 1013.0 + random.uniform(-5, 5)
    gas = random.uniform(2, 5) + (random.uniform(10, 20) if random.random() > 0.99 else 0)
    
    return temp, hum, lux, gas, press

def populate_tiered_db(years=1, num_devices=1):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cols_def = (
        "temp_min REAL, temp_max REAL, temp_avg REAL, "
        "hum_min REAL, hum_max REAL, hum_avg REAL, "
        "lux_min REAL, lux_max REAL, lux_avg REAL, "
        "gas_min REAL, gas_max REAL, gas_avg REAL, "
        "press_min REAL, press_max REAL, press_avg REAL, "
        "sample_count INTEGER, device_id INTEGER NOT NULL"
    )

    # Clean start
    cursor.execute("DROP TABLE IF EXISTS mesures")
    cursor.execute("DROP TABLE IF EXISTS hourly_history")
    cursor.execute("DROP TABLE IF EXISTS daily_history")
    
    cursor.execute(f"CREATE TABLE hourly_history (time_label TEXT NOT NULL, {cols_def}, PRIMARY KEY(time_label, device_id))")
    cursor.execute(f"CREATE TABLE daily_history (time_label TEXT NOT NULL, {cols_def}, PRIMARY KEY(time_label, device_id))")
    cursor.execute('''CREATE TABLE mesures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_time TEXT,
        temp REAL,
        hum REAL,
        lux REAL,
        gas_pct REAL,
        press REAL,
        air_pct REAL,
        device_id INTEGER
    )''')

    now = datetime.now()

    for dev_id in range(num_devices):
        print(f"📡 Generating data for Device {dev_id}...")
        
        # 1. Daily History (for specific device)
        daily_data = []
        for d in range(int(365 * years)):
            date = now - timedelta(days=d)
            samples = [get_sim_val(date.replace(hour=h), dev_id) for h in [4, 12, 18, 0]]
            row = [date.strftime("%Y-%m-%d")]
            for i in range(5): # Adjusted to 5 since get_sim_val returns 5 items
                vals = [s[i] for s in samples]
                row.extend([round(min(vals), 2), round(max(vals), 2), round(sum(vals)/4, 2)])
            row.extend([1440, dev_id])
            daily_data.append(tuple(row))
        cursor.executemany(f"INSERT INTO daily_history VALUES ({','.join(['?']*17)})", daily_data)

        # 2. Hourly History (for specific device)
        hourly_data = []
        for h in range(24 * 30):
            date = now - timedelta(hours=h)
            samples = [get_sim_val(date, dev_id), get_sim_val(date - timedelta(minutes=30), dev_id)]
            row = [date.strftime("%Y-%m-%d %H:00:00")]
            for i in range(5):
                vals = [s[i] for s in samples]
                row.extend([round(min(vals), 2), round(max(vals), 2), round(sum(vals)/2, 2)])
            row.extend([60, dev_id])
            hourly_data.append(tuple(row))
        cursor.executemany(f"INSERT INTO hourly_history VALUES ({','.join(['?']*17)})", hourly_data)

        # 3. Raw Mesures (for specific device)
        raw_data = []
        for m in range(1440):
            date = now - timedelta(minutes=m)
            # Unpacking 5 values: temp, hum, lux, gas, press
            t, h, l, g, p = get_sim_val(date, dev_id)
            # Adding a dummy value for air_pct as it's in the schema but not in get_sim_val
            a = random.uniform(90, 100) 
            raw_data.append((date.strftime("%Y-%m-%d %H:%M:%S"),
                             round(t, 2), int(h), int(l), round(g, 2), round(p, 1), round(a, 1), dev_id))
        
        cursor.executemany("INSERT INTO mesures (date_time, temp, hum, lux, gas_pct, press, air_pct, device_id) VALUES (?,?,?,?,?,?,?,?)", raw_data)

    conn.commit()
    conn.close()
    print(f"\n✅ SUCCESS: Database populated for {num_devices} devices.")


if __name__ == "__main__":
    try:
        y_input = input("Enter number of years to simulate: ").strip()
        years_to_gen = float(y_input) if y_input else 1.0
        
        d_input = input("Enter number of devices to simulate: ").strip()
        num_devs = int(d_input) if d_input else 1
    except ValueError:
        print("Invalid input. Defaulting to 2 year / 2 device.")
        years_to_gen, num_devs = 2.0, 2

    populate_tiered_db(years_to_gen, num_devs)