"""
laser_temperature_characterization.py
=========================
Charakterisierung des Amplifier-Lasers:
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

from lif_analysis.lif_plotter import plot_flex, COL_CONFIG

tc = TerminalColours()

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

print(f"\n{tc.BLUE}============ amplifier_temperature_characterization.py ============{tc.RESET}\n \n")

# ----------------------------------------------------------------
# Konfiguration – hier anpassen
# ----------------------------------------------------------------
BASE_PATH      = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")
FILE_BASE_NAME = "amplifier_temperature_characterization"
COMMENT        = "Piezo-Scan für Temperaturen 15 - 25 °C in 5 °C Schritten"

TEMP_MIN_C       = 15.0     # °C min=-5
TEMP_MAX_C       = 25.0     # °C max=30
TEMP_STEP_C      = 5.0      # °C
N_WLM            = 3        # Wellenlängenmessungen pro Piezo-Punkt
V_STEP           = 13.5     # Piezo-Schrittweite [V]
ZIGZAG           = False
HYSTERESIS       = False

"""
"limits": {"max":30.000, "min": -5.000, "unit": "[C]", "resolution": 1E-3},
            "unit_map": {"C": 1, "[C]": 1, },
"""

# ----------------------------------------------------------------
# Stromliste aufbauen
# ----------------------------------------------------------------
n_steps    = int(round((TEMP_MAX_C - TEMP_MIN_C) / TEMP_STEP_C)) + 1
i_list_C  = [round(TEMP_MIN_C + i * TEMP_STEP_C, 3)
               for i in range(n_steps)]

print(f"Temperaturliste: {i_list_C} °C")
print(f"Anzahl Scans: {len(i_list_C)}\n")

# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = "LIF/amplifier_temperature_characterization",         # manuelle Eingabe
)
file_path_csv  = fu.make_data_file_name(
    data_dir  = data_dir,
    base_name = FILE_BASE_NAME,
    extension = "csv",
)
plots_dir = fu.make_data_dir(
    base_path = BASE_PATH, 
    base_name = "LIF/amplifier_temperature_characterization",   # manuelle Eingabe
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
    r_man.amplifier_diode.set_current(302.0, unit="mA", silent=True)

    scan_start_time = datetime.now()
    all_scans = []

    for i_idx, i_C in enumerate(i_list_C):
        print(f"\n{'─'*50}")
        print(f"  Scan {i_idx+1}/{len(i_list_C)}: T = {i_C:.1f} °C")
        print(f"{'─'*50}")


        # 1. Setze Starttemperatur und warte auf thermisches Gleichgewicht
        print(f"  Moving to temperature {i_C} °C ...")
        r_man.amplifier_diode.set_temperature(value=i_C, unit="C", silent=True)
        
        success = r_man._wait_for_temperature(laser=r_man.amplifier_diode, target_temp=i_C, tolerance=0.05, timeout=600)
        if not success: 
            print("  Warning: Start temperature not fully stabilized. Proceeding anyway...")
        print("    Waiting 20 more seconds for stabilization...")
        time.sleep(20)

        # Piezo-Scan – kein Plot pro Scan, nur DataFrame
        df_scan = r_man.scan_piezo(
            v_step    = V_STEP,
            v_unit    = "[V]",
            n_wlm     = N_WLM,
            zigzag    = ZIGZAG,
            hysteresis= HYSTERESIS,
            silent    = True,
            plot      = False,    # kein Einzel-Plot
            save_path = None,
        )

        # Temperatur als Spalte ergänzen
        # df_scan['master_temperature_C'] = i_C
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
        "temp_min_C":        TEMP_MIN_C,
        "temp_max_C":        TEMP_MAX_C,
        "temp_step_C":       TEMP_STEP_C,
        "n_wlm":             N_WLM,
        "v_step_V":          V_STEP,
        "zigzag":            ZIGZAG,
        "n_scans":           len(i_list_C),
        "n_points_total":    len(df_all),
    }
    meta.update(r_man.get_device_state_meta())

finally:
    r_man.amplifier_diode.set_temperature(
        value=17, unit="C", silent=True
    )
    r_man.laser_off()
    r_man.disconnect_all()

# ----------------------------------------------------------------
# Speichern
# ----------------------------------------------------------------


if df_all is not None and not df_all.empty:

    # Plot erstellen
    # lp.plot_characterization_wl_temp(df=df_all, save_path=str(file_path_plot))

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

# Plot mit lif_plotter: 

plot_flex(
    df              = df_all,
    x_col           = 'amplif_temperature_C',
    y_col           = 'wl_mean_m',
    group_col       = 'master_piezo_off_set_V',
    y_err_col       = 'wl_std_m',
    reference_lines = [
        # {'value': 667.91e-9, 'label': 'Ar I  667.91 nm', 'ls': '--'},
    ],
    linear_fit      = True,
    save_path       = str(file_path_plot),
    show            = True,
)