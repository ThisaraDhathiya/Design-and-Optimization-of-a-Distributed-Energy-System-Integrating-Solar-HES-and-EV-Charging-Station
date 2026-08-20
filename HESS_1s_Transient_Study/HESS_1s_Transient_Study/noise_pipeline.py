"""
noise_pipeline.py
================================================================================
Python port of the MATLAB "High-Resolution Load Profile Generator" you
uploaded (LoadProfileGenerator/*.m). Same algorithm, same math, same default
parameters as main.m — just implemented in Python/numpy/scipy so it plugs
directly into make_sample_1s_data.py instead of needing MATLAB.

Pipeline (matches main.m Steps 3-8 exactly):
  1. interpolate_trend()     — PCHIP interpolation, 96 pts -> 86400 pts
  2. generate_ar1_noise()    — AR(1) correlated noise, scaled to local load
  3. (trend + noise)
  4. lowpass_filter()        — 4th-order Butterworth, zero-phase (filtfilt)
  5. ramp_limiter()          — caps kW/s change, physical charger/load realism
  6. mean_preserving_correction() — forces each 15-min block's mean back to
     the exact original 96-step value -> guarantees identical daily energy
     totals to your original 96-step profiles (no drift from filtering/noise)
  7. clip to >= 0            — no negative power

Default config matches your uploaded main.m exactly:
    noisePercent = 0.4   (%)
    phi          = 0.998 (AR(1) autocorrelation)
    maxRamp      = 0.3   (kW/s)
    filterOrder  = 4
    cutoffFreq   = 0.008 (normalised, 0-1)
================================================================================
"""
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.signal import butter, filtfilt

DEFAULT_CFG = dict(
    noise_percent=0.4,
    phi=0.998,
    max_ramp=0.3,       # kW per 1-second step
    filter_order=4,
    cutoff_freq=0.008,
    random_seed=1,
)

N_96 = 96
N_1S = 86400


def interpolate_trend(power_96, n_1s=N_1S):
    """PCHIP interpolation — shape-preserving, no overshoot (matches
    interpolateTrend.m 'pchip' case)."""
    t96 = np.linspace(0, n_1s, N_96, endpoint=False)
    t1s = np.arange(n_1s)
    pchip = PchipInterpolator(t96, power_96)
    return pchip(t1s)


def generate_ar1_noise(power_trend, cfg, seed_offset=0):
    """
    AR(1) correlated noise: noise(k) = phi*noise(k-1) + sigma(k)*eps(k)
    sigma(k) = (noisePercent/100) * powerTrend(k)
    Exact port of generateARNoise.m, including DC-offset removal and
    +/-3-sigma clipping.
    """
    rng = np.random.default_rng(cfg["random_seed"] + seed_offset)
    n = len(power_trend)
    phi = cfg["phi"]
    local_std = (cfg["noise_percent"] / 100.0) * power_trend
    innovations = rng.standard_normal(n)

    noise = np.zeros(n)
    for k in range(1, n):
        noise[k] = phi * noise[k - 1] + local_std[k] * innovations[k]

    noise -= noise.mean()
    noise_std = noise.std()
    noise = np.clip(noise, -3 * noise_std, 3 * noise_std)
    return noise


def lowpass_filter(signal, cfg):
    """4th-order Butterworth low-pass, zero-phase (matches lowPassFilter.m)."""
    b, a = butter(cfg["filter_order"], cfg["cutoff_freq"], btype="low")
    return filtfilt(b, a, signal)


def ramp_limiter(signal, max_ramp):
    """Caps the step-to-step change to +/- max_ramp (kW per second).
    Exact port of rampLimiter.m — inherently sequential, so this is a loop."""
    n = len(signal)
    out = np.empty(n)
    out[0] = signal[0]
    for k in range(1, n):
        change = signal[k] - out[k - 1]
        change = max(min(change, max_ramp), -max_ramp)
        out[k] = out[k - 1] + change
    return out


def mean_preserving_correction(signal_1s, power_96, block_size=900):
    """
    Forces the mean of each 900-second (15-min) block back to the exact
    original 96-step value. This is what guarantees your daily energy totals
    (kWh) exactly match your original thesis 96-step profiles, no matter what
    noise/filtering/ramp-limiting did to the shape within each block.

    Note: implemented as clean, non-overlapping 900-second blocks aligned to
    each 15-min timestamp (a slightly cleaner equivalent of the MATLAB
    meanPreservingCorrection.m, which defines interval boundaries using the
    previous/next original timestamp and leaves the very first block almost
    empty as an edge case). The energy-conservation guarantee is identical.
    """
    out = signal_1s.copy()
    corrections = np.zeros(N_96)
    for i in range(N_96):
        lo, hi = i * block_size, (i + 1) * block_size
        current_mean = out[lo:hi].mean()
        target_mean = power_96[i]
        correction = target_mean - current_mean
        corrections[i] = correction
        out[lo:hi] += correction
    return out, corrections


def generate_1s_series(power_96, cfg=None, seed_offset=0):
    """
    Full pipeline, matching main.m Steps 3-8. Give it a 96-step (15-min)
    kW profile, get back an 86400-step (1s) kW profile with realistic
    correlated noise, physically-limited ramp rates, and exact energy
    conservation against the original 96 values.
    """
    cfg = {**DEFAULT_CFG, **(cfg or {})}

    trend = interpolate_trend(power_96)
    noise = generate_ar1_noise(trend, cfg, seed_offset=seed_offset)
    combined = trend + noise
    filtered = lowpass_filter(combined, cfg)
    limited = ramp_limiter(filtered, cfg["max_ramp"])
    corrected, _ = mean_preserving_correction(limited, power_96)
    corrected = np.maximum(corrected, 0.0)
    return corrected


def validation_report(power_96, series_1s, block_size=900):
    """Quick sanity metrics — energy match, max/RMSE recompute error, max ramp."""
    recomputed_96 = np.array([series_1s[i*block_size:(i+1)*block_size].mean()
                               for i in range(N_96)])
    err = recomputed_96 - power_96
    energy_orig = power_96.sum() * 0.25          # kWh, 15-min steps
    energy_1s = series_1s.sum() * (1/3600.0)     # kWh, 1s steps
    energy_err_pct = 0.0 if energy_orig == 0 else abs(energy_1s - energy_orig) / energy_orig * 100
    max_ramp = np.max(np.abs(np.diff(series_1s))) if len(series_1s) > 1 else 0.0
    return {
        "max_error_kw": float(np.max(np.abs(err))),
        "rmse_kw": float(np.sqrt(np.mean(err ** 2))),
        "mae_kw": float(np.mean(np.abs(err))),
        "max_ramp_kw_s": float(max_ramp),
        "energy_error_pct": float(energy_err_pct),
    }
