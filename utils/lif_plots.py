"""
lif_plots.py
============
Plot-Funktionen für das LIF-Messsystem.

Alle Visualisierungen die zuvor in lif.py als Methoden des LIFManager
implementiert waren, werden hier als eigenständige Funktionen gesammelt.

Verwendung in lif.py:
    from utils.lif_plots import plot_scan_piezo, plot_settling, ...
    # oder als Modul:
    import utils.lif_plots as lp
    lp.plot_scan_piezo(df, save_path="...")

Verwendung in Mess-Skripten:
    import utils.lif_plots as lp
    lp.plot_characterization(df, save_path="...")

Alle Funktionen haben dieselbe Signatur:
    plot_xxx(df, save_path=None, show=True, **kwargs)
    → speichert wenn save_path gegeben
    → zeigt Plot wenn show=True
    → gibt fig zurück für weitere Bearbeitung
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.gridspec import GridSpec
from pathlib import Path
from utils.terminal_styler import TerminalColours

tc = TerminalColours()


# ----------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------

def _save_and_show(fig, save_path=None, show=True):
    '''Speichert und zeigt Plot. Intern von allen Plot-Funktionen genutzt.'''
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot gespeichert: {save_path}")
    if show:
        plt.show(block=False)
        plt.pause(0.5)
    plt.close(fig)


# ----------------------------------------------------------------
# Plot-Funktionen
# ----------------------------------------------------------------

def plot_scan_piezo(df: pd.DataFrame,
                    save_path: str = None,
                    show: bool = True,
                    ) -> plt.Figure:
    '''Plot results of scan_piezo(): wavelength vs piezo and temperature stability.'''
    
    fig, (ax_wl, ax_temp) = plt.subplots(
        2, 1, figsize=(10, 7), 
        gridspec_kw={"hspace": 0.35}
    )

    # --- Plot A: Wellenlänge vs. Piezo-Spannung ---
    wl_nm     = df['wl_mean_m'] * 1e9
    wl_err_nm = df['wl_std_m']  * 1e9
    piezo     = df['piezo_V']

    ax_wl.errorbar(
        piezo, wl_nm,
        yerr=wl_err_nm,
        fmt='o-', color='tab:blue',
        markersize=5, linewidth=1.4,
        capsize=3, capthick=1, elinewidth=0.8,
        label='λ mean ± std'
    )
    ax_wl.set_xlabel("Piezo-Spannung [V]", fontsize=11)
    ax_wl.set_ylabel("Wellenlänge [nm]",   fontsize=11)
    ax_wl.set_title("Wellenlänge vs. Piezo-Spannung", fontsize=11)
    ax_wl.legend(fontsize=9)
    ax_wl.grid(True, linestyle='--', alpha=0.4)

    # Abstimmrate als Text
    if len(df) > 1:
        dv  = piezo.max() - piezo.min()
        dwl = wl_nm.max() - wl_nm.min()
        rate = dwl / dv if dv > 0 else 0
        ax_wl.text(
            0.97, 0.05,
            f"Abstimmrate: {rate*1e3:.2f} pm/V",
            transform=ax_wl.transAxes,
            fontsize=9, ha='right', va='bottom',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
        )

    # --- Plot B: Temperatur vs. Zeit ---
    time_s = df['time_s']

    ax_temp.plot(time_s, df['master_temperature_C'],
                'o-', color='tab:blue', markersize=4,
                linewidth=1.2, label='Master')
    ax_temp.plot(time_s, df['amplif_temperature_C'],
                's--', color='tab:orange', markersize=4,
                linewidth=1.2, label='Amplifier')

    ax_temp.set_xlabel("Zeit [s]",          fontsize=11)
    ax_temp.set_ylabel("Temperatur [°C]",   fontsize=11)
    ax_temp.set_title("Laser-Temperatur während des Scans", fontsize=11)
    ax_temp.legend(fontsize=9)
    ax_temp.grid(True, linestyle='--', alpha=0.4)

    # Temperaturschwankung als Text
    t_master_range = df['master_temperature_C'].max() - df['master_temperature_C'].min()
    t_amplif_range = df['amplif_temperature_C'].max() - df['amplif_temperature_C'].min()
    ax_temp.text(
        0.97, 0.97,
        f"Master Δ: {t_master_range*1e3:.1f} mK\n"
        f"Amplif Δ: {t_amplif_range*1e3:.1f} mK",
        transform=ax_temp.transAxes,
        fontsize=9, ha='right', va='top',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
    )

    fig.suptitle("scan_piezo() Ergebnis", fontsize=13, fontweight='bold')
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"{tc.GREEN}Plot gespeichert: {save_path}{tc.RESET}")

    print(f"{tc.YELLOW2}-------- Close Figure to continue -------- {tc.RESET}")
    plt.show(block=True)
    # plt.pause(0.5)
    # plt.close(fig)
    pass


def plot_settling(all_results: dict,
                  scenarios: list,
                  save_path: str = None,
                  show: bool = True,
                  ) -> plt.Figure:

    n_scenarios = len(scenarios)
    fig = plt.figure(figsize=(14, 4 * n_scenarios))
    gs = GridSpec(n_scenarios, 3, figure=fig, hspace=0.5, wspace=0.35)

    col_titles = ['Current [A]', 'Temperature [°C]', 'Power']

    for row, (v_start, v_end, label) in enumerate(scenarios):
        df = all_results[label]

        axes = [fig.add_subplot(gs[row, col]) for col in range(3)]

        # current
        axes[0].plot(df.index, df['master_current_A']-df['master_set_current_A'],
                    color='steelblue', label='master')
        axes[0].plot(df.index, df['amplif_current_A']-df['amplif_set_current_A'],
                    color='tomato', label='amplif', linestyle='--')
        axes[0].axhline(0, color='black', linewidth=0.8, linestyle='-')

        # temperature
        axes[1].plot(df.index, df['master_temperature_C']-df['master_set_temperature_C'],
                    color='steelblue', label='master')
        axes[1].plot(df.index, df['amplif_temperature_C']-df['amplif_set_temperature_C'],
                    color='tomato', label='amplif', linestyle='--')
        axes[1].axhline(0, color='black', linewidth=0.8, linestyle='-')

        # power
        axes[2].plot(df.index, df['master_power'],
                    color='steelblue', label='master')
        axes[2].plot(df.index, df['amplif_power'],
                    color='tomato', label='amplif', linestyle='--')

        for col, ax in enumerate(axes):
            ax.set_xlabel('time [s]')
            ax.legend(fontsize=8)
            ax.grid(True, linestyle=':', alpha=0.6)
            if col == 0:
                ax.set_ylabel(f"{label}\n\n{col_titles[col]}", fontsize=9)
            else:
                ax.set_ylabel(col_titles[col], fontsize=9)
            if row == 0:
                ax.set_title(col_titles[col], fontsize=10)

    fig.suptitle('Laser settling after piezo step', fontsize=13, y=1.01)
    plt.tight_layout()

    if save_path: 
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"{tc.GREEN}Plot gespeichert: {save_path}{tc.RESET}")

    print(f"{tc.YELLOW2}-------- Close Figure to continue -------- {tc.RESET}")
    plt.show(block=True)
    # plt.pause(1)
    # plt.close(fig)
    pass


def plot_warmup(df: pd.DataFrame,
                save_path: str = None,
                show: bool = True,
                ) -> plt.Figure:
    '''Plot laser warmup: current drift and temperature drift over time.'''
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    fig = plt.figure(figsize=(14, 8))
    gs  = GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    axes = [fig.add_subplot(gs[row, col]) 
            for row in range(2) for col in range(3)]

    # --- Daten vorbereiten ---
    time_s = df.index

    plots = [
        # (title, y_master, y_amplif, ylabel, nulllinie)
        ("Current [A]",
        df['master_current_A'],
        df['amplif_current_A'],
        "Current [A]", False),

        ("Temperature [°C]",
        df['master_temperature_C'],
        df['amplif_temperature_C'],
        "Temperature [°C]", False),

        ("Power",
        df['master_power'],
        df['amplif_power'],
        "Power", False),

        ("Current drift (Ist - Soll) [A]",
        df['master_current_A'] - df['master_set_current_A'],
        df['amplif_current_A'] - df['amplif_set_current_A'],
        "Drift [A]", True),

        ("Temperature drift (Ist - Soll) [°C]",
        df['master_temperature_C'] - df['master_set_temperature_C'],
        df['amplif_temperature_C'] - df['amplif_set_temperature_C'],
        "Drift [°C]", True),
    ]

    for ax, (title, y_master, y_amplif, ylabel, nulllinie) in zip(axes, plots):
        ax.plot(time_s, y_master,
                color='steelblue', linewidth=1.2, label='master')
        ax.plot(time_s, y_amplif,
                color='tomato', linewidth=1.2, linestyle='--', label='amplif')
        if nulllinie:
            ax.axhline(0, color='black', linewidth=0.8, linestyle='-')
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("time [s]", fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.6)

    # sechsten Subplot ausblenden (nur 5 Plots)
    axes[5].set_visible(False)

    fig.suptitle("Laser Warmup", fontsize=13, fontweight='bold')
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"{tc.GREEN}Plot gespeichert: {save_path}{tc.RESET}")

    plt.show(block=True)
    # plt.pause(0.5)
    # plt.close(fig)
    pass


def plot_drift_monitor(df: pd.DataFrame,
                        save_path: str = None,
                        show: bool = True,
                        ) -> plt.Figure:
    '''Plot drift monitor results: wavelength, drift, temperature and current over time.'''
    
    fig = plt.figure(figsize=(14, 12))
    gs  = GridSpec(4, 2, figure=fig, hspace=0.45, wspace=0.35)

    ax_wl_abs  = fig.add_subplot(gs[0, :])   # volle Breite – absolute Wellenlänge
    ax_wl_drift = fig.add_subplot(gs[1, :])  # volle Breite – Drift in pm
    ax_temp_m  = fig.add_subplot(gs[2, 0])
    ax_temp_a  = fig.add_subplot(gs[2, 1])
    ax_curr_m  = fig.add_subplot(gs[3, 0])
    ax_curr_a  = fig.add_subplot(gs[3, 1])

    time_s     = df.index
    wl_nm      = df['wavelength_m'] * 1e9
    wl_pm_drift = (wl_nm - wl_nm.mean()) * 1e3
    drift_range = wl_pm_drift.max() - wl_pm_drift.min()
    drift_std   = wl_pm_drift.std()

    # --- absolute Wellenlänge ---
    ax_wl_abs.plot(time_s, wl_nm,
                color='tab:blue', linewidth=1.2, label='λ [nm]')
    ax_wl_abs.set_ylabel("Wellenlänge [nm]", fontsize=10)
    ax_wl_abs.set_xlabel("Zeit [s]", fontsize=10)
    ax_wl_abs.set_title("Absolute Wellenlänge", fontsize=11)
    ax_wl_abs.grid(True, linestyle='--', alpha=0.4)
    ax_wl_abs.legend(fontsize=9)

    # --- Drift in pm ---
    ax_wl_drift.plot(time_s, wl_pm_drift,
                    color='tab:red', linewidth=1.2, label='Drift [pm]')
    ax_wl_drift.axhline(0, color='black', linewidth=0.8, linestyle=':')

    # Zeeman-Aufspaltung als Referenz einzeichnen
    ax_wl_drift.axhline( 2.08, color='gray', linewidth=0.8,
                        linestyle='--', alpha=0.6, label='±Δλ_Z = 2.08 pm')
    ax_wl_drift.axhline(-2.08, color='gray', linewidth=0.8,
                        linestyle='--', alpha=0.6)

    ax_wl_drift.set_ylabel("Drift vom Mittelwert [pm]", fontsize=10)
    ax_wl_drift.set_xlabel("Zeit [s]", fontsize=10)
    ax_wl_drift.set_title("Wellenlängen-Drift", fontsize=11)
    ax_wl_drift.grid(True, linestyle='--', alpha=0.4)
    ax_wl_drift.legend(fontsize=9)
    ax_wl_drift.text(
        0.99, 0.95,
        f"Drift range: {drift_range:.2f} pm\n"
        f"Drift std:   {drift_std:.2f} pm\n"
        f"Zeeman Δλ:   2.08 pm",
        transform=ax_wl_drift.transAxes,
        fontsize=9, ha='right', va='top',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
    )

    # --- Master Temperatur ---
    t_master = df['master_temperature_C']
    t_m_range = (t_master.max() - t_master.min()) * 1e3
    ax_temp_m.plot(time_s, t_master,
                color='steelblue', linewidth=1.2)
    ax_temp_m.set_title("Master Temperatur", fontsize=10)
    ax_temp_m.set_xlabel("Zeit [s]", fontsize=9)
    ax_temp_m.set_ylabel("Temperatur [°C]", fontsize=9)
    ax_temp_m.grid(True, linestyle='--', alpha=0.4)
    ax_temp_m.text(
        0.97, 0.97, f"Δ = {t_m_range:.1f} mK",
        transform=ax_temp_m.transAxes,
        fontsize=9, ha='right', va='top',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
    )

    # --- Amplifier Temperatur ---
    t_amplif  = df['amplif_temperature_C']
    t_a_range = (t_amplif.max() - t_amplif.min()) * 1e3
    ax_temp_a.plot(time_s, t_amplif,
                color='tomato', linewidth=1.2)
    ax_temp_a.set_title("Amplifier Temperatur", fontsize=10)
    ax_temp_a.set_xlabel("Zeit [s]", fontsize=9)
    ax_temp_a.set_ylabel("Temperatur [°C]", fontsize=9)
    ax_temp_a.grid(True, linestyle='--', alpha=0.4)
    ax_temp_a.text(
        0.97, 0.97, f"Δ = {t_a_range:.1f} mK",
        transform=ax_temp_a.transAxes,
        fontsize=9, ha='right', va='top',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
    )

    # --- Master Strom ---
    ax_curr_m.plot(time_s, df['master_current_A'] * 1e3,
                color='steelblue', linewidth=1.2)
    ax_curr_m.set_title("Master Strom", fontsize=10)
    ax_curr_m.set_xlabel("Zeit [s]", fontsize=9)
    ax_curr_m.set_ylabel("Strom [mA]", fontsize=9)
    ax_curr_m.grid(True, linestyle='--', alpha=0.4)

    # --- Amplifier Strom ---
    ax_curr_a.plot(time_s, df['amplif_current_A'] * 1e3,
                color='tomato', linewidth=1.2)
    ax_curr_a.set_title("Amplifier Strom", fontsize=10)
    ax_curr_a.set_xlabel("Zeit [s]", fontsize=9)
    ax_curr_a.set_ylabel("Strom [mA]", fontsize=9)
    ax_curr_a.grid(True, linestyle='--', alpha=0.4)

    fig.suptitle(
        f"Drift Monitor – {df.index[-1]:.0f} s  |  "
        f"{len(df)} Messungen  |  "
        f"Interval: {df.index[1]-df.index[0]:.1f} s",
        fontsize=13, fontweight='bold'
    )
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"{tc.GREEN}Plot gespeichert: {save_path}{tc.RESET}")

    plt.show(block=True)
    # plt.pause(0.5)
    # plt.close(fig)
    pass


def plot_tuning_rates(df: pd.DataFrame,
                       df_mean: pd.DataFrame,
                       current_step_mA: float = 10.0,
                       save_path: str = None,
                       show: bool = True,
                       ) -> plt.Figure:
    '''Plot results of measure_tuning_rates().'''
    
    fig = plt.figure(figsize=(14, 9))
    gs  = GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

    ax_main  = fig.add_subplot(gs[0, :])   # λ vs. Strom – volle Breite
    ax_piezo = fig.add_subplot(gs[1, 0])   # Piezo-Rate vs. Strom
    ax_resid = fig.add_subplot(gs[1, 1])   # Residuen vom linearen Fit

    # Farben für Piezo-Punkte
    colors = cm.coolwarm(np.linspace(0, 1, len(df['piezo_V'].unique())))
    piezo_vals = sorted(df['piezo_V'].unique())

    # --- Hauptplot: λ vs. Strom ---
    for col, v in zip(colors, piezo_vals):
        df_v = df[df['piezo_V'] == v]
        ax_main.plot(df_v['current_mA'],
                    df_v['wl_mean_m'] * 1e9,
                    'o-', color=col, markersize=4,
                    linewidth=1.0, alpha=0.8,
                    label=f'Piezo = {v:.0f} V')

    # Mittelwert + linearer Fit
    ax_main.plot(df_mean['current_mA'],
                df_mean['wl_mean_m'] * 1e9,
                's--', color='black', markersize=5,
                linewidth=1.5, label='Mittelwert')

    if len(df_mean) >= 2:
        coeffs = np.polyfit(df_mean['current_mA'].values,
                            df_mean['wl_mean_m'].values, 1)
        i_fit  = np.linspace(df_mean['current_mA'].min(),
                            df_mean['current_mA'].max(), 100)
        wl_fit = np.polyval(coeffs, i_fit) * 1e9
        ax_main.plot(i_fit, wl_fit,
                    '-', color='tab:red', linewidth=1.5,
                    alpha=0.7, label='Linearer Fit')

        rate_pm_per_mA = coeffs[0] * 1e12
        ax_main.text(
            0.97, 0.05,
            f"Abstimmrate: {rate_pm_per_mA:.3f} pm/mA\n"
            f"             {rate_pm_per_mA*1e3/1e9*1e9:.4f} nm/A",
            transform=ax_main.transAxes,
            fontsize=9, ha='right', va='bottom',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

        # Referenzlinie 667.91 nm
        ax_main.axhline(667.91, color='gray', linewidth=0.8,
                        linestyle=':', label='667.91 nm (Ziel)')

    ax_main.set_xlabel("Master-Strom [mA]", fontsize=11)
    ax_main.set_ylabel("Wellenlänge [nm]", fontsize=11)
    ax_main.set_title("Abstimmkurve: λ vs. Master-Strom", fontsize=11)
    ax_main.legend(fontsize=8, loc='upper left')
    ax_main.grid(True, linestyle='--', alpha=0.4)

    # --- Piezo-Rate vs. Strom ---
    piezo_rates = []
    for i_mA, grp in df.groupby('current_mA'):
        if len(grp) >= 2:
            dv  = grp['piezo_V'].iloc[-1] - grp['piezo_V'].iloc[0]
            dwl = grp['wl_mean_m'].iloc[-1] - grp['wl_mean_m'].iloc[0]
            piezo_rates.append({
                'current_mA': i_mA,
                'rate_pm_per_V': dwl / dv * 1e12 if dv != 0 else np.nan
            })

    if piezo_rates:
        df_pr = pd.DataFrame(piezo_rates)
        ax_piezo.plot(df_pr['current_mA'], df_pr['rate_pm_per_V'],
                    'o-', color='tab:blue', markersize=5, linewidth=1.2)
        ax_piezo.axhline(df_pr['rate_pm_per_V'].mean(),
                        color='tab:red', linewidth=0.8, linestyle='--',
                        label=f"Mittel: {df_pr['rate_pm_per_V'].mean():.3f} pm/V")
        ax_piezo.set_xlabel("Master-Strom [mA]", fontsize=10)
        ax_piezo.set_ylabel("Piezo-Rate [pm/V]", fontsize=10)
        ax_piezo.set_title("Piezo-Abstimmrate vs. Strom", fontsize=10)
        ax_piezo.legend(fontsize=8)
        ax_piezo.grid(True, linestyle='--', alpha=0.4)

    # --- Residuen ---
    if len(df_mean) >= 2:
        wl_fit_at_points = np.polyval(coeffs, df_mean['current_mA'].values)
        residuals_pm = (df_mean['wl_mean_m'].values - wl_fit_at_points) * 1e12
        ax_resid.bar(df_mean['current_mA'].values, residuals_pm,
                    width=current_step * 0.6
                    if (current_step := df_mean['current_mA'].diff().median()) > 0
                    else 1.0,
                    color='tab:blue', alpha=0.7)
        ax_resid.axhline(0, color='black', linewidth=0.8)
        ax_resid.set_xlabel("Master-Strom [mA]", fontsize=10)
        ax_resid.set_ylabel("Residuen [pm]", fontsize=10)
        ax_resid.set_title("Residuen vom linearen Fit", fontsize=10)
        ax_resid.grid(True, linestyle='--', alpha=0.4)

    fig.suptitle("Abstimmraten-Messung Master-Laser",
                fontsize=13, fontweight='bold')
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"{tc.GREEN}Plot gespeichert: {save_path}{tc.RESET}")

    plt.show(block=True)
    # plt.pause(0.5)
    # plt.close(fig)
    pass


def plot_piezo_resolution(results: dict,
                           v_steps: list,
                           save_path: str = None,
                           show: bool = True,
                           ) -> plt.Figure:
    '''Plot results of test_piezo_resolution().'''
    
    n_res   = len(results["resolution"])
    n_scans = len(results["reproducibility"])

    fig = plt.figure(figsize=(14, 5 + 4 * n_res))
    gs  = GridSpec(n_res + 1, 2, figure=fig,
                hspace=0.5, wspace=0.35)

    # --- Test A: Auflösung – eine Zeile pro v_step ---
    for row, (v_step, df) in enumerate(results["resolution"].items()):
        ax_wl  = fig.add_subplot(gs[row, 0])
        ax_diff = fig.add_subplot(gs[row, 1])

        wl_nm = df['wl_mean_m'] * 1e9
        err_nm = df['wl_std_m'] * 1e9

        # Wellenlänge vs. Piezo
        ax_wl.errorbar(df['piezo_V'], wl_nm, yerr=err_nm,
                    fmt='o-', color='tab:blue',
                    markersize=3, linewidth=1.0,
                    capsize=2, elinewidth=0.6)
        ax_wl.set_title(f"Auflösung: v_step = {v_step} V", fontsize=9)
        ax_wl.set_xlabel("Piezo [V]", fontsize=8)
        ax_wl.set_ylabel("λ [nm]", fontsize=8)
        ax_wl.grid(True, linestyle='--', alpha=0.4)

        # Differenz zwischen aufeinanderfolgenden Punkten
        wl_diff_pm = np.diff(wl_nm.values) * 1e3
        noise_pm   = err_nm.mean() * 1e3
        ax_diff.bar(range(len(wl_diff_pm)), wl_diff_pm,
                    color=['tab:green' if abs(d) > 3 * noise_pm
                        else 'tab:red'
                        for d in wl_diff_pm],
                    width=0.8, alpha=0.8)
        ax_diff.axhline(3 * noise_pm,  color='gray',
                        linewidth=0.8, linestyle='--',
                        label=f'3σ = {3*noise_pm:.3f} pm')
        ax_diff.axhline(-3 * noise_pm, color='gray',
                        linewidth=0.8, linestyle='--')
        ax_diff.axhline(0, color='black', linewidth=0.5)
        ax_diff.set_title(f"Δλ pro Schritt (grün = auflösbar)", fontsize=9)
        ax_diff.set_xlabel("Schritt-Index", fontsize=8)
        ax_diff.set_ylabel("Δλ [pm]", fontsize=8)
        ax_diff.legend(fontsize=7)
        ax_diff.grid(True, linestyle='--', alpha=0.4)

    # --- Test B: Reproduzierbarkeit ---
    ax_repro  = fig.add_subplot(gs[n_res, 0])
    ax_hyst   = fig.add_subplot(gs[n_res, 1])

    colors = cm.tab10(np.linspace(0, 1, n_scans))

    for i, df_scan in enumerate(results["reproducibility"]):
        df_fwd = df_scan[df_scan['direction'] == 'forward']
        df_bwd = df_scan[df_scan['direction'] == 'backward']

        ax_repro.plot(df_fwd['piezo_V'], df_fwd['wl_mean_m'] * 1e9,
                    'o-', color=colors[i], markersize=3,
                    linewidth=1.0, label=f'Scan {i+1} →')
        ax_repro.plot(df_bwd['piezo_V'], df_bwd['wl_mean_m'] * 1e9,
                    's--', color=colors[i], markersize=3,
                    linewidth=0.8, alpha=0.6, label=f'Scan {i+1} ←')

        # Hysterese
        df_f = df_fwd.set_index('piezo_V')
        df_b = df_bwd.set_index('piezo_V')
        common = df_f.index.intersection(df_b.index)
        if len(common) > 0:
            hyst_pm = (df_f.loc[common, 'wl_mean_m'].values -
                    df_b.loc[common, 'wl_mean_m'].values) * 1e12
            ax_hyst.plot(common, hyst_pm,
                        'o-', color=colors[i], markersize=3,
                        linewidth=1.0, label=f'Scan {i+1}')

    ax_repro.set_title("Reproduzierbarkeit: Hin- und Rückweg", fontsize=10)
    ax_repro.set_xlabel("Piezo [V]", fontsize=9)
    ax_repro.set_ylabel("λ [nm]", fontsize=9)
    ax_repro.legend(fontsize=7, ncol=2)
    ax_repro.grid(True, linestyle='--', alpha=0.4)

    ax_hyst.axhline(0, color='black', linewidth=0.8, linestyle='-')
    ax_hyst.set_title("Hysterese (Vorwärts − Rückwärts) [pm]", fontsize=10)
    ax_hyst.set_xlabel("Piezo [V]", fontsize=9)
    ax_hyst.set_ylabel("Δλ [pm]", fontsize=9)
    ax_hyst.legend(fontsize=7)
    ax_hyst.grid(True, linestyle='--', alpha=0.4)

    fig.suptitle("Piezo Auflösung & Reproduzierbarkeit",
                fontsize=13, fontweight='bold')
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"{tc.GREEN}Plot gespeichert: {save_path}{tc.RESET}")

    plt.show(block=True)
    # plt.pause(0.5)
    # plt.close(fig)
    pass


def plot_characterization(df: pd.DataFrame,
                           CURRENT_STEP_MA: float = 5.0,
                           save_path: str = None,
                           show: bool = True,
                           ) -> plt.Figure:
    '''
    λ vs. Piezo-Spannung für alle Ströme.
    Farbe = Master-Strom [mA].
    '''
    i_values = sorted(df['current_mA'].unique())
    n        = len(i_values)

    # Farbskala: gleichmäßig über volle Colormap
    colors = cm.plasma(np.linspace(0, 1, n))

    fig, ax = plt.subplots(figsize=(11, 7))

    for col, i_mA in zip(colors, i_values):
        df_i = df[df['current_mA'] == i_mA].copy()

        # nach Piezo sortieren für saubere Linie
        df_i = df_i.sort_values('master_piezo_off_set_V')

        wl_nm     = df_i['wl_mean_m'] * 1e9
        wl_err_nm = df_i['wl_std_m']  * 1e9
        piezo     = df_i['master_piezo_off_set_V']

        ax.errorbar(
            piezo, wl_nm,
            yerr      = wl_err_nm,
            fmt       = 'o-',
            color     = col,
            markersize= 4,
            linewidth = 1.3,
            capsize   = 2,
            capthick  = 0.8,
            elinewidth= 0.6,
            label     = f"{i_mA:.0f} mA",
            alpha     = 0.9,
        )

    # Colorbar als zweite Legende
    sm = plt.cm.ScalarMappable(
        cmap  = cm.plasma,
        norm  = plt.Normalize(vmin=i_values[0], vmax=i_values[-1])
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.01)
    cbar.set_label("Master-Strom [mA]", fontsize=11)
    cbar.set_ticks(i_values)

    ax.set_xlabel("Piezo-Spannung [V]", fontsize=12)
    ax.set_ylabel("Wellenlänge [nm]",   fontsize=12)
    ax.set_title(
        f"Laser-Charakterisierung: λ vs. Piezo\n"
        f"Master-Strom {i_values[0]:.0f}–{i_values[-1]:.0f} mA, "
        f"Schritt {CURRENT_STEP_MA:.0f} mA",
        fontsize=12, fontweight='bold'
    )
    ax.grid(True, linestyle='--', alpha=0.4)

    # Abstimmrate als Textbox (aus erstem und letztem Scan)
    df_mid = df[df['current_mA'] == i_values[len(i_values)//2]].sort_values(
        'master_piezo_off_set_V')
    if len(df_mid) >= 2:
        dv   = df_mid['master_piezo_off_set_V'].iloc[-1] - \
               df_mid['master_piezo_off_set_V'].iloc[0]
        dwl  = (df_mid['wl_mean_m'].iloc[-1] - \
                df_mid['wl_mean_m'].iloc[0]) * 1e12
        rate = dwl / dv if dv != 0 else 0
        ax.text(
            0.02, 0.97,
            f"Piezo-Rate ≈ {rate:.2f} pm/V\n"
            f"(bei {i_values[len(i_values)//2]:.0f} mA)",
            transform = ax.transAxes,
            fontsize  = 9,
            va        = 'top',
            bbox      = dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot gespeichert: {save_path}")

    if show: 
        plt.show(block=True)
    # plt.pause(0.5)
    # plt.close(fig)
    pass

def plot_characterization_wl_c(df: pd.DataFrame,
                           CURRENT_STEP_MA: float = 5.0,
                           save_path: str = None,
                           show: bool = True,
                           ) -> plt.Figure:
    '''
    λ vs. Master-Strom [mA].
    Farbe = Piezo-Spannung [V].
    '''
    piezo_values = sorted(df['master_piezo_off_set_V'].unique())
    n            = len(piezo_values)

    # Farbskala: gleichmäßig über volle Colormap
    colors = cm.plasma(np.linspace(0, 1, n))

    fig, ax = plt.subplots(figsize=(11, 7))

    for col, v in zip(colors, piezo_values):
        df_v = df[df['master_piezo_off_set_V'] == v].copy()
        df_v = df_v.sort_values('current_mA')

        wl_nm     = df_v['wl_mean_m'] * 1e9
        wl_err_nm = df_v['wl_std_m']  * 1e9
        current   = df_v['current_mA']

        ax.errorbar(
            current, wl_nm,
            yerr       = wl_err_nm,
            fmt        = 'o-',
            color      = col,
            markersize = 4,
            linewidth  = 1.3,
            capsize    = 2,
            capthick   = 0.8,
            elinewidth = 0.6,
            label      = f"{v:.1f} V",
            alpha      = 0.9,
        )

    # --- Lineare Fits pro Piezo-Spannung ---
    fit_rates = []
    for col, v in zip(colors, piezo_values):
        df_v = df[df['master_piezo_off_set_V'] == v].sort_values('current_mA')
        if len(df_v) < 2:
            continue

        x = df_v['current_mA'].values
        y = df_v['wl_mean_m'].values * 1e9

        coeffs = np.polyfit(x, y, 1)
        x_fit  = np.linspace(x.min(), x.max(), 100)
        y_fit  = np.polyval(coeffs, x_fit)

        ax.plot(x_fit, y_fit,
                color     = col,
                linewidth = 0.8,
                linestyle = '--',
                alpha     = 0.6,
                zorder    = 1)    # hinter den Datenpunkten

        fit_rates.append({
            'piezo_V':      v,
            'rate_pm_per_mA': coeffs[0] * 1e3,   # nm/mA → pm/mA
        })

    # Abstimmraten aller Fits als Textbox
    if fit_rates:
        rate_mean = np.mean([r['rate_pm_per_mA'] for r in fit_rates])
        rate_std  = np.std( [r['rate_pm_per_mA'] for r in fit_rates])
        ax.text(
            0.02, 0.97,
            f"Strom-Abstimmrate (lin. Fit):\n"
            f"  Mittel: {rate_mean:.3f} pm/mA\n"
            f"  Std:    {rate_std:.3f} pm/mA",
            transform = ax.transAxes,
            fontsize  = 9,
            va        = 'top',
            bbox      = dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

    # Colorbar
    sm = plt.cm.ScalarMappable(
        cmap = cm.plasma,
        norm = plt.Normalize(vmin=piezo_values[0], vmax=piezo_values[-1])
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.01)
    cbar.set_label("Piezo-Spannung [V]", fontsize=11)
    cbar.set_ticks(piezo_values[::2] if len(piezo_values) > 8
                   else piezo_values)

    ax.set_xlabel("Master-Strom [mA]", fontsize=12)
    ax.set_ylabel("Wellenlänge [nm]",  fontsize=12)
    ax.set_title(
        f"Laser-Charakterisierung: λ vs. Master-Strom\n"
        f"Piezo {piezo_values[0]:.1f}–{piezo_values[-1]:.1f} V, "
        f"Strom-Schritt {CURRENT_STEP_MA:.0f} mA",
        fontsize=12, fontweight='bold'
    )
    ax.grid(True, linestyle='--', alpha=0.4)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot gespeichert: {save_path}")

    if show:
        plt.show(block=True)
    # plt.close(fig)
    pass

def plot_characterization_wl_temp(df: pd.DataFrame, 
                                 save_path: str = None, 
                                 show: bool = True) -> plt.Figure:
    '''
    λ vs. Master-Temperatur [°C].
    Farbe = Piezo-Spannung [V].
    '''
    fit_rates = []
    
    piezo_values = sorted(df['master_piezo_off_set_V'].unique())
    n = len(piezo_values)
    colors = cm.plasma(np.linspace(0, 1, n))
    fig, ax = plt.subplots(figsize=(11, 7))
    
    for col, v in zip(colors, piezo_values):
        # Daten für diese spezifische Piezo-Spannung filtern und nach Temperatur sortieren
        df_v = df[df['master_piezo_off_set_V'] == v].copy()
        df_v = df_v.sort_values('master_temperature_C')
        
        if df_v.empty:
            continue
            
        wl_nm     = df_v['wl_mean_m'] * 1e9
        wl_err_nm = df_v['wl_std_m']  * 1e9
        temp      = df_v['master_temperature_C']
        
        ax.errorbar(
            temp, wl_nm,
            yerr       = wl_err_nm,
            fmt        = 'o-',
            color      = col,
            markersize = 4,
            linewidth  = 1.3,
            capsize    = 2,
            capthick   = 0.8,
            elinewidth = 0.6,
            label      = f"{v:.1f} V",
            alpha      = 0.9,
        )
        
        # --- Lineare Fits pro Piezo-Spannung (Temperaturkoeffizient) ---
        if len(df_v) >= 2:
            x = df_v['master_temperature_C'].values
            y = df_v['wl_mean_m'].values * 1e9
            
            coeffs = np.polyfit(x, y, 1)
            x_fit  = np.linspace(x.min(), x.max(), 100)
            y_fit  = np.polyval(coeffs, x_fit)
            
            ax.plot(x_fit, y_fit,
                    color     = col,
                    linewidth = 0.8,
                    linestyle = '--',
                    alpha     = 0.6,
                    zorder    = 1)
            
            # Wir speichern die Rate in pm/K (pm/°C)
            fit_rates.append({
                'piezo_V':      v,
                'rate_pm_per_K': coeffs[0] * 1e3, # nm/K -> pm/K
            })

    if fit_rates:
        rates = [r['rate_pm_per_K'] for r in fit_rates]
        rate_mean = np.mean(rates)
        rate_std  = np.std(rates)
        ax.text(
            0.02, 0.97,
            f"Temp-Abstimmrate (lin. Fit):\n"
            f"  Mittel: {rate_mean:.3f} pm/K\n"
            f"  Std:    {rate_std:.3f} pm/K",
            transform = ax.transAxes,
            fontsize  = 9,
            va        = 'top',
            bbox      = dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

    # Colorbar
    sm = plt.cm.ScalarMappable(
        cmap = cm.plasma,
        norm = plt.Normalize(vmin=piezo_values[0], vmax=piezo_values[-1])
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.01)
    cbar.set_label("Piezo-Spannung [V]", fontsize=11)
    cbar.set_ticks(piezo_values[::2] if len(piezo_values) > 8 else piezo_values)
    
    ax.set_xlabel("Master-Temperatur [°C]", fontsize=12)
    ax.set_ylabel("Wellenlänge [nm]",  fontsize=12)
    ax.set_title(
        f"Laser-Charakterisierung: λ vs. Master-Temperatur\n"
        f"Piezo {piezo_values[0]:.1f}–{piezo_values[-1]:.1f} V",
        fontsize=12, fontweight='bold'
    )
    ax.grid(True, linestyle='--', alpha=0.4)
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot gespeichert: {save_path}")
        
    if show:
        plt.show(block=True)
        
    pass

def plot_characterization_for_pres(df: pd.DataFrame,
                           CURRENT_STEP_MA: float = 5.0,
                           save_path: str = None,
                           show: bool = True,
                           ) -> plt.Figure:
    '''
    λ vs. Piezo-Spannung für alle Ströme.
    Farbe = Master-Strom [mA].
    '''
    i_values = sorted(df['current_mA'].unique())
    n        = len(i_values)

    # Farbskala: gleichmäßig über volle Colormap
    colors = cm.plasma(np.linspace(0, 1, n))

    fig, ax = plt.subplots(figsize=(11, 7))

    for col, i_mA in zip(colors, i_values):
        df_i = df[df['current_mA'] == i_mA].copy()

        # nach Piezo sortieren für saubere Linie
        df_i = df_i.sort_values('master_piezo_off_set_V')

        wl_nm     = df_i['wl_mean_m'] * 1e9
        wl_err_nm = df_i['wl_std_m']  * 1e9
        piezo     = df_i['master_piezo_off_set_V']

        ax.errorbar(
            piezo, wl_nm,
            yerr      = wl_err_nm,
            fmt       = 'o-',
            color     = col,
            markersize= 4,
            linewidth = 1.3,
            capsize   = 2,
            capthick  = 0.8,
            elinewidth= 0.6,
            label     = f"{i_mA:.0f} mA",
            alpha     = 0.9,
        )

    # Colorbar als zweite Legende
    sm = plt.cm.ScalarMappable(
        cmap  = cm.plasma,
        norm  = plt.Normalize(vmin=i_values[0], vmax=i_values[-1])
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.01)
    cbar.set_label("Master-Strom [mA]", fontsize=11)
    cbar.set_ticks(i_values)

    ax.set_xlabel("Piezo-Spannung [V]", fontsize=12)
    ax.set_ylabel("Wellenlänge [nm]",   fontsize=12)
    ax.set_title(
        f"Laser-Charakterisierung: λ vs. Piezo\n"
        f"Master-Strom {i_values[0]:.0f}–{i_values[-1]:.0f} mA, "
        f"Schritt {CURRENT_STEP_MA:.0f} mA",
        fontsize=12, fontweight='bold'
    )
    ax.grid(True, linestyle='--', alpha=0.4)

    # Abstimmrate als Textbox (aus erstem und letztem Scan)
    df_mid = df[df['current_mA'] == i_values[len(i_values)//2]].sort_values(
        'master_piezo_off_set_V')
    if len(df_mid) >= 2:
        dv   = df_mid['master_piezo_off_set_V'].iloc[-1] - \
               df_mid['master_piezo_off_set_V'].iloc[0]
        dwl  = (df_mid['wl_mean_m'].iloc[-1] - \
                df_mid['wl_mean_m'].iloc[0]) * 1e12
        rate = dwl / dv if dv != 0 else 0
        ax.text(
            0.02, 0.8,
            f"Piezo-Rate ≈ {rate:.2f} pm/V\n"
            f"(bei {i_values[len(i_values)//2]:.0f} mA)",
            transform = ax.transAxes,
            fontsize  = 9,
            va        = 'top',
            bbox      = dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

    # --- Referenzlinien Argon ---
    ax.axhline(667.91, color='black', linewidth=1.5,
               linestyle='--', alpha=1.0,
               label='Ar I  667.91 nm')
    ax.axhline(668.40, color='black', linewidth=1.5,
               linestyle='--', alpha=1.0,
               label='Ar II 668.40 nm')

    # Beschriftungen rechts an der Y-Achse
    ax.text(
        0.1, 667.91,
        'Ar I\n667.91 nm',
        transform     = ax.get_yaxis_transform(),
        fontsize      = 12,
        va            = 'center',
        color         = 'black',
        alpha         = 1.0,
    )
    ax.text(
        0.1, 668.40,
        'Ar II\n668.40 nm',
        transform     = ax.get_yaxis_transform(),
        fontsize      = 12,
        va            = 'center',
        color         = 'black',
        alpha         = 1.0,
    )

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot gespeichert: {save_path}")

    if show:
        plt.show(block=True)
    # plt.close(fig)
    pass

def plot_temperature_settling(all_results: dict,
                             scenarios: list,
                             save_path: str = None,
                             show: bool = True,
                             ) -> plt.Figure:
    '''
    Plotten des Settling-Verhaltens nach einem Temperatursprung.
    Erwartet ein Dictionary all_results, in dem die Keys die Labels der Szenarien sind.
    '''
    n_scenarios = len(scenarios)
    fig = plt.figure(figsize=(14, 4 * n_scenarios))
    gs = GridSpec(n_scenarios, 3, figure=fig, hspace=0.5, wspace=0.35)
    
    col_titles = ['Current [A]', 'Temperature [°C]', 'Power']
    
    for row, (t_start, t_end, label) in enumerate(scenarios):
        # Zugriff auf den DataFrame über das Label (verhindert den KeyError)
        df = all_results[label]
        
        axes = [fig.add_subplot(gs[row, col]) for col in range(3)]
        
        # 1. Strom-Abweichung (Ist - Soll)
        axes[0].plot(df.index, df['master_current_A'] - df['master_set_current_A'],
                     color='steelblue', label='master')
        axes[0].plot(df.index, df['amplif_current_A'] - df['amplif_set_current_A'],
                     color='tomato', label='amplif', linestyle='--')
        axes[0].axhline(0, color='black', linewidth=0.8, linestyle='-')
        
        # 2. Temperatur-Abweichung (Ist - Soll)
        axes[1].plot(df.index, df['master_temperature_C'] - df['master_set_temperature_C'],
                     color='steelblue', label='master')
        axes[1].plot(df.index, df['amplif_temperature_C'] - df['amplif_set_temperature_C'],
                     color='tomato', label='amplif', linestyle='--')
        axes[1].axhline(0, color='black', linewidth=0.8, linestyle='-')
        
        # 3. Absolute Leistung
        axes[2].plot(df.index, df['master_power'],
                     color='steelblue', label='master')
        axes[2].plot(df.index, df['amplif_power'],
                     color='tomato', label='amplif', linestyle='--')
        
        for col, ax in enumerate(axes):
            ax.set_xlabel('time [s]')
            ax.legend(fontsize=8)
            ax.grid(True, linestyle=':', alpha=0.6)
            if col == 0:
                ax.set_ylabel(f"{label}\n\n{col_titles[col]}", fontsize=9)
            else:
                ax.set_ylabel(col_titles[col], fontsize=9)
            if row == 0:
                ax.set_title(col_titles[col], fontsize=10)
    
    # Titel an Temperatur angepasst
    fig.suptitle('Laser settling after temperature step', fontsize=13, y=1.01)
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        # Nutzt tc für Farben, falls TerminalColours global verfügbar ist
        print(f"{tc.GREEN}Plot gespeichert: {save_path}{tc.RESET}")
    
    print(f"{tc.YELLOW2}-------- Close Figure to continue -------- {tc.RESET}")
    plt.show(block=True)
    
    return fig