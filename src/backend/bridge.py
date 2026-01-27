import serial
import serial.tools.list_ports
import json
import sqlite3
import os
from datetime import datetime

# --- CONFIGURATION ---
PORT_USB = 'COM5'
BAUDRATE = 115200
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'greensat.db')

# Console colors
C_RESET = "\033[0m"
C_PINK = "\033[95m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_BOLD = "\033[1m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"

def save_to_db(data):
    """Inserts data into the SQLite database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA journal_mode=WAL;')
        cursor = conn.cursor()
        
        # Insert values
        cursor.execute('''
            INSERT INTO mesures (date_time, temp, hum, gaz_pct, lux, press, air_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['date_time'], 
            data.get('temp', 0), 
            data.get('hum', 0), 
            data.get('gaz_pct', 0), 
            data.get('lux', 0), 
            data.get('press', 0), 
            data.get('air_pct', 0)
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == "__main__":
    clear_screen()
    ports = serial.tools.list_ports.comports()
    if len(ports) > 1:
        print(f"{C_RED}Multiple COM ports found:{C_RESET}")
        for i, port in enumerate(ports):
            print(f"{i+1}: {port.device}")
        while True:
            choice = int(input("Choose a COM port to use [0-10]: "))
            if choice <= len(ports) and choice > 0:
                PORT_USB = ports[choice-1].device
                break
            else:
                print("Invalid selection....")

    elif len(ports) == 1:
        PORT_USB = ports[0].device
    else:
        print(f"{C_RED}{C_BOLD}No COM ports found!{C_RESET}")
        exit()


    print(f"{C_YELLOW}Starting SQL Bridge...{C_RESET}")
    try:
        try:
            ser = serial.Serial(PORT_USB, BAUDRATE, timeout=1)
        except Exception as e:
            print(e)
            exit
        print(f"{C_GREEN}Bridge running!{C_RESET}")
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                try:
                    if line.startswith('{'):
                        data = json.loads(line)
                        if "error" not in data:
                            # Add timestamp
                            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            data["date_time"] = now
                            
                            # Calculate Air Quality if missing
                            if "air_pct" not in data:
                                data["air_pct"] = round(100 - data.get("gaz_pct", 0), 1)

                            # SQL Save
                            if save_to_db(data):
                                print(f"{C_GREEN}>> [SQL] Data saved at {now}{C_RESET}")
                except:
                    pass
    except Exception as e:
        print(f"Error: {e}")