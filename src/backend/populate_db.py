import sqlite3
import os
import random
import math
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'greensat.db')

def get_sim_val(current_date):
    """Generates a realistic set of sensor data for a specific point in time."""
    day_of_year = current_date.timetuple().tm_yday
    hour = current_date.hour + current_date.minute / 60.0
    
    # Temperature: Seasonal + Daily oscillation
    season_temp = -math.cos((day_of_year - 20) / 365 * 2 * math.pi) * 10 
    daily_temp = -math.cos(((hour - 4) / 24) * 2 * math.pi) * 5
    temp = 15 + season_temp + daily_temp + random.uniform(-1, 1)
    
    # Lux: Sun angle logic
    if 6 <= hour <= 21:
        sun_angle = math.sin(((hour - 6) / 15) * math.pi)
        lux = max(0, 1000 * sun_angle + random.uniform(-50, 50))
    else:
        lux = 0
        
    hum = max(20, min(100, 60 - (daily_temp * 2) + random.uniform(-5, 5)))
    press = 1013.0 + random.uniform(-5, 5)
    gas = random.uniform(2, 5) + (random.uniform(10, 20) if random.random() > 0.99 else 0)
    air = 100 - gas
    
    return temp, hum, lux, gas, press, air

def populate_tiered_db(years=5):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Define columns for history tables
    cols = (
        "temp_min, temp_max, temp_avg, hum_min, hum_max, hum_avg, "
        "lux_min, lux_max, lux_avg, gas_min, gas_max, gas_avg, "
        "press_min, press_max, press_avg, air_min, air_max, air_avg, sample_count"
    )

    # Reset tables
    cursor.execute("DROP TABLE IF EXISTS mesures")
    cursor.execute("DROP TABLE IF EXISTS hourly_history")
    cursor.execute("DROP TABLE IF EXISTS daily_history")
    
    cursor.execute(f"CREATE TABLE hourly_history (time_label TEXT PRIMARY KEY, {cols})")
    cursor.execute(f"CREATE TABLE daily_history (time_label TEXT PRIMARY KEY, {cols})")
    cursor.execute('''CREATE TABLE mesures (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date_time TEXT, 
        temp REAL, hum REAL, lux REAL, gas_pct REAL, press REAL, air_pct REAL
    )''')

    now = datetime.now()
    
    # 1. GENERATE DAILY HISTORY (Years 1 to 10)
    print(f"⏳ Generating {years} years of Daily history...")
    daily_data = []
    for d in range(int(365 * years)):
        date = now - timedelta(days=d)
        # Simplified: Daily stats based on 4 samples (dawn, noon, dusk, night)
        samples = [get_sim_val(date.replace(hour=h)) for h in [4, 12, 18, 0]]
        row = [date.strftime("%Y-%m-%d")]
        for i in range(6): # For each of the 6 sensors
            vals = [s[i] for s in samples]
            row.extend([round(min(vals), 2), round(max(vals), 2), round(sum(vals)/4, 2)])
        row.append(1440) # Sample count
        daily_data.append(tuple(row))
    
    cursor.executemany(f"INSERT INTO daily_history VALUES ({','.join(['?']*20)})", daily_data)

    # 2. GENERATE HOURLY HISTORY (Last 30 Days)
    print("⏳ Generating 30 days of Hourly history...")
    hourly_data = []
    for h in range(24 * 30):
        date = now - timedelta(hours=h)
        # Simplified: 2 samples per hour
        samples = [get_sim_val(date), get_sim_val(date - timedelta(minutes=30))]
        row = [date.strftime("%Y-%m-%d %H:00:00")]
        for i in range(6):
            vals = [s[i] for s in samples]
            row.extend([round(min(vals), 2), round(max(vals), 2), round(sum(vals)/2, 2)])
        row.append(60)
        hourly_data.append(tuple(row))

    cursor.executemany(f"INSERT INTO hourly_history VALUES ({','.join(['?']*20)})", hourly_data)

    # 3. GENERATE RAW DATA (Last 24 Hours)
    print("⏳ Generating 24 hours of Raw 1-min data...")
    raw_data = []
    for m in range(1440):
        date = now - timedelta(minutes=m)
        t, h, l, g, p, a = get_sim_val(date)
        raw_data.append((date.strftime("%Y-%m-%d %H:%M:%S"), 
                         round(t, 2), int(h), int(l), round(g, 2), round(p, 1), round(a, 1)))

    cursor.executemany("INSERT INTO mesures (date_time, temp, hum, lux, gas_pct, press, air_pct) VALUES (?,?,?,?,?,?,?)", raw_data)

    conn.commit()
    conn.close()
    print(f"✅ Database populated: {years}y Daily, 30d Hourly, 24h Raw.")

if __name__ == "__main__":
    try:
        user_input = input("Enter number of years to simulate (e.g., 0.5, 2, 10): ").strip()
        years_to_gen = float(user_input) if user_input else 1.0
        if years_to_gen <= 0:
            raise ValueError
    except ValueError:
        print("Invalid input. Defaulting to 1 year.")
        years_to_gen = 1.0

    populate_tiered_db(years_to_gen)