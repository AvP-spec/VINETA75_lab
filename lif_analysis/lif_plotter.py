"""
lif_plotter_flex.py
===================
Flexibles Plot-Skript für LIF-Messdaten.

Konfiguration am Anfang des Skripts:
  - X_COL    : Spalte für die X-Achse
  - Y_COL    : Spalte für die Y-Achse
  - GROUP_COL: Spalte für Farb- und Symbol-Kodierung (dritte Größe)
  - Filter   : Wertebereiche für X, Y und GROUP

Verfügbare Spalten (typisch):
  'master_piezo_off_set_V'   Piezo-Spannung [V]
  'current_mA'               Master-Strom [mA]
  'master_temperature_C'     Master-Temperatur [°C]
  'wl_mean_m'                Wellenlänge [m]

Beispiel-Konfigurationen:
  λ vs. Piezo, Farbe = Strom:
      X_COL     = 'master_piezo_off_set_V'
      Y_COL     = 'wl_mean_m'
      GROUP_COL = 'current_mA'

  λ vs. Strom, Farbe = Piezo:
      X_COL     = 'current_mA'
      Y_COL     = 'wl_mean_m'
      GROUP_COL = 'master_piezo_off_set_V'

  λ vs. Temperatur, Farbe = Piezo:
      X_COL     = 'master_temperature_C'
      Y_COL     = 'wl_mean_m'
      GROUP_COL = 'master_piezo_off_set_V'
"""

import os
import sys
import json
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from pathlib import Path

# Projektpfad einbinden
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import utils.file_utils as fu

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

# ================================================================
# KONFIGURATION – hier anpassen
# ================================================================

# --- Achsen ---
X_COL     = 'amplif_current_A'                # X-Achse
Y_COL     = 'wl_mean_m'                 # Y-Achse
GROUP_COL = 'master_piezo_off_set_V'    # Farbe + Symbol (dritte Größe)

# --- Fehlerbalken ---
# Spalte für Fehlerbalken auf Y-Achse, None = kein Fehlerbalken
Y_ERR_COL = 'wl_std_m'

# --- Filter: None = kein Filter, sonst [min, max] ---
FILTER = {
    X_COL:     [-0.55,0],          # z.B. [-10, 10]  für Piezo -10 bis +10 V
    Y_COL:     None,          # z.B. [668.5e-9, 668.7e-9]
    GROUP_COL: None,          # z.B. [40, 60]   für Strom 40-60 mA
}

# --- Referenzlinien (Y-Werte in Daten-Einheit, None = keine) ---
REFERENCE_LINES = [
    # {'value': 667.91e-9, 'label': 'Ar I  667.91 nm',  'ls': '--'},
    # {'value': 668.40e-9, 'label': 'Ar II 668.40 nm',  'ls': ':'},
]

# --- Linearer Fit pro Gruppe ---
LINEAR_FIT = True

# --- Colormap ---
COLORMAP = 'tab10'   # 'plasma', 'coolwarm', 'viridis', 'tab10', ...

# --- Plot-Größe ---
FIGSIZE = (11, 7)

# ================================================================
# Achsenbeschriftungen und Skalierung
# ================================================================

# Einheiten und Skalierung pro Spalte
COL_CONFIG = {
    'master_piezo_off_set_V': {
        'label':  'Piezo-Spannung [V]',
        'scale':  1.0,
        'format': '{:.1f}',
        'short':  'piezo',
    },
    'master_current_mA': {
        'label':  'Master-Strom [mA]',
        'scale':  1.0,
        'format': '{:.0f}',
        'short':  'I_m',
    },
    'amplif_current_A': {
        'label':  'Amplifier-Strom [A]',
        'scale':  1.0,
        'format': '{:.0f}',
        'short':  'I_a',
    },
    'master_temperature_C': {
        'label':  'Master-Temperatur [°C]',
        'scale':  1.0,
        'format': '{:.3f}',
        'short':  'T_m',
    },
    'amplif_temperature_C':{
        'label':  'Amplifier-Temperatur [°C]',
        'scale':  1.0,
        'format': '{:.3f}',
        'short':  'T_a',
    },
    'wl_mean_m': {
        'label':  'Wellenlänge [nm]',
        'scale':  1e9,
        'format': '{:.4f}',
        'short':  'wl',
    },
    'wl_std_m': {
        'label':  'λ Std [pm]',
        'scale':  1e12,
        'format': '{:.3f}',
        'short':  'wl_std',
    },
}

def get_cfg(col):
    '''Gibt COL_CONFIG für col zurück, mit Fallback für unbekannte Spalten.'''
    return COL_CONFIG.get(col, {
        'label':  col,
        'scale':  1.0,
        'format': '{:.3f}',
        'short':  col,
    })


# ================================================================
# Hilfsfunktionen
# ================================================================

