"""
LIF Linienprofil-Auswertung: Ar I 667.91 nm / 750.59 mm (4s → 4p' → 4s')
========================================================

Modell: Überlagerung von drei Gaußkurven (Zeeman-Triplett)
  - senkrechte Beobachtung zum B-Feld
  - Intensitätsverhältnis σ- : π : σ+ = 1 : 2 : 1
  - Zeeman-Verschiebung: Δλ_Z = (e * λ² * B) / (4π * m_e * c²)
  - Doppler-Breite: σ_D = (λ₀/c) * sqrt(k_B * T / m_Ar)

Freie Fit-Parameter:
  - T     : Gastemperatur [K]          → aus σ_D
  - A     : Signalamplitude [V]
  - λ_c   : Zentrum der Linie [m]      → leichte Drift möglich
  - offset: Signaluntergrund [V]       → Sicherheit falls Lock-In nicht perfekt

Eingabe: pandas DataFrame aus scan_piezo() mit Spalten
  - wl_mean_m      : Wellenlänge [m]
  - daq_lif_signal_V oder lia_R : Lock-In Signal [V]

Ausgabe:
  - Fit-Parameter mit Unsicherheiten
  - Temperatur mit Fehler
  - Plot mit Messdaten, Fit, Einzelkomponenten

Verwendung:
  from analysis.lif_line_profile import LIFLineProfile
  llp = LIFLineProfile(B_field_T=0.1)
  result = llp.fit(df)
  llp.plot(df, result, save_path="...")
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.constants import k as k_B, c, e, m_e, u
from dataclasses import dataclass
from pathlib import Path
import json
import os
from pathlib import Path

SAVE_PATH = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/2026-04-21_Andrei_LIF/plots_line-profile-analysis")


# ----------------------------------------------------------------
# Physikalische Konstanten für Ar I 667.91 nm
# ----------------------------------------------------------------
LAMBDA_0    = 750.59e-9     # m  Anregungswellenlänge
M_AR        = 39.948 * u    # kg Masse Ar-Atom
G_LANDE     = 1.0           # Lande g-Faktor (g=1 als Näherung, anpassbar)

# Zeeman-Intensitätsverhältnisse bei senkrechter Beobachtung
# σ- : π : σ+ = 1 : 2 : 1  (normiert auf Summe = 4)
ZEEMAN_WEIGHTS = np.array([1.0, 2.0, 1.0]) / 4.0


# ----------------------------------------------------------------
# Dataclass für Fit-Ergebnis
# ----------------------------------------------------------------
@dataclass
class FitResult:
    # Fit-Parameter
    T_K:          float    # Temperatur [K]
    T_K_err:      float    # Unsicherheit Temperatur [K]
    T_C:          float    # Temperatur [°C]
    T_C_err:      float    # Unsicherheit Temperatur [°C]
    amplitude:    float    # Signalamplitude [V]
    amplitude_err:float
    lambda_c_m:   float    # Linienzentrum [m]
    lambda_c_err: float
    offset:       float    # Untergrund [V]
    offset_err:   float
    # Abgeleitete Größen
    sigma_D_m:    float    # Doppler-Breite 1σ [m]
    fwhm_D_pm:    float    # Doppler FWHM [pm]
    delta_Z_pm:   float    # Zeeman-Verschiebung [pm]
    # Fit-Qualität
    chi2_reduced: float    # reduziertes χ²
    r_squared:    float    # R²
    n_points:     int      # Anzahl Datenpunkte
    success:      bool     # Fit erfolgreich?
    message:      str      # Statusmeldung


# ----------------------------------------------------------------
# Hauptklasse
# ----------------------------------------------------------------
class LIFLineProfile:

    def __init__(self,
                 B_field_T:   float = 0.1,
                 g_lande:     float = G_LANDE,
                 lambda_0_m:  float = LAMBDA_0,
                 ):
        """
        Parameters
        ----------
        B_field_T  : Magnetfeldstärke [T]
        g_lande    : Lande g-Faktor (default 1.0, später anpassbar)
        lambda_0_m : Anregungswellenlänge [m]
        """
        self.B          = B_field_T
        self.g          = g_lande
        self.lambda_0   = lambda_0_m

        # Zeeman-Verschiebung berechnen
        self.delta_Z = self._calc_zeeman_shift()
        print(f"LIFLineProfile: λ₀ = {lambda_0_m*1e9:.4f} nm, "
              f"B = {B_field_T*1e3:.0f} mT, "
              f"Δλ_Z = {self.delta_Z*1e12:.2f} pm")


    def _calc_zeeman_shift(self) -> float:
        """
        Zeeman-Verschiebung der σ-Komponenten von der π-Komponente.
        Schritt 1: Frequenzaufspaltung (normaler Zeeman):
            delta_nu = g * (e * B) / (4π * m_e)
        Schritt 2: Umrechnung in Wellenlänge:
            delta_lambda = (lambda_0² / c) * delta_nu
        Returns: Δλ_Z in Metern
        """
        delta_nu = self.g * (e * self.B) / (4 * np.pi * m_e)
        return (self.lambda_0**2 / c) * delta_nu


    def _sigma_D(self, T_K: float) -> float:
        """
        Doppler-Breite 1σ in Metern.
        σ_D = (λ₀/c) * sqrt(k_B * T / m_Ar)
        """
        return (self.lambda_0 / c) * np.sqrt(k_B * T_K / M_AR)


    def _T_from_sigma(self, sigma_m: float) -> float:
        """
        Temperatur aus Doppler-Breite σ.
        T = (σ * c / λ₀)² * m_Ar / k_B
        """
        return (sigma_m * c / self.lambda_0)**2 * M_AR / k_B


    def model(self, wavelength: np.ndarray,
              T_K: float,
              amplitude: float,
              lambda_c: float,
              offset: float,
              ) -> np.ndarray:
        """
        Zeeman-Triplett Modell: drei Gaußkurven mit gemeinsamer Breite.

        Komponenten:
          σ-: Zentrum = lambda_c - delta_Z,  Gewicht = 1/4
          π:  Zentrum = lambda_c,             Gewicht = 2/4
          σ+: Zentrum = lambda_c + delta_Z,  Gewicht = 1/4

        Parameters
        ----------
        wavelength : Wellenlängen-Array [m]
        T_K        : Temperatur [K]
        amplitude  : Gesamtamplitude [V]
        lambda_c   : Linienzentrum [m]
        offset     : Signaluntergrund [V]
        """
        sigma = self._sigma_D(T_K)
        centers = np.array([
            lambda_c - self.delta_Z,   # σ-
            lambda_c,                  # π
            lambda_c + self.delta_Z,   # σ+
        ])

        signal = np.zeros_like(wavelength, dtype=float)
        for center, weight in zip(centers, ZEEMAN_WEIGHTS):
            signal += weight * np.exp(-0.5 * ((wavelength - center) / sigma)**2)

        return amplitude * signal + offset


    def _estimate_start_params(self,
                                wavelength: np.ndarray,
                                signal: np.ndarray,
                                ) -> tuple:
        """
        Schätzt Startparameter für den Fit aus den Rohdaten.
        Returns: (T_K, amplitude, lambda_c, offset)
        """
        offset_est    = np.percentile(signal, 10)   # untere 10% als Untergrund
        amplitude_est = signal.max() - offset_est
        lambda_c_est  = wavelength[np.argmax(signal)]

        # Starttemperatur: gemessene FWHM des Tripletts korrigieren
        # Das Triplett hat eine effektive FWHM die größer ist als die reine
        # Doppler-FWHM. Für delta_Z >> sigma_D gilt FWHM_eff ≈ 2*delta_Z + FWHM_D
        # → FWHM_D ≈ FWHM_eff - 2*delta_Z (Näherung für Startparameter)
        half_max = offset_est + amplitude_est * 0.5
        above    = wavelength[signal > half_max]
        if len(above) >= 2:
            fwhm_eff  = above[-1] - above[0]
            # Zeeman-Korrektur: ziehe den Zeeman-Anteil ab
            fwhm_D_est = max(fwhm_eff - 2 * self.delta_Z,
                             fwhm_eff * 0.1)   # mindestens 10% der gemessenen Breite
            sigma_est  = fwhm_D_est / (2 * np.sqrt(2 * np.log(2)))
            T_est      = self._T_from_sigma(sigma_est)
            T_est      = np.clip(T_est, 50, 2000)
        else:
            T_est = 500.0   # sicherer Fallback

        return (T_est, amplitude_est, lambda_c_est, offset_est)


    def fit(self,
            df: pd.DataFrame,
            signal_col: str = None,
            wavelength_col: str = 'wl_mean_m',
            ) -> FitResult:
        """
        Fittet das Zeeman-Triplett-Modell an die Messdaten.

        Parameters
        ----------
        df           : DataFrame aus scan_piezo()
        signal_col   : Spaltenname des Lock-In Signals
                       (auto-detect: 'daq_lif_signal_V' oder 'lia_R')
        wavelength_col: Spaltenname der Wellenlänge

        Returns
        -------
        FitResult dataclass
        """
        # --- Signalspalte automatisch erkennen ---
        if signal_col is None:
            for candidate in ['daq_lif_signal_V', 'lia_R', 'lia_X']:
                if candidate in df.columns:
                    signal_col = candidate
                    break
            if signal_col is None:
                raise ValueError(
                    "Keine Lock-In Signalspalte gefunden. "
                    "Erwartet: 'daq_lif_signal_V' oder 'lia_R'. "
                    "Bitte signal_col manuell angeben."
                )
        print(f"LIFLineProfile.fit(): Signal aus Spalte '{signal_col}'")

        # --- Daten vorbereiten ---
        df_valid = df[[wavelength_col, signal_col]].dropna()
        df_valid = df_valid[df_valid[signal_col] > 0]   # nur positive Werte
        df_valid = df_valid.sort_values(wavelength_col)

        if len(df_valid) < 5:
            return FitResult(
                T_K=np.nan, T_K_err=np.nan, T_C=np.nan, T_C_err=np.nan,
                amplitude=np.nan, amplitude_err=np.nan,
                lambda_c_m=np.nan, lambda_c_err=np.nan,
                offset=np.nan, offset_err=np.nan,
                sigma_D_m=np.nan, fwhm_D_pm=np.nan,
                delta_Z_pm=self.delta_Z * 1e12,
                chi2_reduced=np.nan, r_squared=np.nan,
                n_points=len(df_valid), success=False,
                message="Zu wenige Datenpunkte für Fit (< 5)"
            )

        wavelength = df_valid[wavelength_col].values
        signal     = df_valid[signal_col].values

        # --- Startparameter ---
        p0 = self._estimate_start_params(wavelength, signal)
        T0, A0, lc0, off0 = p0
        print(f"  Startparameter: T={T0:.0f} K, A={A0:.4f}, "
              f"λ_c={lc0*1e9:.6f} nm, offset={off0:.4f}")

        # --- Grenzen für den Fit ---
        # T: 50 K bis 2000 K (Plasma bei 1-2 Pa, max ~573 K erwartet)
        # A: positiv
        # λ_c: ±5 pm um Schätzwert (kleines Fenster verhindert Drift ins Falsche)
        # offset: ±0.5*A0
        bounds = (
            [50,    0,    lc0 - 5e-12,  -0.5*abs(A0)],
            [2000,  10*A0, lc0 + 5e-12,  0.5*abs(A0)],
        )

        # --- Multi-Start Fit: verschiedene Starttemperaturen probieren ---
        # Das Modell hat mehrere lokale Minima → bestes Ergebnis wählen
        T_starts = [T0, 300, 400, 500, 573, 800, 1000]
        best_result = None
        best_cost   = np.inf

        for T_start in T_starts:
            try:
                p0_try = (T_start, A0, lc0, off0)
                # Prüfe ob Startpunkt innerhalb der Bounds liegt
                if not (50 <= T_start <= 2000):
                    continue
                popt_try, pcov_try = curve_fit(
                    self.model,
                    wavelength,
                    signal,
                    p0=p0_try,
                    bounds=bounds,
                    maxfev=10000,
                )
                # Kosten berechnen
                residuals_try = signal - self.model(wavelength, *popt_try)
                cost = np.sum(residuals_try**2)
                if cost < best_cost:
                    best_cost   = cost
                    best_result = (popt_try, pcov_try)
            except (RuntimeError, ValueError):
                continue

        if best_result is None:
            return FitResult(
                T_K=np.nan, T_K_err=np.nan, T_C=np.nan, T_C_err=np.nan,
                amplitude=np.nan, amplitude_err=np.nan,
                lambda_c_m=np.nan, lambda_c_err=np.nan,
                offset=np.nan, offset_err=np.nan,
                sigma_D_m=np.nan, fwhm_D_pm=np.nan,
                delta_Z_pm=self.delta_Z * 1e12,
                chi2_reduced=np.nan, r_squared=np.nan,
                n_points=len(df_valid), success=False,
                message="Fit fehlgeschlagen: alle Startpunkte ohne Konvergenz"
            )

        popt, pcov = best_result

        popt, pcov = best_result
        perr    = np.sqrt(np.diag(pcov))
        success = True
        message = "Fit erfolgreich"

        T_K, amplitude, lambda_c, offset = popt
        T_K_err, amp_err, lc_err, off_err = perr

        # --- Fit-Qualität ---
        signal_fit   = self.model(wavelength, *popt)
        residuals    = signal - signal_fit
        ss_res       = np.sum(residuals**2)
        ss_tot       = np.sum((signal - signal.mean())**2)
        r_squared    = 1 - ss_res / ss_tot
        chi2_reduced = ss_res / max(len(signal) - 4, 1)

        # --- Abgeleitete Größen ---
        sigma_D  = self._sigma_D(T_K)
        fwhm_D   = sigma_D * 2 * np.sqrt(2 * np.log(2))

        result = FitResult(
            T_K          = T_K,
            T_K_err      = T_K_err,
            T_C          = T_K - 273.15,
            T_C_err      = T_K_err,
            amplitude    = amplitude,
            amplitude_err= amp_err,
            lambda_c_m   = lambda_c,
            lambda_c_err = lc_err,
            offset       = offset,
            offset_err   = off_err,
            sigma_D_m    = sigma_D,
            fwhm_D_pm    = fwhm_D * 1e12,
            delta_Z_pm   = self.delta_Z * 1e12,
            chi2_reduced = chi2_reduced,
            r_squared    = r_squared,
            n_points     = len(df_valid),
            success      = success,
            message      = message,
        )

        self._print_result(result)
        return result


    def _print_result(self, r: FitResult):
        """Gibt Fit-Ergebnis übersichtlich aus."""
        print(f"\n{'='*50}")
        print(f"  Fit-Ergebnis")
        print(f"{'='*50}")
        if not r.success:
            print(f"  FEHLER: {r.message}")
            return
        print(f"  Temperatur:      {r.T_K:.1f} ± {r.T_K_err:.1f} K")
        print(f"                   {r.T_C:.1f} ± {r.T_C_err:.1f} °C")
        print(f"  Amplitude:       {r.amplitude:.4f} ± {r.amplitude_err:.4f} V")
        print(f"  Linienzentrum:   {r.lambda_c_m*1e9:.6f} ± {r.lambda_c_err*1e12:.3f} pm nm")
        print(f"  Untergrund:      {r.offset:.4f} ± {r.offset_err:.4f} V")
        print(f"  Doppler FWHM:    {r.fwhm_D_pm:.2f} pm")
        print(f"  Zeeman Δλ:       {r.delta_Z_pm:.2f} pm")
        print(f"  R²:              {r.r_squared:.4f}")
        print(f"  χ² (red.):       {r.chi2_reduced:.4e}")
        print(f"  Punkte:          {r.n_points}")
        print(f"{'='*50}\n")


    def plot(self,
             df: pd.DataFrame,
             result: FitResult,
             signal_col: str = None,
             wavelength_col: str = 'wl_mean_m',
             save_path: str = None,
             show: bool = True,
             ):
        """
        Erstellt Plot mit:
          - Messdaten
          - Gesamtfit
          - Drei Zeeman-Komponenten einzeln
          - Residuen
          - Fit-Parameter als Textbox
        """
        # --- Signalspalte erkennen ---
        if signal_col is None:
            for candidate in ['daq_lif_signal_V', 'lia_R', 'lia_X']:
                if candidate in df.columns:
                    signal_col = candidate
                    break

        df_valid = df[[wavelength_col, signal_col]].dropna()
        df_valid = df_valid[df_valid[signal_col] > 0].sort_values(wavelength_col)
        wavelength = df_valid[wavelength_col].values
        signal     = df_valid[signal_col].values

        # Wellenlänge relativ zu λ₀ in pm für lesbare Achse
        wl_pm = (wavelength - self.lambda_0) * 1e12

        # feines Raster für Fit-Kurven
        wl_fine    = np.linspace(wavelength.min(), wavelength.max(), 500)
        wl_fine_pm = (wl_fine - self.lambda_0) * 1e12

        # --- Figure ---
        fig, (ax_main, ax_res) = plt.subplots(
            2, 1, figsize=(10, 7), sharex=True,
            gridspec_kw={"hspace": 0.08, "height_ratios": [3, 1]}
        )

        # --- Hauptplot ---
        ax_main.plot(wl_pm, signal,
                     'o', color='black', markersize=5,
                     label='Messdaten', zorder=5)

        if result.success:
            popt = (result.T_K, result.amplitude,
                    result.lambda_c_m, result.offset)

            # Gesamtfit
            fit_signal = self.model(wl_fine, *popt)
            ax_main.plot(wl_fine_pm, fit_signal,
                         '-', color='tab:red', linewidth=2,
                         label='Zeeman-Triplett Fit', zorder=4)

            # Einzelne Zeeman-Komponenten
            sigma   = self._sigma_D(result.T_K)
            centers = [result.lambda_c_m - self.delta_Z,
                       result.lambda_c_m,
                       result.lambda_c_m + self.delta_Z]
            labels  = ['σ⁻', 'π', 'σ⁺']
            colors  = ['tab:blue', 'tab:green', 'tab:orange']
            weights = ZEEMAN_WEIGHTS

            for center, weight, lbl, col in zip(centers, weights, labels, colors):
                comp = result.amplitude * weight * np.exp(
                    -0.5 * ((wl_fine - center) / sigma)**2)
                ax_main.fill_between(wl_fine_pm, result.offset,
                                     comp + result.offset,
                                     alpha=0.2, color=col, label=lbl)
                ax_main.plot(wl_fine_pm, comp + result.offset,
                             '--', color=col, linewidth=1.0)

            # Zeeman-Positionen markieren
            for center, lbl, col in zip(centers, labels, colors):
                ax_main.axvline((center - self.lambda_0) * 1e12,
                                color=col, linewidth=0.6,
                                linestyle=':', alpha=0.7)

            # Textbox mit Ergebnis
            textstr = (
                f"T = {result.T_K:.0f} ± {result.T_K_err:.0f} K\n"
                f"   = {result.T_C:.0f} ± {result.T_C_err:.0f} °C\n"
                f"FWHM_D = {result.fwhm_D_pm:.2f} pm\n"
                f"Δλ_Z = {result.delta_Z_pm:.2f} pm\n"
                f"R² = {result.r_squared:.4f}"
            )
            ax_main.text(0.97, 0.97, textstr,
                         transform=ax_main.transAxes,
                         fontsize=9, verticalalignment='top',
                         horizontalalignment='right',
                         bbox=dict(boxstyle='round', facecolor='white',
                                   alpha=0.8))

            # --- Residuen ---
            residuals = signal - self.model(wavelength, *popt)
            ax_res.plot(wl_pm, residuals,
                        'o', color='black', markersize=4)
            ax_res.axhline(0, color='tab:red', linewidth=1.0, linestyle='--')
            ax_res.set_ylabel("Residuen [V]", fontsize=9)

        else:
            ax_main.text(0.5, 0.5, f"Fit fehlgeschlagen:\n{result.message}",
                         transform=ax_main.transAxes, ha='center', va='center',
                         color='red', fontsize=11)

        ax_main.set_ylabel(f"Lock-In Signal [{signal_col}]", fontsize=10)
        ax_main.legend(fontsize=9, loc='upper left')
        ax_main.grid(True, linestyle='--', alpha=0.4)

        ax_res.set_xlabel(f"Wellenlänge relativ zu λ₀={self.lambda_0*1e9:.2f} nm  [pm]",
                          fontsize=10)
        ax_res.grid(True, linestyle='--', alpha=0.4)

        fig.suptitle(
            f"Ar I {self.lambda_0*1e9:.2f} nm – Zeeman-Triplett LIF\n"
            f"B = {self.B*1e3:.0f} mT,  g = {self.g:.1f}",
            fontsize=12, fontweight='bold'
        )
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot gespeichert: {save_path}")

        if show:
            plt.show(block=True)
            # plt.pause(0.5)
            # plt.close(fig)
        else:
            plt.close(fig)


    def result_to_dict(self, result: FitResult) -> dict:
        """Konvertiert FitResult in ein Dictionary für file_utils.save_dataframe()."""
        from dataclasses import asdict
        return asdict(result)


# ----------------------------------------------------------------
# Simulierte Testdaten
# ----------------------------------------------------------------
def make_test_data(T_K: float = 500,
                   B_field_T: float = 0.1,
                   noise_level: float = 0.005,
                   n_points: int = 150,
                   scan_range_pm: float = 16.7,
                   ) -> pd.DataFrame:
    """
    Erzeugt simulierte scan_piezo()-ähnliche Daten mit Zeeman-Triplett.
    Nützlich zum Testen der Auswertung ohne echte Messung.

    Scan-Parameter orientieren sich an der physikalischen Realität:
      - Zeeman-Shift bei 100mT: ±2.08 pm
      - Doppler-FWHM bei 300-573K: 1.3-1.8 pm
      - Empfohlener Scan: ±8.3 pm (= 4×Zeeman-Shift), ~150 Punkte

    Parameters
    ----------
    T_K          : simulierte Temperatur [K]
    B_field_T    : Magnetfeld [T]
    noise_level  : Rauschen als Bruchteil der Amplitude
    n_points     : Anzahl Datenpunkte (mind. 100 für gute Auflösung)
    scan_range_pm: Scan-Bereich total um λ₀ [pm] (default 16.7 pm)
    """
    llp = LIFLineProfile(B_field_T=B_field_T)

    wl = np.linspace(
        LAMBDA_0 - scan_range_pm * 0.5e-12,
        LAMBDA_0 + scan_range_pm * 0.5e-12,
        n_points
    )

    # Zigzag-Reihenfolge simulieren (wie scan_piezo)
    wl_zz = np.concatenate([wl[::2], wl[1::2][::-1]])

    signal_clean = llp.model(wl_zz, T_K=T_K, amplitude=1.0,
                              lambda_c=LAMBDA_0, offset=0.01)
    noise  = np.random.normal(0, noise_level, len(wl_zz))
    signal = signal_clean + noise

    df = pd.DataFrame({
        'wl_mean_m':        wl_zz,
        'daq_lif_signal_V': signal,
        'master_piezo_off_set_V': np.linspace(-5, 5, n_points),
    })
    return df


# ----------------------------------------------------------------
# Main – Test mit simulierten Daten
# ----------------------------------------------------------------
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== LIF Linienprofil-Auswertung – Test mit simulierten Daten ===\n")

    # --- Test 1: einzelne Temperatur ---
    print("--- Test 1: T = 500 K ---")
    df_test = make_test_data(T_K=500, B_field_T=0.1,
                              noise_level=0.005, n_points=40)
    llp = LIFLineProfile(B_field_T=0.1)
    result = llp.fit(df_test)
    llp.plot(df_test, result, show=True,
             save_path = None)  # save_path = SAVE_PATH / "test_500K.png" zum Speichern

    # --- Test 2: verschiedene Temperaturen ---
    print("\n--- Test 2: Temperaturreihe ---")
    temperatures = [300, 400, 500, 573]
    results = []
    for T in temperatures:
        df_t = make_test_data(T_K=T, noise_level=0.008)
        r    = llp.fit(df_t)
        results.append({"T_input_K": T, "T_fit_K": r.T_K, "T_err_K": r.T_K_err})
        print(f"  Input: {T} K  →  Fit: {r.T_K:.1f} ± {r.T_K_err:.1f} K")

    df_results = pd.DataFrame(results)
    print(f"\n{df_results.to_string(index=False)}")

    # --- Test 3: Einfluss des Rauschens ---
    print("\n--- Test 3: Rauscheinfluss bei T=500 K ---")
    for noise in [0.001, 0.005, 0.01, 0.05]:
        df_n = make_test_data(T_K=500, noise_level=noise)
        r    = llp.fit(df_n)
        print(f"  noise={noise:.3f}  →  T={r.T_K:.1f} ± {r.T_K_err:.1f} K, "
              f"R²={r.r_squared:.4f}")