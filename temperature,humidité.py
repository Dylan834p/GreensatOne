from machine import Pin
import dht
import time

# Capteur connecté sur GP15
dht11 = dht.DHT11(Pin(15))

while True:
    try:
        dht11.measure()
        temperature = dht11.temperature()
        humidity = dht11.humidity()

        print("Température :", temperature, "°C")
        print("Humidité :", humidity, "%")
        print("---------------------")

    except OSError as e:
        print("Erreur de lecture du capteur")

    time.sleep(2)