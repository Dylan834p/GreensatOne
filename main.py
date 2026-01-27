import time
import network
import urequests
import json
from machine import Pin, I2C
from sensors import GasSensor, TempHumSensor, LightSensor, PressureSensor, Alarm

# --- CONFIGURATION (A CHANGER !) ---
WIFI_SSID = "azerty"       # <--- TON WIFI
WIFI_PASS = "1234"        # <--- TON MOT DE PASSE
SERVER_IP = "10.10.16.7"          # <--- L'IP DE TON PC (Vérifie avec ipconfig)
PICO_ID   = "GreenSat_1"          # <--- Change en "GreenSat_2" pour l'autre !

URL = f"http://{SERVER_IP}:5000/api/upload"

# --- PINS (Ton câblage habituel) ---
p1 = Pin(14, Pin.OUT); p1.value(1)
p2 = Pin(4, Pin.OUT); p2.value(1)
time.sleep(2)

buzzer = Alarm(16)
i2c_lux = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
i2c_pres = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)

mq2 = GasSensor(26)
mq135 = GasSensor(28)
dht11 = TempHumSensor(15)
lux = LightSensor(i2c_lux)
bmp = PressureSensor(i2c_pres)

# --- CONNEXION WIFI ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)

print(f"📡 Connexion Wifi vers {WIFI_SSID}...")
while not wlan.isconnected():
    time.sleep(1)
    print(".")
    
print(f"✅ CONNECTÉ ! IP: {wlan.ifconfig()[0]}")
buzzer.beep(0.2)
mq2.calibrer()
mq135.calibrer()

while True:
    try:
        # Lecture
        _, g_pct = mq2.read()
        _, a_pct = mq135.read()
        t, h = dht11.read()
        l_val = lux.read()
        p_val = bmp.read()
        
        # Données
        data = {
            "id": PICO_ID,
            "gaz_pct": round(g_pct, 2),
            "air_pct": round(a_pct, 2),
            "temp": t if t else 0,
            "hum": h if h else 0,
            "lux": l_val if l_val != -1 else 0,
            "press": p_val if p_val != -1 else 0
        }

        # Envoi au Serveur (app.py)
        print(f"📤 Envoi de {PICO_ID}...", end="")
        res = urequests.post(URL, json=data)
        res.close()
        print(" OK")

        # Alerte locale
        if g_pct > 30 or a_pct > 35: buzzer.alert()

    except Exception as e:
        print(f"❌ Erreur: {e}")
        # Si Wifi perdu, on tente de reconnecter
        if not wlan.isconnected(): wlan.connect(WIFI_SSID, WIFI_PASS)

    time.sleep(2)