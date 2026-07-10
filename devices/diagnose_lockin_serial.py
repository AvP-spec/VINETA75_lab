"""
diagnose_lockin_serial.py
==========================
Low-Level-Test der RS232-Verbindung zum DSP7780 - unabhängig von
BaseDevice/get_COM_port_by_idn(), um Verkabelungs-/Settings-Probleme
von Software-Problemen zu unterscheiden.

Passe PORT unten an (z.B. "/dev/ttyUSB0").
"""

import time
import pyvisa

PORT = "ASRL/dev/ttyUSB0::INSTR" # für Linux

# Hier verschiedene Kombinationen durchprobieren, falls die erste nicht
# funktioniert (z.B. falls DATA BITS am Gerät noch auf Werks-Default steht)
SETTINGS_CANDIDATES = [
    {"baud_rate": 9600, "data_bits": 8, "parity": pyvisa.constants.Parity.none,
     "stop_bits": pyvisa.constants.StopBits.one},
]

rm = pyvisa.ResourceManager()
print(f"Verfügbare Resourcen: {rm.list_resources()}")

for settings in SETTINGS_CANDIDATES:
    print("\n" + "=" * 60)
    print(f"Teste Einstellungen: {settings}")
    try:
        inst = rm.open_resource(
            PORT,
            timeout=3000,
            write_termination="",   # wir hängen \r manuell an, um genau zu sehen was passiert
            read_termination="",    # kein Auto-Split, wir lesen roh
            **settings,
        )
    except Exception as e:
        print(f"  Öffnen fehlgeschlagen: {e}")
        continue

    try:
        inst.write_raw(b"ID\r")
        print("  Gesendet: b'ID\\r' - warte auf Antwort (bis zu 3s)...")
        time.sleep(0.5)
        n_bytes = inst.bytes_in_buffer
        print(f"  Bytes im Empfangspuffer: {n_bytes}")
        if n_bytes:
            raw = inst.read_bytes(n_bytes)
            print(f"  Rohantwort: {raw!r}")
            print(f"  Als ASCII:  {raw.decode('ascii', errors='replace')!r}")
        else:
            print("  -> KEINE Antwort erhalten (0 Bytes). "
                  "Verkabelung oder Baudrate/Parity vermutlich falsch.")
    except Exception as e:
        print(f"  Fehler beim Schreiben/Lesen: {e}")
    finally:
        inst.close()

print("\n" + "=" * 60)
print("Fertig. Bei welcher Einstellung kam eine Rohantwort zurück?")
print("Diese Einstellung dann 1:1 in CONNECTION_SETTINGS in")
print("lock_in_amplifier.py übernehmen.")