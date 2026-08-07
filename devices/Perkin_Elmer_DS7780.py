"""
devices/lock_in_amplifier.py
=============================

Treiber für den Perkin Elmer / SIGNAL RECOVERY DSP7780 (baugleich Model 7280)
Lock-In Amplifier, angebunden über einen USB-zu-RS232-Konverter.

Folgt der BaseDevice-Architektur des Projekts (pyvisa ResourceManager,
CONNECTION_SETTINGS, get_COM_port()/connect()/after_connect()-Muster).

-------------------------------------------------------------------------
Einmalige Einstellungen AM GERÄT (Menü Configuration -> Communications ->
RS232 Settings), bevor das hier funktioniert:
-------------------------------------------------------------------------
  BAUD RATE   : 9600  (siehe CONNECTION_SETTINGS unten - muss übereinstimmen)
  DATA BITS   : 8 + no parity
  ECHO        : OFF    (sonst muss jede Antwort doppelt gelesen werden)
  PROMPT      : OFF    (sonst hängt "*"/"?" an jeder Antwort)
"""

import time
import pyvisa
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from devices.base_device import BaseDevice


# HWID des USB<->RS232-Konverters. Über lia.print_com_info() ermitteln und
# hier eintragen (Format wie von BaseDevice erzeugt: "VID:PID = XXXX:YYYY").
HWID = "VID:PID:SER = 1659:8963:None"  # für den verwendeten Converter


class LockInError(Exception):
    """Wird ausgelöst, wenn das Gerät einen Fehler meldet oder nicht antwortet."""


