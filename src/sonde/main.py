import time
import json
from machine import Pin, I2C # type: ignore
from sensors import GasSensor, TempHumSensor, LightSensor, PressureSensor, Alarm

# --- Configuration: Hardware Pins ---
PIN_DHT_POWER = 14
PIN_DHT_DATA  = 15
PIN_BUZZER    = 16
PIN_GAS_ADC   = 26
PIN_BMP_POWER = 4
PIN_SDA_BMP   = 2
PIN_SCL_BMP   = 3
PIN_SDA_LUX   = 0
PIN_SCL_LUX   = 1

# --- Initialization: Power Rails ---
dht_power = Pin(PIN_DHT_POWER, Pin.OUT)
bmp_power = Pin(PIN_BMP_POWER, Pin.OUT)

dht_power.value(1)
bmp_power.value(1)
time.sleep(2)  # Sensor stabilization delay

# --- Initialization: Peripherals ---
buzzer = Alarm(PIN_BUZZER)
i2c_lux = I2C(0, scl=Pin(PIN_SCL_LUX), sda=Pin(PIN_SDA_LUX), freq=400000)
i2c_pres = I2C(1, scl=Pin(PIN_SCL_BMP), sda=Pin(PIN_SDA_BMP), freq=400000)

# --- Initialization: Sensor Objects ---
gas_sensor = GasSensor(PIN_GAS_ADC)
dht_sensor = TempHumSensor(PIN_DHT_DATA)
lux_sensor = LightSensor(i2c_lux)
bmp_sensor = PressureSensor(i2c_pres)

# Calibration sequence
gas_sensor.calibrate()

print("System Initialized. Starting Telemetry...")

while True:
    try:
        # 1. Data Acquisition
        raw_gas, gas_pct = gas_sensor.read()
        temp, hum = dht_sensor.read()
        lux = lux_sensor.read()
        pressure = bmp_sensor.read()
        
        # 2. Data Normalization
        payload = {
            "gas_pct": round(gas_pct, 2),
            "temp_c": temp if temp is not None else 0.0,
            "humidity": hum if hum is not None else 0.0,
            "lux": lux if lux != -1 else 0,
            "pressure_hpa": pressure if pressure != -1 else 0.0,
            "timestamp_ms": time.ticks_ms()
        }

        # 3. Output for Serial Bridge (JSON only)
        # We suppress extra text to prevent parsing errors in bridge.py
        print(json.dumps(payload))

        # 4. Safety Logic
        if gas_pct > 30.0:
            buzzer.alert()
        elif temp is not None and temp > 35.0:
            buzzer.beep(0.5)

    except Exception as e:
        # Log error to stderr if supported, or print clear error message
        print(json.dumps({"error": str(e)}))

    time.sleep(5)