def read_header(filepath: Path) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        if not first_line.startswith('# Header-Lines:'):
            return {}
        n_header = int(first_line.split(':')[-1].strip())
        header_lines = [first_line] + [f.readline() for _ in range(n_header - 1)]
    for line in header_lines:
        if line.startswith('# JSON_META:'):
            return json.loads(line.split('# JSON_META:', 1)[1].strip())
    return {}


def load_csv(filepath: Path):
    meta = read_header(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        n_header = int(f.readline().split(':')[-1].strip())
    df = pd.read_csv(filepath, sep='\t', skiprows=n_header, index_col=0)
    return df, meta


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    '''Filtert DataFrame nach Wertebereichen.'''
    mask = pd.Series(True, index=df.index)
    for col, bounds in filters.items():
        if bounds is None:
            continue
        if col not in df.columns:
            print(f"  WARNUNG: Spalte '{col}' nicht im DataFrame – Filter ignoriert")
            continue
        lo, hi = bounds
        mask &= (df[col] >= lo) & (df[col] <= hi)
        n_before = len(df)
        n_after  = mask.sum()
        print(f"  Filter '{col}' [{lo}, {hi}]: "
              f"{n_before} → {n_after} Zeilen")
    return df[mask].copy()


def make_plot_filename(csv_path: Path, x_col: str, y_col: str) -> Path:
    '''Erstellt PNG-Dateiname aus CSV-Name + Achseninformation.'''
    stem     = csv_path.stem
    x_short  = get_cfg(x_col)['short']
    y_short  = get_cfg(y_col)['short']
    suffix   = f"_{y_short}-{x_short}.png"
    return csv_path.parent / (stem + suffix)


# ================================================================
# Plot-Funktion
# ================================================================

def plot_flex(df: pd.DataFrame,
              x_col: str,
              y_col: str,
              group_col: str,
              y_err_col: str       = None,
              reference_lines: list= None,
              linear_fit: bool     = True,
              colormap: str        = 'plasma',
              figsize: tuple       = (11, 7),
              save_path: str       = None,
              show: bool           = True,
              ) -> plt.Figure:
    '''
    Flexibler Plot: y_col vs. x_col, gruppiert nach group_col.
    Farbe + Symbol kodieren die dritte Größe (group_col).

    Parameters
    ----------
    df             : DataFrame mit Messdaten
    x_col          : Spaltenname X-Achse
    y_col          : Spaltenname Y-Achse
    group_col      : Spaltenname für Farb/Symbol-Kodierung
    y_err_col      : Spaltenname für Fehlerbalken (optional)
    reference_lines: Liste von {'value', 'label', 'ls'} in Y-Daten-Einheit
    linear_fit     : linearen Fit pro Gruppe einzeichnen
    colormap       : matplotlib Colormap Name
    figsize        : Figure-Größe
    save_path      : Speicherpfad für PNG
    show           : Plot anzeigen
    '''
    # Konfiguration für die drei Spalten
    x_cfg   = get_cfg(x_col)
    y_cfg   = get_cfg(y_col)
    grp_cfg = get_cfg(group_col)

    # Skalierte Werte
    df = df.copy()
    df[f'_x']   = df[x_col]   * x_cfg['scale']
    df[f'_y']   = df[y_col]   * y_cfg['scale']
    if y_err_col and y_err_col in df.columns:
        df['_yerr'] = df[y_err_col] * y_cfg['scale']
    else:
        df['_yerr'] = 0.0

    # Gruppen
    group_values = sorted(df[group_col].unique())
    n            = len(group_values)

    cmap   = plt.get_cmap(colormap)
    colors = [cmap(i % 10) if 'tab' in colormap else cmap(i / max(n-1, 1)) for i in range(n)]    
    markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'h', 'X', 'P',
               '<', '>', '8', 'H', 'd']
    markers = (markers * (n // len(markers) + 1))[:n]

    fig, ax = plt.subplots(figsize=figsize)

    fit_rates  = []

    for col, marker, grp_val in zip(colors, markers, group_values):
        df_g  = df[df[group_col] == grp_val].sort_values(x_col)
        x     = df_g['_x'].values
        y     = df_g['_y'].values
        yerr  = df_g['_yerr'].values

        grp_label = grp_cfg['format'].format(grp_val)

        # Datenpunkte
        ax.errorbar(
            x, y,
            yerr       = yerr if y_err_col else None,
            fmt        = f'{marker}-',
            color      = col,
            markersize = 8,
            linewidth  = 0.0,                                  # Verbindungslinie zwischen Messpunkten
            capsize    = 2,
            capthick   = 0.8,
            elinewidth = 0.6,
            label      = f"{grp_label}",
            alpha      = 1.0,
            zorder     = 3,
        )

        # Linearer Fit
        if linear_fit and len(x) >= 2:
            coeffs  = np.polyfit(x, y, 1)
            x_fit   = np.linspace(x.min(), x.max(), 100)
            y_fit   = np.polyval(coeffs, x_fit)
            ax.plot(x_fit, y_fit,
                    color     = col,
                    linewidth = 0.8,
                    linestyle = '--',
                    alpha     = 0.5,
                    zorder    = 2)
            fit_rates.append({
                'group':  grp_val,
                'rate':   coeffs[0],
                'offset': coeffs[1],
            })


    # zusätzliche Legende
    ax.legend(
        title=grp_cfg['label'], 
        fontsize=10, 
        title_fontsize=12, 
        loc='upper left', 
        bbox_to_anchor=(1.01,1),
        frameon=True, 
        edgecolor='gray'
    )

    # Referenzlinien
    if reference_lines:
        for ref in reference_lines:
            y_ref = ref['value'] * y_cfg['scale']
            ax.axhline(y_ref,
                       color     = 'black',
                       linewidth = 1.0,
                       linestyle = ref.get('ls', '--'),
                       alpha     = 0.7,
                       zorder    = 1)
            ax.text(
                0.1, y_ref+0.02,
                ref['label'],
                transform = ax.get_yaxis_transform(),
                fontsize  = 12,
                va        = 'center',
                color     = 'black',
                alpha     = 1.0,
            )

    # Fit-Raten Textbox
    if linear_fit and fit_rates:
        rates     = [r['rate'] for r in fit_rates]
        rate_mean = np.mean(rates) * 1e3   # nm/mA → pm/mA
        rate_std  = np.std(rates)  * 1e3   # nm/mA → pm/mA
        label_text = x_cfg['label']
        if '[' in label_text and ']' in label_text: 
            x_unit = label_text.split('[')[1].split(']')[0]
        else: 
            x_unit = x_cfg.get('short', 'unit')
        ax.text(
            1.01, 0.1,                                             # Position der Textbox
            f"Lin. Fit:\n"
            f"  Mittel: {rate_mean:.3f} pm/{x_unit}\n"
            f"  Std:    {rate_std:.3f} pm/{x_unit}",
            transform = ax.transAxes,
            fontsize  = 10,
            va        = 'top',
            bbox      = dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

    ax.set_xlabel(x_cfg['label'],   fontsize=15)
    ax.set_ylabel(y_cfg['label'],   fontsize=15)
    ax.tick_params(axis='both', labelsize=12, direction='in')
    ax.set_title(
        f"{y_cfg['label'].split('[')[0].strip()} vs. "
        f"{x_cfg['label'].split('[')[0].strip()}\n", 
        # f"({grp_cfg['label'].split('[')[0].strip()} farbkodiert)",
        fontsize=12, fontweight='bold'
    )
    ax.grid(True, linestyle='--', alpha=0.4)

    plt.tight_layout()
    fig.subplots_adjust(right=0.82)

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot gespeichert: {save_path}")

    if show:
        plt.show(block=True)
    plt.close(fig)
    return fig


# ================================================================
# Main
# ================================================================

if __name__ == '__main__':

    # --- Datei auswählen ---
    filepath = fu.select_file(filter="CSV Dateien (*.csv);;Alle Dateien (*)")
    if filepath is None:
        print("Keine Datei ausgewählt – Abbruch.")
        sys.exit()

    filepath = Path(filepath)
    print(f"\nDatei: {filepath.name}")

    # --- Laden ---
    df, meta = load_csv(filepath)
    print(f"Geladen: {len(df)} Zeilen, Spalten: {list(df.columns)}")

    if meta:
        print(f"Metadaten: {list(meta.keys())}")

    # --- Filtern ---
    print("\nFilter:")
    df = apply_filters(df, FILTER)
    print(f"Nach Filter: {len(df)} Zeilen\n")

    if df.empty:
        print("WARNUNG: DataFrame nach Filter leer – Abbruch.")
        sys.exit()

    # --- Fehlende Spalten prüfen ---
    for col in [X_COL, Y_COL, GROUP_COL]:
        if col not in df.columns:
            print(f"FEHLER: Spalte '{col}' nicht im DataFrame.")
            print(f"Verfügbare Spalten: {list(df.columns)}")
            sys.exit()

    # --- Ausgabepfad ---
    save_path = make_plot_filename(filepath, X_COL, Y_COL)
    print(f"Plot wird gespeichert als: {save_path.name}\n")

    # --- Plot ---
    plot_flex(
        df              = df,
        x_col           = X_COL,
        y_col           = Y_COL,
        group_col       = GROUP_COL,
        y_err_col       = Y_ERR_COL,
        reference_lines = REFERENCE_LINES,
        linear_fit      = LINEAR_FIT,
        colormap        = COLORMAP,
        figsize         = FIGSIZE,
        save_path       = str(save_path),
        show            = True,
    )