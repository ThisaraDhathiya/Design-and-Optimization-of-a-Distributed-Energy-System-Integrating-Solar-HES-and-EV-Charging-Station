"""
config.py
================================================================================
University of Ruhuna - Faculty of Engineering
EV Charging Station with Hybrid Energy Storage System
Central configuration — all system parameters in one place
UPDATED: June 2026 — PV_TOTAL_KWP updated (Gym+HostelD PV disabled)
================================================================================
"""

import os

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_DSS  = os.path.join(BASE_DIR, "01_OpenDSS_Model", "Master.dss")
RESULTS_DIR = os.path.join(BASE_DIR, "05_Results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Simulation ────────────────────────────────────────────────────────────────
SIM_STEPS    = 96          # 15-min steps in 24 hours
SIM_STEPSIZE = "15m"
SIM_ALGORITHM = "NR"       # Newton-Raphson

# ── Battery (LiFePO4 BESS) ────────────────────────────────────────────────────
BESS_KWH         = 670.0   # kWh total capacity
BESS_KW          = 100.0   # kW max charge/discharge
BESS_SOC_MIN     = 15.0    # % minimum SOC (battery protection)
BESS_SOC_MAX     = 90.0    # % maximum SOC (longevity)
BESS_SOC_INIT    = 23.0    # % initial SOC at start of simulation
BESS_EFF_CHARGE  = 0.97    # charge efficiency (includes PCS inverter)
BESS_EFF_DISCH   = 0.97    # discharge efficiency

# ── Supercapacitor ────────────────────────────────────────────────────────────
SC_KWH           = 1.0     # kWh energy capacity
SC_KW            = 100.0   # kW peak power
SC_SOC_MIN       = 20.0    # % minimum SOC
SC_SOC_MAX       = 95.0    # % maximum SOC
SC_SOC_INIT      = 80.0    # % initial SOC

# ── PV System ─────────────────────────────────────────────────────────────────
# NOTE: Gym (156.3 kWp) and HostelD (111.45 kWp) PV systems disabled
# due to overvoltage on long feeders (709m and 576m respectively)
# Original total was 2089.35 kWp — now 1821.60 kWp (15 active systems)
PV_TOTAL_KWP      = 1843.05   # kWp — active PV capacity (HostelD PV re-enabled: +111.45 kWp, cable upgraded 75→120mm²)
PV_DC_AC_RATIO    = 1.1        # DC/AC sizing ratio
PV_LOCATION       = "Matara, Sri Lanka"
PV_LATITUDE       = 5.95
PV_LONGITUDE      = 80.55
PV_SPECIFIC_YIELD = 1450       # kWh/kWp/year (PVGIS estimate)
PV_ANNUAL_KWH     = PV_TOTAL_KWP * PV_SPECIFIC_YIELD

# ── EV Charging Station ───────────────────────────────────────────────────────
EV_CHARGERS      = 2       # number of AC Type 2 chargers
EV_KW_PER_UNIT   = 22.0   # kW per charger
EV_TOTAL_KW      = EV_CHARGERS * EV_KW_PER_UNIT   # 44 kW
EV_CABLE_M       = 50.0   # cable length from panel to EV station (m)

# ── EMS Parameters ────────────────────────────────────────────────────────────
EMS_PEAK_SHAVE_LIMIT  = 204.0  # kW — 85% of 240 kW demand limit
EMS_SC_SPIKE_KW       = 30.0   # kW — threshold to trigger SC dispatch
EMS_EVENING_START_H   = 17.5   # 17:30 — battery evening support start
EMS_EVENING_END_H     = 22.5   # 22:30 — battery evening support end
EMS_EVENING_SOC_MIN   = 15.0   # % — SOC floor during evening
EMS_EV_CUTOFF_HOUR    = 16.0   # 16:00 — EV session cutoff (fallback)
EMS_NIGHT_CHARGE_SOC  = 80.0   # % — target SOC for night charging

# ── Network ───────────────────────────────────────────────────────────────────
GRID_KV          = 33.0    # kV — CEB supply voltage
LV_KV            = 0.415   # kV — campus LV network
TX_KVA           = 1000.0  # kVA — transformer rating
TX_Z_PCT         = 5.04    # % — transformer impedance (nameplate)
V_BASE_LN_KV     = LV_KV / (3 ** 0.5)  # 0.23960 kV line-to-neutral

# ── Voltage limits (IEC 60038 / CEB grid code) ────────────────────────────────
V_MIN_PU         = 0.94    # per unit minimum
V_MAX_PU         = 1.06    # per unit maximum

# ── Emissions ─────────────────────────────────────────────────────────────────
SRI_LANKA_CO2    = 0.72    # kg CO2 per kWh (CEB grid emission factor 2024)
