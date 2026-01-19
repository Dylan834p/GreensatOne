import serial
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
PORT_USB = 'COM7'   # Vérifie si c'est toujours COM7 !
BAUDRATE = 115200

# Le fichier sera créé dans le même dossier que ce script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, "data.json")

print(f"📂 Le fichier JSON sera ici : {JSON_FILE}")

try:
    ser = serial.Serial(PORT_USB, BAUDRATE, timeout=1)
    print(f"🔌 Connecté au Pico sur {PORT_USB}. En attente...")
    
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            try:
                if line.startswith('{'):
                    data = json.loads(line)
                    if "error" not in data:
                        # Ajout de l'heure
                        data["date_time"] = datetime.now().strftime("%H:%M:%S")
                        
                        # Écriture dans le fichier
                        with open(JSON_FILE, 'w') as f:
                            json.dump(data, f)
                        
                        print(f"[OK] Reçu : {data}")
            except:
                pass
except Exception as e:
    print(f"❌ Erreur : {e}")