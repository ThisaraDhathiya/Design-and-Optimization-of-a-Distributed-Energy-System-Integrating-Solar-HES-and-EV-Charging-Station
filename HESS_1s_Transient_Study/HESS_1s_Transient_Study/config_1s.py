"""
config_1s.py
================================================================================
University of Ruhuna — Faculty of Engineering
1-second resolution configuration for the HESS Transient / Supercapacitor study.

This is a SEPARATE, SUPPLEMENTARY project. It shares the same physical system
parameters as your main thesis project (03_Python_EMS/config.py) but runs at
1-second resolution instead of 15-minute resolution, so the supercapacitor's
fast-transient buffering behaviour is actually visible.

Your main thesis project is untouched — nothing here edits it.
================================================================================
"""
import os

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
LOADS_DIR   = os.path.join(DATA_DIR, "loads")
SOLAR_DIR   = os.path.join(DATA_DIR, "solar")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(os.path.join(RESULTS_DIR, "plots"), exist_ok=True)

# ── Simulation ──────────────────────────────────────────────────────────────
SIM_STEPS = 86400            # 24 hours x 1-second steps
DT_HOURS  = 1.0 / 3600.0     # step length in hours (was 0.25 h for 15-min)

# Set True only if you also want a full OpenDSS power-flow Solve() every step.
# IMPORTANT: your main project's bus voltage estimates (_calc_voltages) are
# computed with an analytical R x P formula, NOT read back from OpenDSS's own
# Solve() results anywhere in ems_controller.py. That means OpenDSS solving is
# NOT required to reproduce the same voltage numbers or any other result here.
# Leave this False unless your supervisor specifically wants OpenDSS's own
# power-flow engine exercised 86,400 times (this adds hours to the runtime).
USE_OPENDSS_SOLVE = False
MASTER_DSS    = os.path.join(BASE_DIR, "01_OpenDSS_Model", "Master.dss")
SIM_ALGORITHM = "NR"

# When USE_OPENDSS_SOLVE=True: real power-flow solves have per-call overhead,
# so you can decimate — solve OpenDSS every N seconds and hold the last-solved
# voltages in between, instead of solving all 86,400 steps. 1 = every step
# (slowest, most accurate). Run `python opendss_bridge_1s.py` for a timing
# benchmark on your machine before choosing this.
OPENDSS_SOLVE_EVERY_N = 1

# ── Battery (LiFePO4 BESS) — same as main project ────────────────────────────
BESS_KWH        = 670.0
BESS_KW         = 100.0
BESS_SOC_MIN    = 15.0
BESS_SOC_MAX    = 90.0
BESS_SOC_INIT   = 23.0
BESS_EFF_CHARGE = 0.97
BESS_EFF_DISCH  = 0.97

# ── Supercapacitor — DERIVED SIZING (Eaton XLM-62, 6-module series stack) ────
# Replaces the original provisional placeholder (1.0 kWh / 100 kW). Derived in
# Supercapacitor_Sizing_Document.docx from real campus transient data:
#   Design transient: dP=22kW nameplate charger step (real observed max: 16.53kW)
#   Result: 313 Wh usable energy, 44.0 kW peak power
#   Margins: 2.0x power, 3.04x capacitance over the formal minimum
SC_KWH          = 0.313
SC_KW           = 44.0
SC_SOC_MIN      = 20.0
SC_SOC_MAX      = 95.0
SC_SOC_INIT     = 80.0
SC_SOC_HARD_MIN = 15.0

# ── PV ────────────────────────────────────────────────────────────────────────
PV_TOTAL_KWP = 1843.05

# ── EV Charging Station ───────────────────────────────────────────────────────
# UPDATED per your correction: 4 x 22 kW AC Type 2 chargers (was 2x22kW)
EV_CHARGERS    = 4
EV_KW_PER_UNIT = 22.0
EV_TOTAL_KW    = EV_CHARGERS * EV_KW_PER_UNIT   # 88 kW nameplate

# ── EMS parameters (same thresholds as your 15-min model) ────────────────────
EMS_PEAK_SHAVE_LIMIT = 204.0
EMS_SC_SPIKE_KW      = 30.0     # kW step-to-step change that triggers SC discharge (THRESHOLD mode only)
EMS_EVENING_START_H  = 17.5
EMS_EVENING_END_H    = 22.5
EMS_EVENING_SOC_MIN  = 15.0

# ── Supercapacitor dispatch mode ──────────────────────────────────────────────
# "threshold" = original rule-based logic (if step change > EMS_SC_SPIKE_KW: discharge)
# "filter"    = recommended logic: causal low-pass filter splits P_net into a slow
#               component (BESS) and fast residual (SC), no arbitrary threshold,
#               plus a SOC-recovery bias that keeps the SC in a "ready" band
#               between transients. See ems_controller_1s.py _run_sc_logic_filter().
SC_DISPATCH_MODE = "filter"   # "threshold" or "filter"

