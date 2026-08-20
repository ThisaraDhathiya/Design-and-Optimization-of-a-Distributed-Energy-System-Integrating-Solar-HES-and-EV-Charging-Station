# HESS 1-Second Transient / Supercapacitor Study

Supplementary project to the main thesis (`University_EV_Charging_OpenDSS`).
Same physical system (BESS 670 kWh/100 kW, 18 building loads + EV station,
1843.05 kWp PV), run at **1-second resolution using real measured campus
data** (all building, EV, and PV files are final, real 1-second data).

**Supercapacitor: 0.313 kWh / 44.0 kW** (Eaton XLM-62, 6-module series stack)
— sized from real campus transient data. See
`docs/Supercapacitor_Sizing_Document.docx` for the complete topology,
control logic, and sizing derivation, ready for direct inclusion in the thesis.

The main thesis project folder is **untouched**. This is a separate folder.

## Why this exists

At 15-minute resolution, cloud-driven PV ramps, EV charger switching, and
other sub-minute events are invisible — the supercapacitor looks like it does
nothing. This project studies the same system at 1-second resolution over a
single 24-hour window so the SC's response to real fast transients shows up.

## Folder structure

```
HESS_1s_Transient_Study/
├── 01_OpenDSS_Model/         # your REAL OpenDSS model files (copied from your main
│                              # project) — Master.dss, Loads.dss, PVSystem.dss, etc.
├── config_1s.py              # all system parameters (dt=1s, BESS/SC specs, SC dispatch mode)
├── data_loader_1s.py         # loads all CSVs into memory ONCE before the loop
├── noise_pipeline.py         # ported MATLAB noise-generation algorithm (PCHIP/AR1/Butterworth/etc)
├── ems_controller_1s.py      # EMS dispatch logic — TWO SC control modes, see below
├── opendss_bridge_1s.py      # REAL OpenDSS integration via opendssdirect.py — see note below
├── run_simulation_1s.py      # main entry point (single mode, from config_1s.SC_DISPATCH_MODE)
├── run_comparison_1s.py      # runs BOTH SC modes back-to-back and compares them
├── sc_sizing_analysis.py     # Step 1 of SC sizing: real fluctuation/event analysis at MainBus
├── generate_plots_1s.py      # produces the transient/SC plots
├── make_sample_1s_data.py    # generates data from your real 96-step profiles + noise pipeline
├── reference_profiles_96.py  # copy of your main project's load_profiles.py
├── data/
│   ├── loads/                # one CSV per building + EV, 86400 rows each
│   └── solar/                # PV_1s.csv, 86400 rows
└── results/
    ├── EMS_1s_results.csv
    ├── SC_mode_comparison.csv
    ├── SC_sizing_delta_stats.csv
    ├── SC_sizing_threshold_sweep.csv
    ├── SC_sizing_events_thr*.csv
    └── plots/
```

## About the OpenDSS files (`01_OpenDSS_Model/`) and real solving

Your real `.dss` model files are now included, and `opendss_bridge_1s.py` provides a genuine `opendssdirect.py` integration — `pip install opendssdirect.py` and set `config_1s.USE_OPENDSS_SOLVE = True` to actually compile and solve your real network every second (or every Nth second via `OPENDSS_SOLVE_EVERY_N`, for speed). **Performance is good**: a real 86,400-step solved day took ~30-40s in testing.

**However — testing surfaced a real issue in the underlying `.dss` files, not in this bridge code:** `CalcVoltageBases` is not correctly propagating the 33kV source voltage through the network — every bus (including `SourceBus` itself) resolves to the smallest declared base (0.24kV) instead of its real level, which corrupts every per-unit voltage reading. This was never caught before because your original `ems_controller.py` never actually reads voltages back from OpenDSS — it uses the analytical `_calc_voltages()` formula exclusively (confirmed by inspection). This is therefore the first time this model's real OpenDSS voltage output has actually been used for anything.

**Because of this, `USE_OPENDSS_SOLVE` defaults to `False`** — the analytical formula remains the validated, working path for all results in this project. If you want genuine OpenDSS solves for your thesis (e.g. as a supervisor requirement or formal cross-check), the `Transformer.dss`/bus voltage-base setup needs debugging first — happy to help dig into that when you're ready; it's a `CalcVoltageBases`/bus topology issue, likely something in how the buses' base kV propagates from `SourceBus`, not a fundamental flaw in your design.

## Supercapacitor dispatch modes

`config_1s.SC_DISPATCH_MODE` selects between two SC control strategies:

- **`"threshold"`** — the original rule: if a step change exceeds `EMS_SC_SPIKE_KW` (30 kW), discharge. Simple, but the threshold is arbitrary.
- **`"filter"` (recommended, default)** — a causal low-pass filter splits net demand into a slow component (assigned to the BESS) and a fast residual (assigned to the SC automatically, no threshold), plus a SOC-recovery layer that keeps the SC in a healthy target band (`SC_TARGET_SOC_LOW`-`SC_TARGET_SOC_HIGH`) between transients. This is the physically-motivated approach used in HESS literature (frequency/complementary filtering).

Run `python run_comparison_1s.py` to simulate both modes on identical data and get a side-by-side comparison table + plot (`results/SC_mode_comparison.csv`, `results/plots/Plot5_SC_Mode_Comparison.png`) — useful for a "rule-based vs. filter-based SC dispatch" thesis section.

**Known architectural note (carried over from your main project, not something introduced here):** the SC's power currently only affects whether peak-shaving triggers — it isn't subtracted from the load the battery/grid must cover in the main dispatch balance. In this project's data, peak-shaving rarely triggers, so different SC dispatch modes don't change grid import. Worth discussing with your supervisor whether SC discharge should directly offset load like the battery does.

