import time
from machine import Pin, I2C
from sensors import GasSensor, TempHumSensor, LightSensor, PressureSensor, GreenSatLogger, Alarm

# --- PINS ---
PIN_DHT_POWER = 14  # Alim DHT11
PIN_DHT_DATA  = 15
PIN_BUZZER    = 16  # Alarme (VSYS)
PIN_GAZ       = 26  # MQ-2 (VBUS)

PIN_BMP_POWER = 4   # Alim BMP280 (NOUVEAU)
PIN_SDA_BMP   = 2   # I2C1 SDA
PIN_SCL_BMP   = 3   # I2C1 SCL

PIN_SDA_LUX   = 0   # I2C0 SDA (Light)
PIN_SCL_LUX   = 1   # I2C0 SCL (Light)

# --- 1. ACTIVATION DES ALIMENTATIONS LOGICIELLES ---
print("🔌 Activation des alims capteurs...")
# Pour le DHT11
p1 = Pin(PIN_DHT_POWER, Pin.OUT)
p1.value(1)
# Pour le BMP280 (NOUVEAU)
p2 = Pin(PIN_BMP_POWER, Pin.OUT)
p2.value(1)
time.sleep(2) # Pause reveil

# --- 2. SETUP ---
print("🚀 Démarrage GreenSat...")
buzzer = Alarm(PIN_BUZZER)
buzzer.beep(0.1)

# I2C pour la LUMIÈRE (Bus 0)
i2c_lux = I2C(0, scl=Pin(PIN_SCL_LUX), sda=Pin(PIN_SDA_LUX), freq=400000)
# I2C pour la PRESSION (Bus 1 - NOUVEAU)
i2c_pres = I2C(1, scl=Pin(PIN_SCL_BMP), sda=Pin(PIN_SDA_BMP), freq=400000)

mq2 = GasSensor(PIN_GAZ)
dht11 = TempHumSensor(PIN_DHT_DATA)
lux_sensor = LightSensor(i2c_lux)
bmp280 = PressureSensor(i2c_pres) # Adresse auto 0x76
logger = GreenSatLogger()

print("⏱️ Calibrage Gaz...")
mq2.calibrer()

print("\n--- STATION MÉTÉO ULTIME ---")

while True:
    try:
        # LECTURES
        raw_gaz, pct_gaz = mq2.read()
        temp, hum = dht11.read()
        lux = lux_sensor.read()
        press = bmp280.read()
        
        # SAUVEGARDE
        t = logger.save(pct_gaz, temp, hum, lux, press)
        
        # FORMULATION MESSAGES
        if temp is None: t_str = "❌ Temp"
        else: t_str = f"{temp}°C | {hum}%"
            
        if lux == -1: l_str = "❌ Lux"
        else: l_str = f"{lux} Lx"

        if press == -1 or press == 0: p_str = "❌ Pres"
        else: p_str = f"{press} hPa"

        # AFFICHAGE
        print(f"[{t:.0f}s] {t_str} | {l_str} | ☁️ {p_str} || Gaz: {pct_gaz:.1f}%")

        # SECURITÉ
        if pct_gaz > 30:
            print("⚠️ ALERTE GAZ !")
            buzzer.alert()
        elif temp is not None and temp > 35:
            print("⚠️ ALERTE CHALEUR !")
            buzzer.beep(0.5)

    except Exception as e:
        print("Erreur:", e)

    time.sleep(2)