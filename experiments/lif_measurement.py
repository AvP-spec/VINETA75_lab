"""
lif_measurement.py
=========================
LIF-Anregungsspektrum: Piezo-Scan der Master-Laser-Wellenlänge bei fester
Temperatur. Für jeden Piezo-Punkt wird die Wellenlänge (WLM) UND das
LIF-Signal (Lock-In X/Y/R/Theta) gemessen.
 
Ergebnis: LIF-Signal (R, aus X/Y) vs. Wellenlänge, optional über mehrere
Wiederholungen (REPEATS) gemittelt/übereinandergelegt zur Rauschunterdrückung
bzw. Reproduzierbarkeits-Check.
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
 
# Master-Laser: einzige Quelle mit Piezo -> Wellenlängen-Durchstimmung
LASER_NAME    = 'Master'
SAFE_TEMP_C   = 16.0
SAFE_CURRENT  = 70 * 1e-3       # A
 
MEASURE_TEMP_C = 16.0           # Temperatur, bei der die LIF-Spektren
                                  # aufgenommen werden (typischerweise die
                                  # Betriebstemperatur, an der der Laser
                                  # sauber modenhoppfrei durchstimmt)
MEASURE_CURRENT_A = 70 * 1e-3
 
N_WLM      = 5      # Wellenlängen-/Lock-In-Messungen pro Piezo-Punkt (gemittelt)
V_STEP     = 0.5    # Piezo-Schrittweite [V] - fein für ein sauberes Spektrum
V_MIN      = None   # None -> volles Piezo-Limit verwenden
V_MAX      = None
ZIGZAG     = False
HYSTERESIS = False   # True: Hin- und Rückscan (z.B. um Piezo-Hysterese zu sehen)
 
N_REPEATS  = 3       # Anzahl kompletter Wiederholungen des Scans
                      # (Rauschunterdrückung / Reproduzierbarkeit; LIF-Signale
                      # sind i.d.R. deutlich verrauschter als das WLM-Signal)
 
BASE_PATH      = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud_Manz/DATA/")
FILE_BASE_NAME = "lif_measurement"
COMMENT        = (f"LIF-Anregungsspektrum bei T={MEASURE_TEMP_C} °C, "
                   f"{N_REPEATS} Wiederholungen, Piezo-Schrittweite {V_STEP} V")
 
# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
folder_name = "LIF/lif_measurement"
 
data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = folder_name,
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
 
print(f"\n{tc.BLUE}============ LIF Measurement ============{tc.RESET}")
print(f"Temperatur: {MEASURE_TEMP_C} °C, {N_REPEATS} Wiederholungen, "
      f"Piezo-Schrittweite {V_STEP} V\n")
print(f"Daten werden gespeichert in:\n  {data_dir}\nCSV:  {file_path_csv.name}\nPlot: {file_path_plot.name}\n")
 
# ----------------------------------------------------------------
# Messung
# ----------------------------------------------------------------
r_man = LIFManager()
 
df_all = None
 
try:
    # --- Vorab-Check: Lock-In Status (Referenz-Lock, Übersteuerung) ---
    # Wichtig, BEVOR der eigentliche Scan losläuft: wenn die Referenz nicht
    # eingerastet ist oder das Signal bereits übersteuert, ist jede
    # nachfolgende Messung wertlos.
    if hasattr(r_man, 'lia') and r_man.lia.connection is not None:
        status = r_man.lia.read_status_byte()
        if status["reference_unlock"]:
            print(f"{r_man.RED}WARNUNG: Lock-In Referenz ist NICHT eingerastet "
                  f"(reference unlock)! Referenzquelle/-frequenz prüfen "
                  f"(z.B. Chopper-Frequenz vs. IE-Einstellung am Gerät).{r_man.RESET}")
        if status["overload"]:
            print(f"{r_man.RED}WARNUNG: Lock-In meldet bereits jetzt Overload! "
                  f"Sensitivity/Empfindlichkeit am Gerät erhöhen (weniger empfindlich).{r_man.RESET}")
    else:
        print(f"{r_man.RED}WARNUNG: Lock-In (self.lia) nicht verbunden - "
              f"es wird kein LIF-Signal aufgezeichnet!{r_man.RESET}")
 
    r_man.laser_on()
    r_man.master_diode.set_current(MEASURE_CURRENT_A, unit="A", silent=True)
 
    print(f"Moving to measurement temperature {MEASURE_TEMP_C} °C ...")
    r_man.master_diode.set_temperature(value=MEASURE_TEMP_C, unit="C", silent=True)
    success = r_man._wait_for_temperature(
        laser=r_man.master_diode, target_temp=MEASURE_TEMP_C, tolerance=0.05, timeout=600
    )
    if not success:
        print("  Warning: Temperature not fully stabilized. Proceeding anyway...")
    print("    Waiting 20 more seconds for stabilization...")
    time.sleep(20)
 
    scan_start_time = datetime.now()
    all_scans = []
 
    for rep in range(N_REPEATS):
        print(f"\n{'─'*50}")
        print(f"  Scan {rep+1}/{N_REPEATS}")
        print(f"{'─'*50}")
 
        df_scan = r_man.scan_piezo(
            v_step     = V_STEP,
            v_min      = V_MIN,
            v_max      = V_MAX,
            v_unit     = "[V]",
            n_wlm      = N_WLM,
            zigzag     = ZIGZAG,
            hysteresis = HYSTERESIS,
            silent     = True,
            plot       = False,
            save_path  = None,
        )
        df_scan['repeat_idx'] = rep
        all_scans.append(df_scan)
 
    df_all = pd.concat(all_scans, ignore_index=True)
 
    print(f"\n{'='*50}")
    print(f"  Alle Scans abgeschlossen.")
    print(f"  Gesamt: {len(df_all)} Messpunkte")
    n_overload = int(df_all['lia_overload'].sum()) if 'lia_overload' in df_all else 0
    n_unlock   = int(df_all['lia_ref_unlock'].sum()) if 'lia_ref_unlock' in df_all else 0
    if n_overload or n_unlock:
        print(f"{r_man.RED}  WARNUNG: {n_overload} Punkte mit Overload, "
              f"{n_unlock} Punkte mit Reference-Unlock - diese Punkte vor der "
              f"Auswertung prüfen/verwerfen (df[~df['lia_overload']])!{r_man.RESET}")
    print(f"{'='*50}\n")
 
    # Metadaten
    meta = {
        "operator":          getpass.getuser(),
        "script":            Path(__file__).name,
        "scan_start_time":   str(scan_start_time),
        "comment":           COMMENT,
        "measure_temp_C":    MEASURE_TEMP_C,
        "measure_current_A": MEASURE_CURRENT_A,
        "n_wlm":             N_WLM,
        "v_step_V":          V_STEP,
        "zigzag":            ZIGZAG,
        "hysteresis":        HYSTERESIS,
        "n_repeats":         N_REPEATS,
        "n_points_total":    len(df_all),
        "n_overload_points": n_overload,
        "n_unlock_points":   n_unlock,
    }
    meta.update(r_man.get_device_state_meta())
 
finally:
    print(f"  Returning {LASER_NAME} to safe state...")
    r_man.master_diode.set_temperature(value=SAFE_TEMP_C, unit="C", silent=True)
    r_man.master_diode.set_current(SAFE_CURRENT, unit="A", silent=True)
    r_man.laser_off()
    r_man.disconnect_all()
 
# ----------------------------------------------------------------
# Speichern
# ----------------------------------------------------------------
 
if df_all is not None and not df_all.empty:
 
    # DataFrame speichern
    fu.save_dataframe(
        df        = df_all,
        file_path = file_path_csv,
        metadata  = meta,
        sep       = "\t",
        index     = True,
        silent    = False,
    )
 
    # Plot: LIF-Signal (Magnitude R) vs. Wellenlänge, je Wiederholung eingefärbt
    plot_flex(
        df              = df_all,
        x_col           = 'wl_mean_m',
        y_col           = 'lia_R_V',
        group_col       = 'repeat_idx',
        y_err_col       = None,
        reference_lines = [
            # {'value': 667.91e-9, 'label': 'Ar I  667.91 nm', 'ls': '--'},
        ],
        linear_fit      = False,
        save_path       = str(file_path_plot),
        show            = True,
    )
 
else:
    print("WARNUNG: Kein DataFrame – Messung leer oder abgebrochen")
 
