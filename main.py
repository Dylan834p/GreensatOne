import time
from sensors import GasSensor, GreenSatLogger

# 1. On initialise le capteur de gaz sur le Pin GP26 (AO)
mq2 = GasSensor(pin_adc=26)

# 2. On initialise l'enregistreur SD
logger = GreenSatLogger()

print("--- Démarrage GreenSat : Test MQ-2 ---")
print("Soufflez un peu de gaz (briquet sans flamme) vers le capteur pour tester.")

# 3. Boucle principale
while True:
    try:
        # Lecture du capteur
        valeur_brute, pourcentage = mq2.read()
        
        # Affichage à l'écran
        print(f"Gaz détecté : {valeur_brute} / 65535 ({pourcentage:.1f}%)")
        
        # Enregistrement sur la SD
        logger.save(valeur_brute, pourcentage)
        
    except Exception as e:
        print("Erreur dans la boucle :", e)

    # Pause de 2 secondes entre chaque mesure
    time.sleep(2)