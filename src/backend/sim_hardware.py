import json
import random
import time

class FakeSerial:
    def __init__(self, port=None, baudrate=None, timeout=None):
        self.port = port
        self.in_waiting = 1  # Always "has data" for the loop
        self.start_time = time.time()

    def readline(self):
        # Change 'x' seconds here to control speed
        time.sleep(2) 
        
        data = {
            "pressure_hpa": round(random.uniform(980, 1010), 1),
            "timestamp_ms": int((time.time() - self.start_time) * 1000),
            "gas_pct": round(random.uniform(1.0, 5.0), 2),
            "temp_c": random.randint(20, 25),
            "humidity": random.randint(30, 50),
            "lux": round(random.uniform(200, 500), 1)
        }
        # Return as bytes to match real serial behavior
        return (json.dumps(data) + "\n").encode("utf-8")

    def close(self):
        pass