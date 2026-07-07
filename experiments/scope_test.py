"""
scope_test.py
=============
Testskript für das NI PXIe-5170R Oszilloskop.
Nimmt eine einzelne Waveform auf, speichert sie als CSV und als Plot.

Ausführen:
    python scope_test.py
"""

# ----------------------------------------------------------------
# Imports
# ----------------------------------------------------------------
import os
import sys
import getpass
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

# Projektpfad einbinden
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from devices.Scope_NI5170R import ScopeJakobs
import utils.file_utils as fu
from utils.terminal_styler import TerminalColours
tc = TerminalColours()

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)
print(f"\n{tc.BLUE}============ scope_test.py ============{tc.RESET}\n")

# ----------------------------------------------------------------
# Konfiguration – hier anpassen
# ----------------------------------------------------------------
BASE_PATH      = Path(r"C:\Users\andrei_lab\Nextcloud\5360.AG_Manz\DATA")
FILE_BASE_NAME = "scope_test"
COMMENT        = "Testmessung NI PXIe-5170R, Immediate Trigger, keine Signalquelle"

CHANNELS       = [0, 1]   # zu messende Kanäle
TIMEOUT_S      = 5.0      # Acquisition Timeout [s]

# Trigger-Modus:
# True  → Immediate (kein Hardware-Signal nötig, für Tests)
# False → Edge-Trigger auf TRIGGER_SOURCE
IMMEDIATE_TRIGGER  = True
TRIGGER_SOURCE     = "0"   # Kanal für Hardware-Trigger
TRIGGER_LEVEL_V    = 0.5   # [V]

# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = "LIF/scope_test",
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
df = None
scope = ScopeJakobs()
measure_start = datetime.now()

try:
    scope.connect(silent=False)

    if IMMEDIATE_TRIGGER:
        scope.configure_trigger_immediate(silent=False)
    else:
        scope.configure_trigger(
            trigger_source=TRIGGER_SOURCE,
            trigger_level=TRIGGER_LEVEL_V,
            silent=False,
        )

    df = scope.read_waveform_df(channels=CHANNELS, timeout=TIMEOUT_S, silent=False)
    print(f"\n{tc.GREEN}Messung erfolgreich:{tc.RESET} {len(df)} Datenpunkte")
    print(df.head())

finally:
    scope.disconnect()

# ----------------------------------------------------------------
# Speichern
# ----------------------------------------------------------------
if df is not None and not df.empty:

    # Metadaten
    meta = {
        "operator":        getpass.getuser(),
        "script":          Path(__file__).name,
        "measure_start":   str(measure_start),
        "comment":         COMMENT,
        "channels":        str(CHANNELS),
        "immediate_trigger": IMMEDIATE_TRIGGER,
        "trigger_source":  TRIGGER_SOURCE if not IMMEDIATE_TRIGGER else "immediate",
        "trigger_level_V": TRIGGER_LEVEL_V if not IMMEDIATE_TRIGGER else "N/A",
        "timeout_s":       TIMEOUT_S,
        "n_points":        len(df),
        "sample_rate_MS":  f"{1/(df.index[1]-df.index[0])/1e6:.1f}",
    }

    # CSV speichern
    fu.save_dataframe(
        df        = df,
        file_path = file_path_csv,
        metadata  = meta,
        sep       = "\t",
        index     = True,
        silent    = False,
    )

    # Plot erstellen und speichern
    fig, ax = plt.subplots(figsize=(10, 4))
    t_ms = df.index * 1e3  # s → ms
    for col in df.columns:
        ax.plot(t_ms, df[col], label=col)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(f"NI PXIe-5170R – {measure_start.strftime('%Y-%m-%d %H:%M:%S')}")
    ax.legend()
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(file_path_plot, dpi=150)
    print(f"{tc.GREEN}Plot gespeichert:{tc.RESET} {file_path_plot}")
    plt.show(block=True)

else:
    print(f"{tc.RED}WARNUNG: Kein DataFrame – Messung leer oder abgebrochen{tc.RESET}")