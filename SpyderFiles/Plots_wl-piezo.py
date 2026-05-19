"""
Vergleichsplot: Wellenlänge vs. Piezo-Spannung – alle Scans überlagert.

Liest alle .csv Dateien aus PIEZO_SCAN_DIR ein und plottet:
  - Oberer Plot: Wellenlänge [nm] vs. Piezo-Spannung [V], alle Scans überlagert
  - Unterer Plot: Wellenlänge relativ zum Mittelwert [pm], um Drift sichtbar zu machen

Farbe kodiert die Uhrzeit (früh → spät), Linienstil kodiert average ON/OFF.
Speichert den Plot als .png in PLOTS_DIR.
"""

import json
import re
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import os

import sys
from pathlib import Path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.terminal_styler import TerminalColours
style = TerminalColours()


BASE_PATH = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")
EXPERIMENT_PATH = "2026-04-21_Andrei_LIF"           # <-- anpassen

PIEZO_SCAN_DIR = BASE_PATH / EXPERIMENT_PATH / "piezo_scan"
PLOTS_DIR      = BASE_PATH / EXPERIMENT_PATH / "plots_wl-piezo"

LOCAL_TZ = ZoneInfo("Europe/Berlin")



def read_header(filepath: Path) -> dict:
    """Liest den JSON_META-Block aus dem Datei-Header."""
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if not first_line.startswith("# Header-Lines:"):
            raise ValueError(f"Kein gültiger Header in {filepath.name}")
        n_header = int(first_line.split(":")[-1].strip())
        header_lines = [first_line] + [f.readline() for _ in range(n_header - 1)]

    for line in header_lines:
        if line.startswith("# JSON_META:"):
            return json.loads(line.split("# JSON_META:", 1)[1].strip())

    raise ValueError(f"Kein JSON_META in {filepath.name}")


