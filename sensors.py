from machine import Pin, SPI, ADC
import sdcard
import os
import time

class GasSensor:
    """Gère le capteur MQ-2"""
    def __init__(self, pin_adc):
        # On configure le pin en mode ADC (Lecture de tension)
        self.sensor = ADC(Pin(pin_adc))

    def read(self):
        # Lit une valeur brute entre 0 et 65535
        raw_value = self.sensor.read_u16()
        # On convertit approximativement en pourcentage (juste pour l'affichage)
        # 65535 est le max (3.3V), 0 est le min (0V)
        percentage = (raw_value / 65535) * 100
        return raw_value, percentage

class GreenSatLogger:
    """Gère l'enregistrement sur la Carte SD"""
    def __init__(self):
        # Configuration SD (SPI0 sur GP 2,3,4,5)
        self.spi = SPI(0, baudrate=1_000_000, sck=Pin(2), mosi=Pin(3), miso=Pin(4))
        self.cs = Pin(5, Pin.OUT)
        self.file = "/sd/mq2_data.csv"
        self.start_time = time.time()
        self.setup_sd()

    def setup_sd(self):
        try:
            sd = sdcard.SDCard(self.spi, self.cs)
            os.mount(sd, "/sd")
            # Si le fichier n'existe pas, on met l'en-tête
            if "mq2_data.csv" not in os.listdir("/sd"):
                with open(self.file, "w") as f:
                    f.write("temps_s,gaz_raw,gaz_pct\n")
            print("Carte SD prête pour le MQ-2 !")
        except Exception as e:
            print("Erreur SD (vérifier branchements) :", e)

    def save(self, raw, pct):
        duree = time.time() - self.start_time
        try:
            with open(self.file, "a") as f:
                f.write("{},{},{:.2f}\n".format(duree, raw, pct))
            print(f"Enregistré: Raw={raw} | {pct:.1f}%")
        except Exception as e:
            print("Erreur écriture :", e)