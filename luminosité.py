from machine import Pin, I2C
import time

# Initialisation I2C
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=100000)

# Adresse du BH1750 (GY-302)
BH1750_ADDR = 0x23

# Commandes BH1750
POWER_ON = 0x01
RESET = 0x07
CONT_HIGH_RES = 0x10

# Initialisation du capteur
i2c.writeto(BH1750_ADDR, bytes([POWER_ON]))
i2c.writeto(BH1750_ADDR, bytes([RESET]))

def read_lux():
    i2c.writeto(BH1750_ADDR, bytes([CONT_HIGH_RES]))
    time.sleep(0.18)
    data = i2c.readfrom(BH1750_ADDR, 2)
    lux = (data[0] << 8 | data[1]) / 1.2
    return lux

while True:
    lux = read_lux()
    print("Luminosité :", int(lux), "lux")
    time.sleep(1)