def load_csv(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """Liest Header-Metadaten und Messdaten aus einer .csv Datei."""
    meta = read_header(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        n_header = int(f.readline().split(":")[-1].strip())
    df = pd.read_csv(filepath, sep="\t", skiprows=n_header, index_col=0)
    return df, meta


def parse_scan_time(meta: dict, filepath: Path) -> datetime:
    """
    Liest scan_start_time aus dem Header.
    Fallback: Uhrzeit aus dem Dateinamen (HH-MM-SS).
    """
    if "scan_start_time" in meta:
        dt = datetime.fromisoformat(meta["scan_start_time"])
        return dt.replace(tzinfo=LOCAL_TZ)

    # Fallback: Dateiname z.B. "09-52-07_average_ON.csv"
    match = re.match(r"(\d{2})-(\d{2})-(\d{2})", filepath.stem)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        today = datetime.now(tz=LOCAL_TZ).date()
        return datetime(today.year, today.month, today.day, h, m, s, tzinfo=LOCAL_TZ)

    raise ValueError(f"Keine Zeitinformation für {filepath.name}")


def parse_average_mode(filepath: Path) -> str:
    """Liest average ON/OFF aus dem Dateinamen."""
    name = filepath.stem.lower()
    if "average_on" in name:
        return "ON"
    if "average_off" in name:
        return "OFF"
    return "?"




def plot_piezo_comparison(
        piezo_scan_dir: Path = PIEZO_SCAN_DIR,
        plots_dir: Path = PLOTS_DIR,
        wl_unit: str = "nm",        # "nm" oder "pm"
        sort_by_time: bool = True,
):
    """
    Erstellt Vergleichsplot: λ vs. Piezo für alle Scans im Ordner.

    Parameters
    ----------
    wl_unit     : Einheit der Wellenlängen-Achse ("nm" oder "pm")
    sort_by_time: Scans chronologisch sortieren (für Farbkodierung)
    """
    csv_files = sorted(piezo_scan_dir.glob("*.csv"))
    if not csv_files:
        print(f"Keine .csv Dateien in {piezo_scan_dir}")
        return


    scans = []
    for fp in csv_files:
        try:
            df, meta = load_csv(fp)
            t = parse_scan_time(meta, fp)
            avg = parse_average_mode(fp)
            scans.append({
                "filepath": fp,
                "df":       df,
                "meta":     meta,
                "time":     t,
                "average":  avg,
                "label":    f"{t.strftime('%H:%M:%S')}  avg {avg}",
            })
        except Exception as e:
            print(f"  FEHLER beim Laden von {fp.name}: {e}")

    if not scans:
        print("Keine Scans geladen.")
        return

    if sort_by_time:
        scans.sort(key=lambda s: s["time"])

    n = len(scans)
    print(f"{n} Scan(s) geladen.")

    # Farbskala
    times_unix = np.array([s["time"].timestamp() for s in scans])
    t_min, t_max = times_unix.min(), times_unix.max()
    norm = np.linspace(0, 1, n)
    # colors = cm.plasma(norm)
    colors = cm.coolwarm(norm)
    # colors = cm.tab20(norm)

    # Linienstil nach average-Modus
    linestyle_map = {"ON": "-", "OFF": "--", "?": ":"}

    # Wellenlängen-Skalierung
    if wl_unit == "nm":
        wl_scale = 1e9
        wl_label = "Wellenlänge [nm]"
    else:
        wl_scale = 1e12
        wl_label = "Wellenlänge [pm]"

    # globaler Mittelwert
    # Interpoliere alle Scans auf ein gemeinsames Piezo-Raster
    v_all = np.sort(np.unique(np.concatenate(
        [s["df"]["master_piezo_off_set_V"].values for s in scans]
    )))


    fig, axes = plt.subplots(
        2, 1,
        figsize=(11, 9),
        sharex=True,
        gridspec_kw={"hspace": 0.08, "height_ratios": [2, 1]}
    )

    ax_abs = axes[0]   # absoluter Plot
    ax_rel = axes[1]   # relativer Plot (Drift)

    # gemeinsame interpolierte Wellenlängenwerte für Mittelwert
    interp_matrix = []

    for i, scan in enumerate(scans):
        df  = scan["df"]
        col = colors[i]
        ls  = linestyle_map.get(scan["average"], "-")
        lbl = scan["label"]

        piezo = df["master_piezo_off_set_V"].values
        wl    = df["wlm_wavelength"].values * wl_scale

        # nach Piezo-Spannung sortieren für saubere Linie
        order = np.argsort(piezo)
        piezo_s = piezo[order]
        wl_s    = wl[order]

        ax_abs.plot(piezo_s, wl_s,
                    color=col, linestyle=ls, linewidth=1.2,
                    marker="o", markersize=3,
                    label=lbl, alpha=0.85)

        # Interpolation auf gemeinsames Raster
        wl_interp = np.interp(v_all, piezo_s, wl_s,
                               left=np.nan, right=np.nan)
        interp_matrix.append(wl_interp)

    # Mittelwert und relative Abweichung
    interp_matrix = np.array(interp_matrix)           # (n_scans, n_v)
    wl_mean = np.nanmean(interp_matrix, axis=0)        # Mittelwert über alle Scans

    for i, scan in enumerate(scans):
        col = colors[i]
        ls  = linestyle_map.get(scan["average"], "-")
        delta = interp_matrix[i] - wl_mean             # Abweichung in wl_unit

        # nur gültige Punkte
        mask = ~np.isnan(delta)
        if wl_unit == "nm":
            delta_pm = delta[mask] * 1e3               # nm → pm für relativen Plot
            rel_label = "Abweichung [pm]"
        else:
            delta_pm = delta[mask]
            rel_label = "Abweichung [pm]"

        ax_rel.plot(v_all[mask], delta_pm,
                    color=col, linestyle=ls, linewidth=1.0,
                    marker="o", markersize=2, alpha=0.8)

    ax_rel.axhline(0, color="black", linewidth=0.8, linestyle=":")


    ax_abs.set_ylabel(wl_label, fontsize=11)
    ax_abs.grid(True, linestyle="--", alpha=0.4)
    ax_abs.tick_params(axis="x", labelbottom=False)

    ax_rel.set_xlabel("Piezo-Spannung [V]", fontsize=11)
    ax_rel.set_ylabel(rel_label, fontsize=11)
    ax_rel.grid(True, linestyle="--", alpha=0.4)


    ncol = 2 if n > 8 else 1
    ax_abs.legend(
        fontsize=7.5,
        loc="upper left",
        ncol=ncol,
        framealpha=0.85,
        title="Uhrzeit   avg",
        title_fontsize=8,
    )


    from matplotlib.lines import Line2D
    style_handles = [
        Line2D([0], [0], color="gray", linestyle="-",  label="average ON"),
        Line2D([0], [0], color="gray", linestyle="--", label="average OFF"),
    ]
    ax_abs.legend(
        handles=style_handles,
        fontsize=8,
        loc="upper left",
        framealpha=0.85,
        title="Messmodus",
        title_fontsize=8,
    )

    handles, labels = [], []
    for i, scan in enumerate(scans):
        handles.append(Line2D([0], [0],
                               color=colors[i],
                               linestyle=linestyle_map.get(scan["average"], "-"),
                               linewidth=1.5))
        labels.append(scan["label"])

    fig.legend(
        handles, labels,
        fontsize=7.5,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        framealpha=0.85,
        title="Uhrzeit   avg",
        title_fontsize=8,
        ncol=1,
    )

    fig.suptitle(
        f"Wellenlänge vs. Piezo-Spannung – {n} Scans\n"
        f"{EXPERIMENT_PATH}",
        fontsize=12, fontweight="bold"
    )

    plt.tight_layout(rect=[0, 0, 0.82, 1])  # Platz für Legende rechts


    plots_dir.mkdir(parents=True, exist_ok=True)
    out_path = plots_dir / "piezo_comparison_all.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"{style.GREEN}Plot gespeichert: {out_path}{style.RESET}")




if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\n {style.MAGENTA}====== Plots_wl-piezo.py ======={style.RESET}")

    plot_piezo_comparison(
        wl_unit="nm",       # "nm" oder "pm"
        sort_by_time=True,
    )