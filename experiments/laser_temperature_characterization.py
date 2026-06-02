"""
laser_temperature_characterization.py
=========================
Charakterisierung des Master-Lasers:
Piezo-Scan für jeden Temperaturwert im angegebenen Bereich. 

Für jede Temperatur wird ein vollständiger Piezo-Scan durchgeführt.
Ergebnis: Wellenlänge vs. Piezo-Spannung für alle Temperaturen, farbcodiert nach Temperatur.
"""

# ----------------------------------------------------------------
# Imports
# ----------------------------------------------------------------
import os
import sys
import time
import getpass
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm

# Projektpfad einbinden
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from managers.lif import LIFManager
import utils.file_utils as fu
import utils.lif_plots as lp

from utils.terminal_styler import TerminalColours

tc = TerminalColours()

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

print(f"\n{tc.BLUE}============ laser_temperature_characterization.py ============{tc.RESET}\n \n")

# ----------------------------------------------------------------
# Konfiguration – hier anpassen
# ----------------------------------------------------------------
BASE_PATH      = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")
FILE_BASE_NAME = "laser_temperature_characterization"
COMMENT        = "Piezo-Scan für Temperaturen 10 - 20 °C in 5 °C Schritten"

LASER_WARMUP_S   = 20       # Wartezeit nach laser_on()
TEMP_MIN_C       = 10.0     # °C
CURRENT_MAX_MA   = 20.0     # °C
TEMP_STEP_C      = 5.0      # °C
TEMP_SETTLE_S    = 2.0      # Wartezeit nach Stromänderung          <-- muss noch angepasst werden
N_WLM            = 2        # Wellenlängenmessungen pro Piezo-Punkt
V_STEP           = 13.5     # Piezo-Schrittweite [V]
ZIGZAG           = False

# ----------------------------------------------------------------
# Stromliste aufbauen
# ----------------------------------------------------------------
n_steps    = int(round((CURRENT_MAX_MA - TEMP_MIN_C) / TEMP_STEP_C)) + 1
i_list_mA  = [round(TEMP_MIN_C + i * TEMP_STEP_C, 3)
               for i in range(n_steps)]

print(f"Temperaturliste: {i_list_mA} mA")
print(f"Anzahl Scans: {len(i_list_mA)}\n")

# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = "LIF/laser_temperature_characterization",         # manuelle Eingabe
)
file_path_csv  = fu.make_data_file_name(
    data_dir  = data_dir,
    base_name = FILE_BASE_NAME,
    extension = "csv",
)
plots_dir = fu.make_data_dir(
    base_path = BASE_PATH, 
    base_name = "LIF/laser_temperature_characterization",   # manuelle Eingabe
)
file_path_plot = fu.make_data_file_name(
    data_dir  = data_dir,
    base_name = FILE_BASE_NAME,
    extension = "png",
)

print(f"Daten werden gespeichert in:\n  {data_dir}")
print(f"CSV:  {file_path_csv.name}")
print(f"Plot: {file_path_plot.name}\n")

# ----------------------------------------------------------------
# Messung
# ----------------------------------------------------------------
r_man  = LIFManager()
df_all = None

try:
    r_man.laser_on()
    print(f"    Waiting {LASER_WARMUP_S} sec for laser warmup")
    time.sleep(LASER_WARMUP_S)

    scan_start_time = datetime.now()
    all_scans = []

    for i_idx, i_mA in enumerate(i_list_mA):
        print(f"\n{'─'*50}")
        print(f"  Scan {i_idx+1}/{len(i_list_mA)}: I = {i_mA:.1f} mA")
        print(f"{'─'*50}")

        # Temperatur setzen und warten
        r_man.master_diode.set_temperature(value=i_mA, unit="°C", silent=True)
        
    
        time.sleep(TEMP_SETTLE_S)

        # Piezo-Scan – kein Plot pro Scan, nur DataFrame
        df_scan = r_man.scan_piezo(
            v_step    = V_STEP,
            v_unit    = "[V]",
            n_wlm     = N_WLM,
            zigzag    = ZIGZAG,
            silent    = True,
            plot      = False,    # kein Einzel-Plot
            save_path = None,
        )

        # Strom als Spalte ergänzen
        df_scan['current_mA'] = i_mA
        all_scans.append(df_scan)

    # alle Scans zusammenführen
    df_all = pd.concat(all_scans, ignore_index=True)
    print(f"\n{'='*50}")
    print(f"  Alle Scans abgeschlossen.")
    print(f"  Gesamt: {len(df_all)} Messpunkte")
    print(f"{'='*50}\n")

    # Metadaten
    meta = {
        "operator":          getpass.getuser(),
        "script":            Path(__file__).name,
        "scan_start_time":   str(scan_start_time),
        "comment":           COMMENT,
        "current_min_mA":    CURRENT_MIN_MA,
        "current_max_mA":    CURRENT_MAX_MA,
        "current_step_mA":   CURRENT_STEP_MA,
        "current_settle_s":  CURRENT_SETTLE_S,
        "n_wlm":             N_WLM,
        "v_step_V":          V_STEP,
        "zigzag":            ZIGZAG,
        "laser_warmup_s":    LASER_WARMUP_S,
        "n_scans":           len(i_list_mA),
        "n_points_total":    len(df_all),
    }
    meta.update(r_man.get_device_state_meta())

finally:
    r_man.master_diode.set_current(
        CURRENT_MIN_MA * 1e-3, unit="A", silent=True
    )
    r_man.laser_off()
    r_man.disconnect_all()

# ----------------------------------------------------------------
# Speichern
# ----------------------------------------------------------------


if df_all is not None and not df_all.empty:

    # Plot erstellen
    lp.plot_characterization(df=df_all, CURRENT_STEP_MA=CURRENT_STEP_MA, save_path=str(file_path_plot))

    # DataFrame speichern
    fu.save_dataframe(
        df        = df_all,
        file_path = file_path_csv,
        metadata  = meta,
        sep       = "\t",
        index     = True,
        silent    = False,
    )

else:
    print("WARNUNG: Kein DataFrame – Messung leer oder abgebrochen")