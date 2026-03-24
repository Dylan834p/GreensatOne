import time
import json
import network
import requests
from machine import Pin, I2C
from sensors import GasSensor, TempHumSensor, LightSensor, PressureSensor, Alarm

# --- Configuration ---
DEVICE_ID = 1
WIFI_SSID = "QF"
WIFI_PASSWORD = "Qu!zzFact0ry"
API_URL = "http://192.168.0.102:5000/upload/raw"

# Pins
PIN_DHT_POWER = 14
PIN_DHT_DATA  = 15
PIN_BUZZER    = 16
PIN_GAS_ADC   = 26
PIN_BMP_POWER = 4
PIN_SDA_BMP   = 2
PIN_SCL_BMP   = 3
PIN_SDA_LUX   = 0
PIN_SCL_LUX   = 1
PIN_BUZZER_POWER = 8
wlan = None

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0xa11140)
    if not wlan.isconnected():
        print(f"Connecting to '{WIFI_SSID}'...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            
    if wlan.isconnected():
        print("Connected! IP:", wlan.ifconfig()[0])
    else:
        print("WiFi connection failed. Continuing in offline mode.")

# Power Rails Initialization
dht_power = Pin(PIN_DHT_POWER, Pin.OUT)
bmp_power = Pin(PIN_BMP_POWER, Pin.OUT)
buzzer_power = Pin(PIN_BUZZER_POWER, Pin.OUT) 
dht_power.value(1)
bmp_power.value(1)
buzzer_power.value(1)
time.sleep(2) 

# Peripherals & Sensors
buzzer = Alarm(PIN_BUZZER)
buzzer.beep(0.5) 

i2c_lux = I2C(0, scl=Pin(PIN_SCL_LUX), sda=Pin(PIN_SDA_LUX), freq=400000)
i2c_pres = I2C(1, scl=Pin(PIN_SCL_BMP), sda=Pin(PIN_SDA_BMP), freq=400000)

gas_sensor = GasSensor(PIN_GAS_ADC)
dht_sensor = TempHumSensor(PIN_DHT_DATA)
lux_sensor = LightSensor(i2c_lux)
bmp_sensor = PressureSensor(i2c_pres)

gas_sensor.calibrate()
connect_wifi()
print("System Initialized.")

while True:
    try:
        # 1. Data Acquisition
        raw_gas, gas_pct = gas_sensor.read()
        temp, hum = dht_sensor.read()
        lux = lux_sensor.read()
        pressure = bmp_sensor.read()
        
        # 2. Prepare Data
        telemetry_packet = {
            "device_id": DEVICE_ID,
            "temp_c": temp if temp is not None else 0.0,
            "humidity": hum if hum is not None else 0.0,
            "lux": lux if lux != -1 else 0,
            "pressure": pressure if pressure != -1 else 0.0,
            "gas_pct": round(gas_pct, 2),
            "timestamp": time.time()
        }

        # 3. Transmission
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(API_URL, data=json.dumps(telemetry_packet), headers=headers, timeout=5)
            print(f"Sent (Status: {response.status_code})")
            response.close() 
        except Exception as e:
            print(f"WiFi Send Error: {e}")

        # 4. Safety Logic
        if gas_pct > 30.0:
            buzzer.alert()
        elif temp is not None and temp > 35.0:
            buzzer.beep(0.5)

    except Exception as e:
        print(f"System Error: {e}")

    time.sleep(1)