class LockInAmplifier(BaseDevice):

    # RS232-Verbindungsparameter für pyvisa (ASRL-Resource).
    # Muss zu den Einstellungen im RS232 Settings Menü des Geräts passen!
    CONNECTION_SETTINGS = {
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": pyvisa.constants.Parity.none,
        "stop_bits": pyvisa.constants.StopBits.one,
        "write_termination": "\r",
        "read_termination": "\r",
        "timeout": 2000,  # ms
    }

    def __init__(self):
        super().__init__()
        self.name = "LockInAmplifier (DSP7780)"
        self.hwid = HWID
        self.get_COM_port()  # ermittelt self.port bereits hier, wie bei den
                              # anderen Devices - LIFManager._connect_device()
                              # ruft später nur noch .connect() auf

    # -------------------------------------------------------------
    # Verbindungsaufbau
    # -------------------------------------------------------------

    def get_COM_port(self, silent=True):
        """Sucht den Port über die HWID + aktive Identifikation per 'ID'
        Befehl (Antwort muss '7280' sein). settle_time=0, da das Gerät
        beim Öffnen des Ports keinen Reset durchführt (anders als z.B.
        ein Arduino)."""
        return self.get_COM_port_by_idn(
            idn_expected="7280",
            idn_command="ID",
            settle_time=0,
            silent=silent,
        )

    def after_connect(self, silent=True):
        """Wird von BaseDevice.connect() automatisch nach dem Öffnen der
        Verbindung aufgerufen. Prüft die Geräte-ID und setzt eine
        definierte Zeitkonstante."""
        try:
            idn = self.identify()
        except Exception as e:
            print(f"{self.RED}[{self.name}] after_connect: Identifikation fehlgeschlagen: {e}{self.RESET}")
            return False

        if idn != "7280":
            print(f"{self.RED}[{self.name}] Unerwartete Geräte-ID: '{idn}' (erwartet '7280'){self.RESET}")
            return False

        if not silent:
            print(f"{self.GREEN}[{self.name}] Geräte-ID bestätigt: {idn}{self.RESET}")

        return True

    # -------------------------------------------------------------
    # Low-Level Kommunikation
    # -------------------------------------------------------------

    def _query(self, command):
        """Sendet einen Befehl und liest die Antwort. Filtert ein Echo
        heraus, falls ECHO am Gerät (entgegen der Empfehlung) noch
        eingeschaltet ist, sowie ein evtl. angehängtes Prompt-Zeichen."""
        if self.connection is None:
            raise LockInError(f"{self.name} ist nicht verbunden.")

        self.connection.write(command)
        line = self.connection.read().strip()

        # Falls ECHO am Gerät eingeschaltet ist, kommt zuerst der
        # gesendete Befehl zurück, bevor die eigentliche Antwort folgt.
        if line.strip().upper() == command.strip().upper():
            line = self.connection.read().strip()

        # Falls PROMPT am Gerät eingeschaltet ist, hängt "*" oder "?" an.
        if line.endswith("?") or line.endswith("*"):
            line = line[:-1].strip()

        if line == "":
            raise LockInError(f"Leere Antwort auf Befehl '{command}'.")

        return line

    def _write(self, command):
        if self.connection is None:
            raise LockInError(f"{self.name} ist nicht verbunden.")
        self.connection.write(command)
        # auch bei set-Befehlen ohne Datenantwort kann ein Echo/Prompt
        # zurückkommen - das lesen wir hier auf, um es nicht in der
        # nächsten Abfrage fälschlich als Antwort zu interpretieren.
        try:
            self.connection.read()
        except pyvisa.errors.VisaIOError:
            pass  # kein Echo/Prompt aktiv -> Timeout ist hier ok

    @staticmethod
    def _split_two_values(response):
        parts = [p for p in response.replace(",", " ").split() if p]
        if len(parts) != 2:
            raise LockInError(f"Unerwartetes Antwortformat: '{response}'")
        return parts

    # -------------------------------------------------------------
    # Öffentliche Befehle (siehe Handbuch Kap. 6.4)
    # -------------------------------------------------------------

    def identify(self):
        """ID-Befehl: Gerät antwortet mit '7280'."""
        return self._query("ID")

    def set_time_constant(self, tc_code):
        """TC [n]: Zeitkonstante setzen (n gemäß Handbuch Kap. 6.4.03,
        z.B. n=16 entspricht 200 ms)."""
        self._write(f"TC {tc_code}")

    def read_time_constant_s(self):
        """TC.: liest die aktuell eingestellte Zeitkonstante in Sekunden."""
        return float(self._query("TC."))
    
    def read_status_byte(self):
        """ST: liest das Status-Byte (Kap. 6.3.13 im Handbuch) und gibt die
        relevanten Fehlerbits als dict zurück. Wichtig für Datenqualität:
        bit 3 = Referenz "unlocked", bit 4 = Overload (Signal übersteuert -
        Messwert an diesem Punkt ist dann nicht vertrauenswürdig)."""
        status = int(self._query("ST"))
        return {
            "invalid_command":  bool(status & (1 << 1)),
            "parameter_error":  bool(status & (1 << 2)),
            "reference_unlock": bool(status & (1 << 3)),
            "overload":         bool(status & (1 << 4)),
        }

    def read_xy(self):
        """XY.: liefert (X, Y) in Volt als Float-Tupel."""
        response = self._query("XY.")
        x_str, y_str = self._split_two_values(response)
        return float(x_str), float(y_str)

    def read_mag_phase(self):
        """MP.: liefert (Magnitude [V], Phase [deg]) als Float-Tupel."""
        response = self._query("MP.")
        m_str, p_str = self._split_two_values(response)
        return float(m_str), float(p_str)

    def read_signal(self, silent=True, device_read_time=False, check_status=True):
        """
        Einheitliche Ausleseschnittstelle, kompatibel mit
        LIFManager.read_state() (wird dort automatisch mit 'lia_' geprefixt).
 
        Liefert X, Y, Magnitude und Phase in einem Aufruf (zwei Geräte-
        Anfragen, XY. und MP.), sowie optional Overload-/Unlock-Flags -
        wichtig, um übersteuerte oder unverlässliche Messpunkte im
        Nachhinein leicht herausfiltern zu können (z.B. df[~df['lia_overload']]).
        """
        t_start = time.perf_counter()
 
        try:
            x_v, y_v = self.read_xy()
            mag_v, phase_deg = self.read_mag_phase()
            data = {
                "X_V": x_v,
                "Y_V": y_v,
                "R_V": mag_v,
                "theta_deg": phase_deg,
            }
            if check_status:
                status = self.read_status_byte()
                data["overload"] = status["overload"]
                data["ref_unlock"] = status["reference_unlock"]
        except Exception as e:
            if not silent:
                print(f"{self.RED}[{self.name}] read_signal Fehler: {e}{self.RESET}")
            return {"error": str(e)}
 
        if device_read_time:
            data["read_start_s"] = t_start
            data["read_duration_s"] = time.perf_counter() - t_start
 
        if not silent:
            print(f"[{self.name}] {data}")
 
        return data



if __name__ == "__main__":
    lia = LockInAmplifier()
    lia.print_com_info()
    lia.get_COM_port(silent=False).connect(silent=False)

    if lia.connection is not None:
        print(lia.read_signal(silent=False, device_read_time=True))
        lia.disconnect()
