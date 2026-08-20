"""
generate_pv_from_irradiance.py
================================================================================
Generates PV_1s.csv from your REAL measured 96-step (15-min) irradiance
LoadShape — pure PCHIP interpolation to 86,400 points, NO noise added.

This deliberately does NOT use noise_pipeline.py's AR(1)/Butterworth/ramp-
limiter stages. Those exist to add PLAUSIBLE fast fluctuation on top of load
profiles that don't otherwise have any — but this irradiance curve IS your
real measured data, so adding synthetic noise on top of it would be
fabricating detail that was never actually observed. Interpolation only
fills in the shape BETWEEN your 96 real measurement points; it invents
nothing beyond what the smooth PCHIP curve implies.

PV_1s(t) = irradiance_pu(t) x PV_TOTAL_KWP

PV_TOTAL_KWP comes from config_1s.py (1843.05 kWp) so this stays consistent
with the same total your EMS's analytical voltage calculation assumes.

Run:
    python generate_pv_from_irradiance.py
================================================================================
"""
import os
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from config_1s import SOLAR_DIR, PV_TOTAL_KWP

N_96 = 96
N_1S = 86400

# Your real measured 96-step irradiance LoadShape (per-unit, 0-1)
IRRADIANCE_96 = np.array([
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0015, 0.0030, 0.0045,
    0.0060, 0.0260, 0.0460, 0.0660, 0.0860, 0.1497, 0.2135, 0.2773, 0.3410, 0.4083,
    0.4755, 0.5428, 0.6100, 0.6740, 0.7380, 0.8020, 0.8660, 0.8942, 0.9225, 0.9507,
    0.9790, 0.9842, 0.9895, 0.9948, 1.0000, 0.9962, 0.9925, 0.9888, 0.9850, 0.9677,
    0.9505, 0.9333, 0.9160, 0.8873, 0.8585, 0.8297, 0.8010, 0.7492, 0.6975, 0.6458,
    0.5940, 0.5245, 0.4550, 0.3855, 0.3160, 0.2510, 0.1860, 0.1210, 0.0560, 0.0420,
    0.0280, 0.0140, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
])
assert len(IRRADIANCE_96) == 96, f"Expected 96 points, got {len(IRRADIANCE_96)}"


def main():
    t96 = np.linspace(0, N_1S, N_96, endpoint=False)
    t1s = np.arange(N_1S)

    pchip = PchipInterpolator(t96, IRRADIANCE_96)
    irr_1s = pchip(t1s)

    # PCHIP is shape-preserving (low overshoot) but clip defensively to the
    # physically valid range anyway — irradiance p.u. can't exceed the real
    # observed peak or go negative.
    irr_1s = np.clip(irr_1s, 0.0, IRRADIANCE_96.max())

    pv_1s = irr_1s * PV_TOTAL_KWP

    out_path = os.path.join(SOLAR_DIR, "PV_1s.csv")
    df = pd.DataFrame({"second": np.arange(N_1S), "kW": np.round(pv_1s, 4)})
    df.to_csv(out_path, index=False)

    # Validation: compare recomputed 15-min block averages against the
    # original 96-step values (pure interpolation won't conserve this
    # exactly like the noise pipeline's mean-preserving correction does,
    # but it should be very close since PCHIP is a smooth, faithful fit).
    recomputed_96 = np.array([pv_1s[i*900:(i+1)*900].mean() / PV_TOTAL_KWP
                               for i in range(N_96)])
    max_err = np.max(np.abs(recomputed_96 - IRRADIANCE_96))
    energy_96 = IRRADIANCE_96.sum() * 0.25 * PV_TOTAL_KWP   # kWh, 15-min steps
    energy_1s = pv_1s.sum() * (1/3600.0)                     # kWh, 1s steps
    energy_err_pct = abs(energy_1s - energy_96) / energy_96 * 100

    print(f"Wrote {out_path}")
    print(f"  rows={len(df)}  peak={pv_1s.max():.2f} kW  mean={pv_1s.mean():.2f} kW")
    print(f"  Max block-average deviation from original 96-step irradiance: {max_err:.5f} p.u.")
    print(f"  Daily energy: 96-step={energy_96:.1f} kWh  1s={energy_1s:.1f} kWh  "
          f"(diff {energy_err_pct:.3f}%)")


if __name__ == "__main__":
    main()
