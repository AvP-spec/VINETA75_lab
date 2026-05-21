"""
drift_monitor_test.py
=====================
Messung der Wellenlängendrift des Master-Lasers bei 667.91 nm über 30 Minuten.
Speichert DataFrame + Plot mit Metadaten.

Ausführen:
    python drift_monitor_test.py
"""

# ----------------------------------------------------------------
# Imports
# ----------------------------------------------------------------
import sys
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Projektpfad einbinden
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from managers.lif import LIFManager
import utils.file_utils as fu
from utils.terminal_styler import TerminalColours

tc = TerminalColours()

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

print(f"{tc.BLUE}============= laser_warmup_test.py ============={tc.RESET}\n \n")

# ----------------------------------------------------------------
# Konfiguration – hier anpassen
# ----------------------------------------------------------------
BASE_PATH    = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")

FILE_BASE_NAME = "drift_667nm"              # Dateiname-Basis
COMMENT = "Drift-Monitor bei 667.91 nm, 30 min, avg ON"

LASER_WARMUP_S   = 20       # Wartezeit nach laser_on()
TARGET_WL_M      = 667.91e-9
TOLERANCE_PM     = 1.0
DRIFT_DURATION_S = 1800     # 30 Minuten
DRIFT_INTERVAL_S = 5        # alle 5 Sekunden

# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = "LIF/drift_monitor",    # <-- einzige manuelle Eingabe
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

print(f"Daten werden gespeichert in:\n  {data_dir}") 
print(f"CSV:  {file_path_csv.name}")
print(f"Plot: {file_path_plot.name}\n")

# ----------------------------------------------------------------
# Messung
# ----------------------------------------------------------------
r_man = LIFManager()
df = None

try:
    r_man.laser_on()
    print(f"    Waiting {LASER_WARMUP_S} sec for laser warmup")
    time.sleep(LASER_WARMUP_S)

    # Wellenlänge auf Zielwert einstellen
    reached = r_man.set_wavelength(
        target_wavelength_m = TARGET_WL_M,
        tolerance_pm        = TOLERANCE_PM,
        n_wlm               = 5,
        silent              = False,
    )
    if not reached:
        print(f"WARNUNG: Zielwellenlänge nicht erreicht – Messung wird trotzdem gestartet")

    # Metadaten zusammenstellen
    scan_start_time = datetime.now()
    meta = {
        "script":           Path(__file__).name,
        "scan_start_time":  str(scan_start_time),
        "comment":          COMMENT,
        "target_wl_nm":     TARGET_WL_M * 1e9,
        "tolerance_pm":     TOLERANCE_PM,
        "duration_s":       DRIFT_DURATION_S,
        "interval_s":       DRIFT_INTERVAL_S,
        "laser_warmup_s":   LASER_WARMUP_S,
    }
    # Geräteeinstellungen automatisch aus LIFManager
    meta.update(r_man.get_device_state_meta())

    # Drift-Monitor starten
    df = r_man.drift_monitor(
        duration_s = DRIFT_DURATION_S,
        interval_s = DRIFT_INTERVAL_S,
        plot       = True,
        save_path  = str(file_path_plot),
        silent     = False,
    )

finally:
    r_man.laser_off()
    r_man.disconnect_all()

# ----------------------------------------------------------------
# Speichern
# ----------------------------------------------------------------
if df is not None and not df.empty:
    fu.save_dataframe(
        df        = df,
        file_path = file_path_csv,
        metadata  = meta,
        sep       = "\t",
        index     = True,
        silent    = False,
    )
else:
    print("WARNUNG: Kein DataFrame zum Speichern – Messung leer oder abgebrochen")