## Supercapacitor sizing workflow

`sc_sizing_analysis.py` implements Step 1 of the sizing procedure discussed with Claude: it aggregates all building + EV + PV files into `P_net` at MainBus (the same signal your EMS uses — NOT individual building fluctuations, which mostly cancel out on aggregation), then extracts:
- Step-change (delta) distribution statistics
- A ranked event table (magnitude, duration, dP/dt) at several candidate thresholds
- Candidate `(ΔP_design, dt_design)` pairs for the electrical sizing step

**Important:** run this only once real building/EV data is in `data/loads/` — with the current synthetic placeholder data, the "worst events" it finds are artifacts of the noise-generation pipeline's 900-second correction blocks, not real transients (every synthetic-data event lands exactly on a multiple of 900s). No code changes needed when you swap in real data — just re-run.

## Required input files

Every file needs exactly **86,400 rows** (one per second, 24 hours) and a
`kW` column. Filenames must match exactly:

**`data/loads/`** — one file per building:
`ElecDept_1s.csv`, `Workshop_1s.csv`, `Auditorium_1s.csv`, `Admin_1s.csv`,
`CivilDept_1s.csv`, `MechDept_1s.csv`, `LecTheatre_1s.csv`, `Library_1s.csv`,
`HostelD_1s.csv`, `HostelC_1s.csv`, `HostelBlock_1s.csv`, `BoysHostelB_1s.csv`,
`HostelF_1s.csv`, `LowerCanteen_1s.csv`, `GuestHouse_1s.csv`,
`UpperCanteen_1s.csv`, `Gym_1s.csv`, **and** `EV_1s.csv` (EV station demand).

**`data/solar/`**: `PV_1s.csv` — total campus PV generation in kW.

Example format (`ElecDept_1s.csv`):
```
second,kW
0,18.3
1,18.4
2,18.2
...
86399,17.9
```

## Result sheet columns (updated)

`EMS_1s_results.csv` (and `EMS_1s_results_no_SC.csv`) now include two
additional columns:

- **`p_net_kw`** — combined campus demand: `p_load_kw + p_ev_kw − p_pv_kw`
  (the same signal the EMS filter uses internally to split power between
  battery and SC)
- **`v_mainbus_pu`** — voltage at MainBus, the common coupling point where
  both the battery and supercapacitor connect (`Bus1=MainBus` in
  `Battery.dss` and `SuperCap.dss`). Computed from the real 1000 kVA,
  %Z=5.04% transformer nameplate impedance and the net power flowing
  through it (`export_kw − grid_kw`) — **not** the downstream cable
  resistance table used for individual buildings, since that resistance
  (calibrated for single-building loads of tens of kW) produces physically
  implausible results when applied to full campus-scale aggregate flow
  (hundreds to ~1600 kW). See the docstring in `_calc_voltages()` in
  `ems_controller_1s.py` for the full derivation.

**Important finding from this addition:** MainBus voltage now genuinely
varies (0.996–1.082 pu across the day) and exceeds the 1.06 pu safe limit
for roughly 20,000 of the 86,400 seconds (~23% of the day), concentrated
between 08:00–14:00 whenever PV export exceeds ~1190 kW. This means your
campus's midday solar export exceeds what the 1000 kVA transformer can
absorb without overvoltage — a real, common issue in high-PV-penetration
systems that was **not visible in earlier results**, since the previous
MainBus voltage formula was mathematically constant at 1.0 pu (no building
or PV was ever attached to that bus in the model, so its local voltage
drop was always zero). This is a significant change from the "0 voltage
violations" figure reported in earlier project documents — those documents
should be revisited if you want them to reflect this finding.

## Two full result sheets — with and without the supercapacitor

`run_simulation_both_1s.py` runs the identical simulation twice on the same
real data and saves two complete, directly comparable 86,400-row sheets:
- `results/EMS_1s_results.csv` — supercapacitor working normally
- `results/EMS_1s_results_no_SC.csv` — supercapacitor fully disabled

Both have identical columns, so you can compare them row-by-row in Excel,
not just via the summary statistics already produced by `run_ablation_1s.py`.

## How to run

The `data/loads/` and `data/solar/` folders already contain your **final real
1-second data** — no generation step needed. Just run:

```bash
cd HESS_1s_Transient_Study
python run_simulation_1s.py       # runs the 86,400-step EMS loop
python generate_plots_1s.py       # produces the plots in results/plots/
python sc_sizing_analysis.py      # real transient/sizing analysis at MainBus
python run_comparison_1s.py       # compares threshold vs. filter SC dispatch
```

If you ever need to regenerate synthetic placeholder data for testing (e.g.
after changing the EMS logic and wanting a quick sanity check before your
next real dataset arrives), `make_sample_1s_data.py` is still available —
but running it will **overwrite** the real data files currently in place, so
don't run it unless you mean to.

## Performance note

`config_1s.USE_OPENDSS_SOLVE` defaults to `False`. The analytical R×P voltage
formula (`_calc_voltages`) reproduces the main project's results without the
cost of 86,400 power-flow solves. A real OpenDSS integration is available
(`opendss_bridge_1s.py`, ~30s/day when enabled) but testing surfaced a
voltage-base propagation issue in the underlying `.dss` files that should be
resolved before trusting its violation output — see the note further down.

## Recommended thesis framing

Treat this as a focused supplementary section (e.g. "4.X High-Resolution
Transient Response of the Supercapacitor") rather than replacing your five
main 15-minute scenarios — those remain your primary quantitative results.
This section's job is to show, with real second-by-second data, that the
supercapacitor visibly responds to fast transients that the 15-minute model
cannot see.
