from machine import UART, Pin
import time

# UART GPS Initialization
# Using UART 1, common for Raspberry Pi Pico or ESP32
gps = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))

def convert(coord, direction):
    """
    Converts NMEA coordinate format (DDMM.MMMM) to Decimal Degrees.
    """
    if coord == "":
        return None
    deg = float(coord[:2])
    minutes = float(coord[2:])
    dec = deg + minutes / 60
    if direction in ["S", "W"]:
        dec = -dec
    return dec

def parse_gps(line):
    """
    Parses a GPGGA sentence to extract Latitude, Longitude, and Altitude.
    """
    parts = line.split(",")

    # $GPGGA is the standard NMEA sentence for fix data
    # parts[6] is the fix quality (0 = no fix)
    if parts[0] == "$GPGGA" and parts[6] != "0":
        lat = convert(parts[2], parts[3])
        lon = convert(parts[4], parts[5])
        alt = parts[9]

        return lat, lon, alt
    return None

print("GPS searching for satellites...")

while True:
    if gps.any():
        line = gps.readline()
        # Print raw data for debugging
        print(line)
        
        try:
            # Decode the byte string from UART
            line = line.decode("utf-8")
            data = parse_gps(line)

            if data:
                lat, lon, alt = data
                print("Latitude :", lat)
                print("Longitude:", lon)
                print("Altitude :", alt, "m")
                print("--------------------")
        except:
            # Handle potential decoding errors from noisy UART signals
            pass

    time.sleep(0.2)