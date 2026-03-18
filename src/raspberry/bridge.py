import serial
import serial.tools.list_ports
import json
import time
import os

# --- CONFIGURATION ---
USE_SIM = False
COM_PORT = None
BAUDRATE = 115200

if USE_SIM:
    try:
        from sim_hardware import FakeSerial as Serial
    except ImportError:
        Serial = serial.Serial
else:
    Serial = serial.Serial

def choose_port():
    global COM_PORT
    if USE_SIM: 
        COM_PORT = "SIM_PORT"
        return True
    
    while True:
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("No COM ports found! Retrying in 5 seconds...")
            time.sleep(5)
            continue

        if len(ports) == 1:
            COM_PORT = ports[0].device
            print(f"Automatically selected {COM_PORT}")
            return True
        else:
            print("\nAvailable Ports:")
            for i, p in enumerate(ports):
                print(f"{i+1}: {p.device}")
            
            try:
                choice = input(f"Select port [1-{len(ports)}] (or press Enter to refresh): ")
                if not choice.strip():
                    continue
                idx = int(choice) - 1
                if 0 <= idx < len(ports):
                    COM_PORT = ports[idx].device
                    return True
            except ValueError:
                print("Invalid input. Refreshing...")
                time.sleep(1)

if __name__ == "__main__":
    choose_port()

    while True:
        try:
            print(f"Connecting to {COM_PORT}...")
            ser = Serial(COM_PORT, BAUDRATE, timeout=1)
            print("Bridge Active. Reading Data...")

            while True:
                if ser.in_waiting <= 0:
                    time.sleep(0.1)
                    continue

                line = ser.readline().decode("utf-8", errors="ignore").strip()
                
                if not (line.startswith("{") and line.endswith("}")):
                    continue

                try:
                    data = json.loads(line)
                    if "error" in data:
                        print(f"Sensor Error: {data['error']}")
                        continue

                    telemetry_packet = {
                        "device_id": data.get("device_id", data.get("id", 0)),
                        "temp_c":    data.get("temp_c", data.get("temp", 0)),
                        "humidity":  data.get("humidity", data.get("hum", 0)),
                        "lux":       data.get("lux", 0),
                        "pressure":  data.get("pressure_hpa", data.get("press", 0)),
                        "gas_pct":   data.get("gas_pct", data.get("gas", 0)),
                        "timestamp": time.time()
                    }
                    
                    print(f"Packet Prepared: {telemetry_packet}")

                except json.JSONDecodeError:
                    continue

        except (serial.SerialException, OSError, AttributeError) as e:
            print(f"Disconnected or Port Error: {e}")
            print("Attempting to rediscover ports...")
            time.sleep(5)
            choose_port() 
        except KeyboardInterrupt:
            print("\nBridge Stopped.")
            break