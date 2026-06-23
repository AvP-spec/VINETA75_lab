"""
laser_temperature_characterization.py
=========================
Charakterisierung des Lasers:
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

# ----------------------------------------------------------------
# Konfiguration – hier anpassen
# ----------------------------------------------------------------

# Laser Auswahl: master / amplifier
LASER_TYPE = 'master'

LASER_MAP = {
    'master': {
        'obj': None, # Wird unten zugewiesen
        'name': 'Master',
        'col_temp': 'master_temperature_C',
        'col_piezo': 'master_piezo_off_set_V',
        'safe_temp': 16.0,
        'safe_current': 70 * 1e-3,
        'has_piezo': True,
    },
    'amplifier': {
        'obj': None, # Wird unten zugewiesen
        'name': 'Amplifier',
        'col_temp': 'amplif_temperature_C',
        'col_piezo': None,
        'safe_temp': 17.0,
        'safe_current': 302 * 1e-3,
        'has_piezo': False,
    }
}

active_laser = LASER_MAP[LASER_TYPE]
laser_obj     = active_laser['obj']
laser_name    = active_laser['name']
col_temp      = active_laser['col_temp']
col_piezo     = active_laser['col_piezo']
safe_temp     = active_laser['safe_temp']
safe_current  = active_laser['safe_current']
has_piezo     = active_laser['has_piezo']

TEMP_MIN_C       = 15.0     # °C min=-5
TEMP_MAX_C       = 25.0     # °C max=30
TEMP_STEP_C      = 5.0      # °C
N_WLM            = 5        # Wellenlängenmessungen pro Piezo-Punkt
V_STEP           = 13.5     # Piezo-Schrittweite [V]
ZIGZAG           = False
HYSTERESIS       = False

BASE_PATH      = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud_Manz/DATA/")
FILE_BASE_NAME = f"{LASER_TYPE}_temperature_characterization"
COMMENT        = f"Piezo-Scan für {laser_name} Laser, Temperaturen {TEMP_MIN_C} - {TEMP_MAX_C} °C in {TEMP_STEP_C} °C Schritten"

"""
"limits": {"max": 30, "min": -5, "unit": "[C]", "resolution": 1E-3},
            "unit_map": {"C": 1, "[C]": 1, },
"""

# ----------------------------------------------------------------
# Stromliste aufbauen
# ----------------------------------------------------------------
n_steps    = int(round((TEMP_MAX_C - TEMP_MIN_C) / TEMP_STEP_C)) + 1
i_list_C  = [round(TEMP_MIN_C + i * TEMP_STEP_C, 3)
               for i in range(n_steps)]

print(f"\n{tc.BLUE}============ {laser_name} Temp Characterization ============{tc.RESET}")
print(f"Temperaturliste: {i_list_C} °C\nAnzahl Scans: {len(i_list_C)}\n")

# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
folder_name = f"LIF/{LASER_TYPE}_temperature_characterization"

data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = folder_name,         # manuelle Eingabe
)
file_path_csv  = fu.make_data_file_name(
    data_dir  = data_dir,
    base_name = FILE_BASE_NAME,
    extension = "csv",
)
file_path_plot = fu.make_data_file_name(
    data_dir  = data_dir,
    base_name = FILE_BASE_NAME,
    extension = "png",
)

print(f"Daten werden gespeichert in:\n  {data_dir}\nCSV:  {file_path_csv.name}\nPlot: {file_path_plot.name}\n")

# ----------------------------------------------------------------
# Messung
# ----------------------------------------------------------------
r_man  = LIFManager()
if LASER_TYPE == 'master':
    laser_obj = r_man.master_diode
else:
    laser_obj = r_man.amplifier_diode

df_all = None

try:
    r_man.laser_on()
    laser_obj.set_current(safe_current, unit="A", silent=True)

    scan_start_time = datetime.now()
    all_scans = []

    for i_idx, i_C in enumerate(i_list_C):
        print(f"\n{'─'*50}")
        print(f"  Scan {i_idx+1}/{len(i_list_C)}: {laser_name} T = {i_C:.1f} °C")
        print(f"{'─'*50}")


        # 1. Setze Starttemperatur und warte auf thermisches Gleichgewicht
        print(f"  Moving to temperature {i_C} °C ...")
        laser_obj.set_temperature(value=i_C, unit="C", silent=True)
        
        success = r_man._wait_for_temperature(laser=laser_obj, target_temp=i_C, tolerance=0.05, timeout=600)
        if not success: 
            print("  Warning: Start temperature not fully stabilized. Proceeding anyway...")
        print("    Waiting 20 more seconds for stabilization...")
        time.sleep(20)

        # Piezo Messung nur für master
        if has_piezo: # master
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
        else: # amplifier
            df_scan = r_man.scan_piezo(
                v_step=0, v_unit="[V]", n_wlm=N_WLM,
                zigzag=False, hysteresis=False, silent=True,
                plot=False, save_path=None,
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
        "laser_type":        LASER_TYPE,
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
    print(f"  Returning {laser_name} to safe state...")
    laser_obj.set_temperature(
        value=safe_temp, unit="C", silent=True
    )
    laser_obj.set_current(
        safe_current, unit="A", silent=True
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

    # Plot mit lif_plotter: 
    plot_flex(
    df              = df_all,
    x_col           = col_temp,
    y_col           = 'wl_mean_m',
    group_col       = col_piezo,
    y_err_col       = 'wl_std_m',
    reference_lines = [
        # {'value': 667.91e-9, 'label': 'Ar I  667.91 nm', 'ls': '--'},
    ],
    linear_fit      = True,
    save_path       = str(file_path_plot),
    show            = True,
)

else:
    print("WARNUNG: Kein DataFrame – Messung leer oder abgebrochen")
