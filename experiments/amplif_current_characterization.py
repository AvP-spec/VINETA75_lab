"""
laser_characterization.py
=========================
Charakterisierung des Amplifier-Lasers:
Piezo-Scan für jeden Stromwert im angegebenen Bereich. 

Für jeden Strom wird ein vollständiger Piezo-Scan durchgeführt.
Ergebnis: Wellenlänge vs. Piezo-Spannung für alle Ströme, farbcodiert nach Strom.

Ausführen:
    python laser_characterization.py
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

from lif_analysis.lif_plotter import plot_flex

from utils.terminal_styler import TerminalColours

tc = TerminalColours()

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

print(f"\n{tc.BLUE}============ amplifier_current_characterization.py ============{tc.RESET}\n \n")

# ----------------------------------------------------------------
# Konfiguration – hier anpassen
# ----------------------------------------------------------------
BASE_PATH      = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")
FILE_BASE_NAME = "amplifier_current_characterization"
COMMENT        = "Piezo-Scan für Ströme 200-1000 mA in 100 mA Schritten"

LASER_WARMUP_S   = 5        # Wartezeit nach laser_on()
CURRENT_MIN_MA   = 200.0     # mA        min = 0 A
CURRENT_MAX_MA   = 600.0     # mA        max = 4.1 A
CURRENT_STEP_MA  = 100.0      # mA
CURRENT_SETTLE_S = 2.0      # Wartezeit nach Stromänderung
N_WLM            = 3        # Wellenlängenmessungen pro Piezo-Punkt
V_STEP           = 13.5      # Piezo-Schrittweite [V]
ZIGZAG           = False
HYSTERESIS       = False     # Hysteresis Messung

# ----------------------------------------------------------------
# Stromliste aufbauen
# ----------------------------------------------------------------
n_steps    = int(round((CURRENT_MAX_MA - CURRENT_MIN_MA) / CURRENT_STEP_MA)) + 1
i_list_mA  = [round(CURRENT_MIN_MA + i * CURRENT_STEP_MA, 3)
               for i in range(n_steps)]

print(f"Stromliste: {i_list_mA} mA")
print(f"Anzahl Scans: {len(i_list_mA)}\n")

# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = "LIF/amplifier_current_characterization",         # manuelle Eingabe
)
file_path_csv  = fu.make_data_file_name(
    data_dir  = data_dir,
    base_name = FILE_BASE_NAME,
    extension = "csv",
)
plots_dir = fu.make_data_dir(
    base_path = BASE_PATH, 
    base_name = "LIF/amplifier_current_characterization",   # manuelle Eingabe
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

        # Strom setzen und warten
        r_man.amplifier_diode.set_current(i_mA * 1e-3, unit="A", silent=True)
        time.sleep(CURRENT_SETTLE_S)

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

        # Strom als Spalte ergänzen
        # df_scan['current_mA'] = i_mA
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
    r_man.amplifier_diode.set_current(
        302 * 1e-3, unit="A", silent=True
    )
    r_man.laser_off()
    r_man.disconnect_all()

# ----------------------------------------------------------------
# Speichern
# ----------------------------------------------------------------


if df_all is not None and not df_all.empty:

    # Plot erstellen
    # lp.plot_characterization(df=df_all, CURRENT_STEP_MA=CURRENT_STEP_MA, save_path=str(file_path_plot))

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

plot_flex(
    df              = df_all,
    x_col           = 'master_piezo_off_set_V',
    y_col           = 'wl_mean_m',
    group_col       = 'amplif_current_A',
    y_err_col       = 'wl_std_m',
    reference_lines = [
        # {'value': 667.91e-9, 'label': 'Ar I  667.91 nm', 'ls': '--'},
    ],
    linear_fit      = True,
    save_path       = str(file_path_plot),
    show            = True,
)