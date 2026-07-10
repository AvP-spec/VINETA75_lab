"""
loopback_test.py
=================
Testet NUR den USB-RS232-Konverter + Kabel + Treiber, ganz ohne den
Lock-In. Vor dem Ausführen: Pin 2 (TXD) und Pin 3 (RXD) am DB9-Stecker
(der sonst zum Lock-In geht) mit einem Draht/einer Büroklammer brücken.
"""

import time
import serial

PORT = "/dev/ttyUSB0"
BAUD = 9600

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(0.2)
ser.reset_input_buffer()

test_bytes = b"Hallo\r\n"
ser.write(test_bytes)
ser.flush()
time.sleep(0.3)

n = ser.in_waiting
print(f"Bytes im Puffer: {n}")
received = ser.read(n) if n else b""
print(f"Empfangen: {received!r}")

if received == test_bytes:
    print("OK: Loopback erfolgreich. Konverter/Kabel/Treiber sind in Ordnung.")
elif received:
    print("Es kam etwas zurück, aber nicht identisch. Ungewöhnlich - Kabel/Kontakt prüfen.")
else:
    print("Nichts zurückbekommen. Problem liegt beim Konverter, Kabel bis zur Brücke, "
          "oder der Brücke selbst (Pin 2/3 falsch erwischt?).")

ser.close()