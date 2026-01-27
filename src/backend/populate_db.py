import sqlite3
import os
import random
import math
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'greensat.db')

# Console colors
C_RESET = "\033[0m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_PINK = "\033[95m"

def populate_database():
    # --- USER INPUTS ---
    try:
        years = float(input(f"{C_CYAN}Enter the amount of years to simulate: {C_RESET}"))
        print(f"{C_YELLOW}Frequency options: [S]econds or [M]inutes?{C_RESET}")
        freq_type = input("Choice (S/M): ").strip().upper()
        freq_val = int(input(f"Enter interval value (every X { 'seconds' if freq_type == 'S' else 'minutes' }): "))
    except ValueError:
        print(f"{C_PINK}Invalid input. Using defaults: 1 year, every 60 minutes.{C_RESET}")
        years, freq_type, freq_val = 1, 'M', 60

    print(f"\n🔧 Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🧹 Cleaning up old table...")
    cursor.execute("DROP TABLE IF EXISTS mesures")
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mesures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_time DATETIME,
        temp REAL,
        hum REAL,
        gaz_pct REAL,
        lux REAL,
        press REAL,
        air_pct REAL
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON mesures(date_time)')

    # --- GENERATION LOGIC ---
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(365 * years))
    current_date = start_date
    
    # Define the time jump based on user input
    delta = timedelta(seconds=freq_val) if freq_type == 'S' else timedelta(minutes=freq_val)
    
    batch_data = []
    base_press = 1013.0

    print(f"⏳ Generating {years} years of history... (Please wait)")

    while current_date <= end_date:
        day_of_year = current_date.timetuple().tm_yday
        hour = current_date.hour + current_date.minute / 60.0
        
        # Seasonal/Daily simulation logic
        season_temp = -math.cos((day_of_year - 20) / 365 * 2 * math.pi) * 10 
        daily_temp = -math.cos(((hour - 4) / 24) * 2 * math.pi) * 5
        temp = 15 + season_temp + daily_temp + random.uniform(-2, 2)
        
        # Light logic
        if 6 <= hour <= 21:
            sun_angle = math.sin(((hour - 6) / 15) * math.pi)
            lux = max(0, 1000 * sun_angle + random.uniform(-100, 100))
            if season_temp < 0: lux *= 0.6 
        else:
            lux = 0
            
        hum = max(20, min(100, 60 - (daily_temp * 2) + random.uniform(-10, 10)))
        base_press = max(980, min(1040, base_press + random.uniform(-0.5, 0.5)))
        
        gaz_pct = random.uniform(2, 8)
        if random.random() > 0.995: gaz_pct += random.uniform(10, 25)
        air_pct = round(100 - gaz_pct, 1)

        batch_data.append((
            current_date.strftime("%Y-%m-%d %H:%M:%S"),
            round(temp, 1),
            int(hum),
            round(gaz_pct, 2),
            int(lux),
            round(base_press, 1),
            air_pct
        ))
        
        current_date += delta

    # --- BULK INSERT ---
    print(f"💾 Saving {len(batch_data)} records to the database...")
    cursor.executemany('''
        INSERT INTO mesures (date_time, temp, hum, gaz_pct, lux, press, air_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', batch_data)
    
    conn.commit()
    conn.close()
    print(f"{C_GREEN}✅ Done! Database populated successfully.{C_RESET}")

if __name__ == '__main__':
    populate_database()