# Filter-mode parameters
SC_FILTER_TAU_S      = 25.0   # low-pass time constant (s) — matches the "operating"
                               # value used in the sizing document; battery gets
                               # everything slower than this, SC gets everything faster
SC_IDLE_THRESHOLD_KW = 2.0     # |P_sc| below this = "no active transient" -> recovery mode
SC_TARGET_SOC_LOW    = 50.0    # below this (while idle) -> gentle trickle charge
SC_TARGET_SOC_HIGH   = 90.0    # above this (while idle) -> gentle bleed-down
SC_RECOVERY_KW       = 3.0     # magnitude of the gentle recovery nudge (kW)

EVENING_START_STEP = int(EMS_EVENING_START_H * 3600)
EVENING_END_STEP   = int(EMS_EVENING_END_H * 3600)

# ── Voltage limits ────────────────────────────────────────────────────────────
V_MIN_PU = 0.94
V_MAX_PU = 1.06

# ── Emissions ─────────────────────────────────────────────────────────────────
SRI_LANKA_CO2 = 0.72   # kg CO2 / kWh

# ── Building list — MUST match filenames in data/loads/ exactly ─────────────
# Expected file: data/loads/<name>_1s.csv  with a "kW" column, 86400 rows.
BUILDINGS = [
    "ElecDept", "Workshop", "Auditorium", "Admin", "CivilDept", "MechDept",
    "LecTheatre", "Library", "HostelD", "HostelC", "HostelBlock",
    "BoysHostelB", "HostelF", "LowerCanteen", "GuestHouse", "UpperCanteen", "Gym",
]
# EV is handled separately: data/loads/EV_1s.csv (it is dispatched by the EMS,
# not a purely passive load like the buildings above).

# ── Cable resistance data for analytical voltage estimation ─────────────────
# Unchanged from your main project's ems_controller.py _BUS_CABLES table,
# reorganised to reference building names directly instead of profile-type strings.
BUS_CABLES = {
    "mainbus":           {"R": 0.008,  "pv_kwp": 0,      "building": None},
    "panelbus":          {"R": 0.010,  "pv_kwp": 0,      "building": None},
    "mechworkshopbus":   {"R": 0.016,  "pv_kwp": 203.1,  "building": "Workshop"},
    "hostelfbus":        {"R": 0.016,  "pv_kwp": 203.1,  "building": "HostelF"},
    "guesthousebus":     {"R": 0.026,  "pv_kwp": 51.6,   "building": "GuestHouse"},
    "auditoriumbus":     {"R": 0.049,  "pv_kwp": 210.0,  "building": "Auditorium"},
    "librarybus":        {"R": 0.0389, "pv_kwp": 125.1,  "building": "Library"},
    "civildeptbus":      {"R": 0.009,  "pv_kwp": 172.8,  "building": "CivilDept"},
    "mechdeptbus":       {"R": 0.033,  "pv_kwp": 172.8,  "building": "MechDept"},
    "elecdeptbus":       {"R": 0.02,   "pv_kwp": 172.8,  "building": "ElecDept"},
    "ltdbus":            {"R": 0.022,  "pv_kwp": 0,      "building": None},
    "hostelcbus":        {"R": 0.073,  "pv_kwp": 135.3,  "building": "HostelC"},
    "hosteldbus":        {"R": 0.088,  "pv_kwp": 111.45, "building": "HostelD"},
    "gymbus":            {"R": 0.174,  "pv_kwp": 0.0,    "building": "Gym"},
    "evbus":             {"R": 0.012,  "pv_kwp": 0,      "building": "EV"},
    "lecturetheatrebus": {"R": 0.015,  "pv_kwp": 210.0,  "building": "LecTheatre"},
    "adminbus":          {"R": 0.038,  "pv_kwp": 79.7,   "building": "Admin"},
    "pumphousebus":      {"R": 0.042,  "pv_kwp": 0,      "building": None},
    "securitybus":       {"R": 0.044,  "pv_kwp": 0,      "building": None},
    "uppercanteenbus":   {"R": 0.033,  "pv_kwp": 41.1,   "building": "UpperCanteen"},
    "lowercanteenbus":   {"R": 0.022,  "pv_kwp": 125.1,  "building": "LowerCanteen"},
    "boyshostelbbus":    {"R": 0.052,  "pv_kwp": 31.8,   "building": "BoysHostelB"},
    "hostelblockbus":    {"R": 0.028,  "pv_kwp": 32.25,  "building": "HostelBlock"},
}
