import time
import json
import network

# Correction 1 : Gérer correctement l'importation de urequests
try:
    import urequests as requests
except ImportError:
    import requests

from machine import Pin, I2C # type: ignore
from sensors import GasSensor, TempHumSensor, LightSensor, PressureSensor, Alarm

# --- Configuration: Station & Réseau ---
DEVICE_ID = 1  # 1 pour la station 1, 2 pour la station 2
WIFI_SSID = "NOM_DE_TON_WIFI" # <-- À MODIFIER IMPÉRATIVEMENT
WIFI_PASSWORD = "MOT_DE_PASSE_WIFI" # <-- À MODIFIER IMPÉRATIVEMENT
API_URL = "http://192.168.X.X:5000/api/data"  # <-- L'URL que Jan va te donner

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
PIN_BUZZER_POWER = 8

# --- Connexion Wi-Fi ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"Connexion au réseau Wi-Fi '{WIFI_SSID}'...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Correction 3 : Empêcher le code de rester bloqué ici à l'infini
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            
    if wlan.isconnected():
        print("Wi-Fi Connecté! IP:", wlan.ifconfig()[0])
    else:
        print("ATTENTION: Impossible de se connecter au Wi-Fi. Le programme continue sans réseau.")

# --- Initialization: Power Rails ---
dht_power = Pin(PIN_DHT_POWER, Pin.OUT)
bmp_power = Pin(PIN_BMP_POWER, Pin.OUT)
buzzer_power = Pin(PIN_BUZZER_POWER, Pin.OUT) 
dht_power.value(1)
bmp_power.value(1)
buzzer_power.value(1)
time.sleep(2)  # Sensor stabilization delay

# --- Initialization: Peripherals ---
buzzer = Alarm(PIN_BUZZER)

buzzer.beep(0.5)  # Bip immédiat pour confirmer que le courant passe et le script se lance !

i2c_lux = I2C(0, scl=Pin(PIN_SCL_LUX), sda=Pin(PIN_SDA_LUX), freq=400000)
i2c_pres = I2C(1, scl=Pin(PIN_SCL_BMP), sda=Pin(PIN_SDA_BMP), freq=400000)

# --- Initialization: Sensor Objects ---
gas_sensor = GasSensor(PIN_GAS_ADC)
dht_sensor = TempHumSensor(PIN_DHT_DATA)
lux_sensor = LightSensor(i2c_lux)
bmp_sensor = PressureSensor(i2c_pres)

# Démarrage
gas_sensor.calibrate()
connect_wifi()
print("System Initialized. Starting Telemetry...")

while True:
    try:
        # 1. Data Acquisition
        raw_gas, gas_pct = gas_sensor.read()
        temp, hum = dht_sensor.read()
        lux = lux_sensor.read()
        pressure = bmp_sensor.read()
        
        # 2. Data Normalization (Format Dictionnaire pour API)
        telemetry_packet = {
            "device_id": DEVICE_ID,
            "temp_c": temp if temp is not None else 0.0,
            "humidity": hum if hum is not None else 0.0,
            "lux": lux if lux != -1 else 0,
            "pressure": pressure if pressure != -1 else 0.0,
            "gas_pct": round(gas_pct, 2),
            "timestamp": time.time()
        }

        # 3. Envoi des données vers l'URL via Wi-Fi
        try:
            # Correction 2 : Rendre la requête compatible avec toutes les versions de MicroPython
            headers = {'Content-Type': 'application/json'}
            response = requests.post(API_URL, data=json.dumps(telemetry_packet), headers=headers)
            print(f"Envoyé avec succès (Code: {response.status_code})")
            response.close() # Très important pour ne pas saturer la mémoire du Pico
        except Exception as e:
            print(f"Erreur d'envoi Wi-Fi : {str(e)}")

        # 4. Safety Logic
        if gas_pct > 30.0:
            buzzer.alert()
        elif temp is not None and temp > 35.0:
            buzzer.beep(0.5)

    except Exception as e:
        print(json.dumps({"error": str(e)}))

    # 5. Attente stricte de 2 secondes
    time.sleep(2)
