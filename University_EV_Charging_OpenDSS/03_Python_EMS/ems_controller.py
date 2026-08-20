"""
ems_controller.py
================================================================================
University of Ruhuna - Faculty of Engineering
EMS Controller - opendssdirect.py new API (v0.9+)

Load scaling fix: Python applies LoadShape multipliers directly each step
using Set LoadMult= command. This bypasses the OpenDSS Daily mode issue.

UPDATED: voltage violations are now checked every step and written to the
same alert log as the other EMS alerts (previously check_voltage_violations()
existed in utils.py but was never called anywhere).
================================================================================
"""

import csv
import os
import numpy as np
import opendssdirect as dss
from config import (
    BESS_KWH, BESS_KW, BESS_SOC_MIN, BESS_SOC_MAX, BESS_SOC_INIT,
    SC_KWH, SC_KW, SC_SOC_MIN, SC_SOC_MAX, SC_SOC_INIT,
    EMS_SC_SPIKE_KW, EMS_PEAK_SHAVE_LIMIT,
    EMS_EVENING_START_H, EMS_EVENING_END_H, EMS_EVENING_SOC_MIN,
    EMS_EV_CUTOFF_HOUR, EV_TOTAL_KW, PV_TOTAL_KWP,
    SIM_STEPS, RESULTS_DIR, V_MIN_PU, V_MAX_PU,
)

# Load profile arrays (96-step per-unit values)
from load_profiles import _WORKING_DAY_PU, _CLEAR_DAY_PU
from load_profiles import (
    _LS_TEACHING, _LS_LIBRARY, _LS_HOSTEL, _LS_CANTEEN,
    _LS_GYM, _LS_WORKSHOP, _LS_GUESTHOUSE, _LS_UTILITY,
)
try:
    from load_profiles import _LS_ELEC_DEPT, ELEC_DEPT_PEAK_KW
except ImportError:
    _LS_ELEC_DEPT = _LS_TEACHING
    ELEC_DEPT_PEAK_KW = 23.69
try:
    from load_profiles import _LS_WORKSHOP_REAL
except ImportError:
    _LS_WORKSHOP_REAL = _LS_WORKSHOP   # fallback to assumed
try:
    from load_profiles import _LS_CIVIL_REAL
except ImportError:
    _LS_CIVIL_REAL = _LS_TEACHING      # fallback to assumed

# Voltage limit checker (was defined in utils.py but never called - now wired in)
# check_voltage_violations is defined inline in run_step

# ── Constants ─────────────────────────────────────────────────────────────────
PEAK_LOAD_KW     = 219.7   # peak faculty load kW (sum of all building peaks)
EV_CUTOFF_STEP   = int(EMS_EV_CUTOFF_HOUR * 4)
EVENING_START    = int(EMS_EVENING_START_H * 4)
EVENING_END      = int(EMS_EVENING_END_H * 4)
SC_SOC_HARD_MIN  = 15.0
V_MIN_PU         = 0.94    # bus voltage lower limit (pu)
V_MAX_PU         = 1.06    # bus voltage upper limit (pu)

# ── Real EV demand profile from measurement (96-step, kW per step) ────────────
# Source: 10-EV demand chart, hourly bins expanded to 15-min steps (July 2026 update)
# Replaces previous single-EV-session profile (was peak 82.8 kW, 349.7 kWh/day)
# Peak: 58.3 kW at 13:00-13:45  Total: 300.5 kWh/day
_EV_PROFILE_KW = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 14.2, 14.2, 14.2, 14.2, 24.8, 24.8, 24.8, 24.8, 39.7, 39.7, 39.7, 39.7, 53.7, 53.7, 53.7, 53.7, 58.3, 58.3, 58.3, 58.3, 49.6, 49.6, 49.6, 49.6, 33.7, 33.7, 33.7, 33.7, 17.0, 17.0, 17.0, 17.0, 8.1, 8.1, 8.1, 8.1, 1.4, 1.4, 1.4, 1.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

def step_to_time(step):
    h = (step * 15) // 60
    m = (step * 15) % 60
    return f"{h:02d}:{m:02d}"

def is_evening(step):
    return EVENING_START <= step <= EVENING_END

def cmd(text):
    dss.Text.Command(text)


# ── Cable resistance data for voltage calculation (from Lines.dss) ─────────────
# R_ohm = R1(ohm/km) x length(km)
# V_bus_pu = 1.0 + (P_net_kW x R_ohm) / (V_base_kV^2 x 1000)
_BUS_CABLES = {
    "mainbus"        : {"R": 0.008,  "pv_kwp":    0,   "load_peak":  0,    "profile": "flat"},
    "panelbus"       : {"R": 0.010,  "pv_kwp":    0,   "load_peak":  0,    "profile": "flat"},
    "mechworkshopbus" : {"R": 0.016,  "pv_kwp": 203.1,  "load_peak": 3.51,  "profile": "workshop"},
    "hostelfbus" : {"R": 0.016,  "pv_kwp": 203.1,  "load_peak": 5.52,  "profile": "hostelf_real"},
    "guesthousebus" : {"R": 0.026,  "pv_kwp": 51.6,  "load_peak": 0.001,  "profile": "guesthouse_real"},
    "auditoriumbus" : {"R": 0.049,  "pv_kwp": 210.0,  "load_peak": 40.94,  "profile": "auditorium_real"},
    "librarybus" : {"R": 0.0389,  "pv_kwp": 125.1,  "load_peak": 9.12,  "profile": "library_real"},
    "civildeptbus" : {"R": 0.009,  "pv_kwp": 172.8,  "load_peak": 13.45,  "profile": "civil_real"},
    "mechdeptbus" : {"R": 0.033,  "pv_kwp": 172.8,  "load_peak": 13.45,  "profile": "mechdept_real"},
    "elecdeptbus" : {"R": 0.02,  "pv_kwp": 172.8,  "load_peak": 33.33,  "profile": "teaching"},
    "ltdbus"         : {"R": 0.022,  "pv_kwp":    0,   "load_peak":  0,    "profile": "flat"},
    "hostelcbus" : {"R": 0.073,  "pv_kwp": 135.3,  "load_peak": 9.44,  "profile": "hostelc_real"},
    "hosteldbus" : {"R": 0.088,  "pv_kwp": 111.45,  "load_peak": 9.44,  "profile": "hosteld_real"},
    "gymbus" : {"R": 0.174,  "pv_kwp": 0.0,  "load_peak": 0.001,  "profile": "gym_real"},
    "evbus"          : {"R": 0.012,  "pv_kwp":    0,   "load_peak": 44.0,  "profile": "ev"},
    "lecturetheatrebus" : {"R": 0.015,  "pv_kwp": 210.0,  "load_peak": 8.15,  "profile": "lectheatre_real"},
    "adminbus" : {"R": 0.038,  "pv_kwp": 79.7,  "load_peak": 70.69,  "profile": "admin_real"},
    "pumphousebus"   : {"R": 0.042,  "pv_kwp":    0,   "load_peak":  0.12, "profile": "utility"},
    "securitybus"    : {"R": 0.044,  "pv_kwp":    0,   "load_peak":  0.45, "profile": "utility"},
    "uppercanteenbus" : {"R": 0.033,  "pv_kwp": 41.1,  "load_peak": 0.001,  "profile": "uppercanteen_real"},
    "lowercanteenbus" : {"R": 0.022,  "pv_kwp": 125.1,  "load_peak": 12.65,  "profile": "lowercanteen_real"},
    "boyshostelbbus" : {"R": 0.052,  "pv_kwp": 31.8,  "load_peak": 5.52,  "profile": "hostelb_real"},
    "hostelblockbus" : {"R": 0.028,  "pv_kwp": 32.25,  "load_peak": 5.52,  "profile": "hostelblock_real"},
}

# ── EMSController ─────────────────────────────────────────────────────────────
class EMSController:

    def __init__(self, pv_scale=1.0, ev_scale=1.0, load_scale=1.0):
        self.pv_scale   = pv_scale    # S2 cloudy=0.3, S5 no_solar=0.0
        self.ev_scale   = ev_scale    # S4 no_ev=0.0
        self.load_scale = load_scale  # S3 high_load=1.15
        self.step = 0
        self.soc_batt = 23.0  # initial SOC = 23% as specified
        self.soc_sc   = SC_SOC_INIT
        self.ev_session_active = False
        self.evening_grid_mode = False
        self.prev_p_load = 0.0
        self.prev_p_pv   = 0.0
        self.alerts = []
        self.log    = []
        self.bess_charged_kwh    = 0.0
        self.bess_discharged_kwh = 0.0
        self.ev_energy_kwh_cum   = 0.0
        self.pv_total_kwh_cum    = 0.0
        self.grid_import_kwh_cum = 0.0
        self.co2_saved_cum       = 0.0
        self.voltage_violation_steps = 0   # NEW: count of steps with >=1 bus violation

        print("=" * 70)
        print("  EMS Controller initialised")
        print(f"  Battery : {BESS_KWH} kWh / {BESS_KW} kW  SOC {BESS_SOC_MIN}%-{BESS_SOC_MAX}%")
        print(f"  SC      : {SC_KWH} kWh / {SC_KW} kW  SOC {SC_SOC_MIN}%-{SC_SOC_MAX}%")
        print(f"  EV      : real demand profile, peak 58.3 kW at 13:00, active 09:00-19:00")
        print(f"  Evening : {step_to_time(EVENING_START)}-{step_to_time(EVENING_END)}")
        print(f"  Peak shave limit : {EMS_PEAK_SHAVE_LIMIT} kW")
        print("=" * 70)

    def _get_load_kw(self, step):
        """
        Get faculty load kW for this step.
        Uses combined per-building-type profiles.
        Calibrated to match real meter data (peak 214.1 kW).
        """
        # Building peak kW and their profile types
        # Profile index: 0=Teaching 1=Library 2=Hostel 3=Canteen 4=Gym 5=Workshop 6=GuestHouse 7=Utility
        # Real data logger values where available, assumed otherwise
        # CivilDept  : real 13.50 kW (was assumed 23.69)
        # ElecDept   : real 33.33 kW (was assumed 23.69)
        # Workshop   : real  3.51 kW (was assumed  0.31)
        civil_peak      = 13.45   # real data logger
        mech_peak       = 13.45   # real data (civil data used)
        elec_peak       = ELEC_DEPT_PEAK_KW  # 33.33 real
        audit_peak      = 40.94   # real data logger
        lect_peak       =  8.15   # real data logger
        admin_peak      = 70.69   # real data logger
        library_peak    =  9.12   # real data logger
        hostel_peaks    = 9.44+9.44+5.52+5.52+5.52        # 35.44 kW real data
        canteen_peaks   = 12.65+0.001                       # 12.65 kW real data
        gym_peak        = 0.001  # zero load building
        workshop_peak   = 3.51   # real data logger
        guesthouse_peak = 0.001  # zero load building
        utility_peaks   = 0.12+0.45                              # 0.57 kW

        load = (
            # Teaching buildings
            civil_peak      * float(_LS_CIVIL_REAL[step])   +  # real
            mech_peak       * float(_LS_TEACHING[step])     +  # assumed
            elec_peak       * float(_LS_ELEC_DEPT[step])    +  # real
            audit_peak      * float(_LS_TEACHING[step])     +  # assumed
            lect_peak       * float(_LS_TEACHING[step])     +  # assumed
            admin_peak      * float(_LS_TEACHING[step])     +  # assumed
            # Other buildings
            library_peak    * float(_LS_LIBRARY[step])      +  # assumed
            hostel_peaks    * float(_LS_HOSTEL[step])       +  # assumed
            canteen_peaks   * float(_LS_CANTEEN[step])      +  # assumed
            gym_peak        * float(_LS_GYM[step])          +  # assumed
            workshop_peak   * float(_LS_WORKSHOP_REAL[step])+  # real (3.51kW)
            guesthouse_peak * float(_LS_GUESTHOUSE[step])   +  # assumed
            utility_peaks   * float(_LS_UTILITY[step])         # assumed
        )
        return round(load * self.load_scale, 2)

    def _get_pv_kw(self, step):
        """Get PV generation kW for this step from profile."""
        return float(_CLEAR_DAY_PU[step] * PV_TOTAL_KWP * self.pv_scale)

    def _read_soc(self):
        """
        Update SOC using energy balance — manual tracking.
        OpenDSS Storage in EXTERNAL DispMode does not auto-update SOC.
        SOC_new = SOC_old + delta_energy / total_capacity * 100
        """
        pass  # SOC is updated in _update_soc_manual after each step

    def _update_soc_manual(self, batt_state, batt_kw_abs, sc_state, sc_kw_abs):
        """Update SOC manually after each solve step."""
        dt = 0.25  # 15-min step = 0.25 hours
        EFF_CH = 0.97
        EFF_DC = 0.97

        # Battery SOC update
        if batt_state == "CHARGING":
            delta_batt = (batt_kw_abs * EFF_CH * dt) / BESS_KWH * 100.0
            self.soc_batt = min(self.soc_batt + delta_batt, BESS_SOC_MAX)
        elif batt_state == "DISCHARGING":
            delta_batt = (batt_kw_abs / EFF_DC * dt) / BESS_KWH * 100.0
            self.soc_batt = max(self.soc_batt - delta_batt, BESS_SOC_MIN)

        # SC SOC update
        if sc_state == "CHARGING":
            delta_sc = (sc_kw_abs * EFF_CH * dt) / SC_KWH * 100.0
            self.soc_sc = min(self.soc_sc + delta_sc, SC_SOC_MAX)
        elif sc_state == "DISCHARGING":
            delta_sc = (sc_kw_abs / EFF_DC * dt) / SC_KWH * 100.0
            self.soc_sc = max(self.soc_sc - delta_sc, SC_SOC_HARD_MIN)

        # Sync to OpenDSS
        cmd(f"Edit Storage.Battery %stored={self.soc_batt:.2f}")
        cmd(f"Edit Storage.SuperCap %stored={self.soc_sc:.2f}")

    def _cmd_battery(self, state, kw=0.0):
        kw = min(abs(kw), BESS_KW)
        cmd(f"Edit Storage.Battery State={state} kW={kw:.2f}")

    def _cmd_sc(self, state, kw=0.0):
        kw = min(abs(kw), SC_KW)
        cmd(f"Edit Storage.SuperCap State={state} kW={kw:.2f}")

    def _log_alert(self, msg):
        t = step_to_time(self.step)
        full = f"[{t}] {msg}"
        if full not in self.alerts:
            self.alerts.append(full)
            print(f"  *** {full}")

    def _check_voltages(self, voltages, step):
        """
        NEW: Check all bus voltages against safe limits and log any violations
        to the same alert log used for battery/EV/peak-shave alerts.
        Previously this check existed in utils.py (check_voltage_violations)
        but was never actually called anywhere in the simulation loop.
        """
        violations = [
            (bus, v, "OVERVOLTAGE" if v > V_MAX_PU else "UNDERVOLTAGE")
            for bus, v in voltages.items()
            if v > V_MAX_PU or (v < V_MIN_PU and v > 0.5)
        ]
        if violations:
            self.voltage_violation_steps += 1
            for bus, v, status in violations:
                self._log_alert(f"VOLTAGE {status}: {bus} = {v:.4f} pu")
        return violations

    def _run_sc_logic(self, p_load, p_pv):
        sc_kw    = 0.0
        sc_state = "IDLING"
        delta_load = abs(p_load - self.prev_p_load)
        delta_pv   = abs(p_pv   - self.prev_p_pv)
        spike = max(delta_load, delta_pv)

        if spike > EMS_SC_SPIKE_KW and self.soc_sc > SC_SOC_HARD_MIN:
            sc_kw    = min(spike, SC_KW)
            sc_state = "DISCHARGING"
        elif self.soc_sc < SC_SOC_MAX:
            sc_state = "CHARGING"
            sc_kw    = 5.0

        if self.soc_sc <= SC_SOC_HARD_MIN:
            sc_state = "IDLING"
            sc_kw    = 0.0

        self._cmd_sc(sc_state, sc_kw)
        return sc_kw if sc_state == "DISCHARGING" else -sc_kw, sc_state

    def run_step(self, step, ev_connected=False):
        self.step = step
        t = step_to_time(step)

        # ── Get values from profiles (not from OpenDSS - bypasses loadshape bug)
        p_load = self._get_load_kw(step)
        p_pv   = self._get_pv_kw(step)

        # Apply load scaling to OpenDSS so voltages are correct
        load_mult = _WORKING_DAY_PU[step]
        cmd(f"Set LoadMult={load_mult:.4f}")

        # EV load from real measured profile
        # Profile already contains 0 for non-charging steps
        p_ev = float(_EV_PROFILE_KW[step] * self.ev_scale)
        self.ev_session_active = p_ev > 0.5  # True if EV is charging this step

        # SC logic
        sc_kw, sc_state = self._run_sc_logic(p_load, p_pv)
        sc_support = max(0.0, sc_kw)

        mode       = "NORMAL"
        batt_kw    = 0.0
        batt_state = "IDLING"
        grid_kw    = 0.0
        export_kw  = 0.0
        ev_alert   = False

        # ── PEAK SHAVING ──────────────────────────────────────────────────────
        total_demand  = p_load + p_ev
        net_demand    = total_demand - p_pv - sc_support
        peak_shave_kw = 0.0

        if net_demand > EMS_PEAK_SHAVE_LIMIT and self.soc_batt > BESS_SOC_MIN:
            peak_shave_kw = min(net_demand - EMS_PEAK_SHAVE_LIMIT, BESS_KW)
            mode = "PEAK_SHAVE"
            self._log_alert(f"INFO: Peak shaving {t} - BESS {peak_shave_kw:.1f} kW")

        # ── EVENING SUPPORT ───────────────────────────────────────────────────
        if is_evening(step) and not self.evening_grid_mode:
            if mode == "NORMAL":
                mode = "EVENING"
            if self.soc_batt <= EMS_EVENING_SOC_MIN:
                self.evening_grid_mode = True
                self.ev_session_active = False
                p_ev = 0.0
                self._log_alert("ALERT: Evening SOC reached 15% - grid taking over")

        if step > EVENING_END:
            self.evening_grid_mode = False

        # ── POWER DISPATCH ────────────────────────────────────────────────────
        remaining_pv = p_pv

        if peak_shave_kw > 0 and self.soc_batt > BESS_SOC_MIN:
            batt_state = "DISCHARGING"
            batt_kw    = -peak_shave_kw
        else:
            batt_at_max = self.soc_batt >= BESS_SOC_MAX
            batt_at_min = self.soc_batt <= BESS_SOC_MIN

            # B1 — charge battery from solar first
            if remaining_pv > 0 and not batt_at_max:
                charge_kw  = min(remaining_pv, BESS_KW)
                batt_state = "CHARGING"
                batt_kw    = charge_kw
                remaining_pv -= charge_kw

            # B2 — EV from remaining solar
            if self.ev_session_active:
                if remaining_pv > 0:
                    ev_solar  = min(remaining_pv, p_ev)
                    remaining_pv -= ev_solar
                    shortfall = p_ev - ev_solar
                    if shortfall > 0 and not batt_at_min:
                        ev_batt = min(shortfall, BESS_KW - abs(batt_kw))
                        batt_state = "DISCHARGING"
                        batt_kw   -= ev_batt
                        shortfall  -= ev_batt
                    if shortfall > 0:
                        ev_alert = True
                        self._log_alert("ALERT: EV needs grid - charging stopped")
                        self.ev_session_active = False
                        p_ev = 0.0
                elif not batt_at_min:
                    ev_batt = min(p_ev, BESS_KW - abs(batt_kw))
                    batt_state = "DISCHARGING"
                    batt_kw   -= ev_batt
                else:
                    ev_alert = True
                    self._log_alert("ALERT: EV needs grid - charging stopped")
                    self.ev_session_active = False
                    p_ev = 0.0

            # B3 — faculty load from remaining solar + grid
            # Only use battery for faculty load during EVENING support
            faculty_solar = min(remaining_pv, p_load)
            remaining_pv -= faculty_solar
            faculty_short = p_load - faculty_solar
            if faculty_short > 0 and not batt_at_min and batt_state != "CHARGING" and is_evening(step) and not self.evening_grid_mode:
                fac_batt = min(faculty_short, BESS_KW - abs(batt_kw))
                batt_state    = "DISCHARGING"
                batt_kw      -= fac_batt
                faculty_short -= fac_batt
            grid_kw = max(0.0, faculty_short)

            # B4 — export surplus
            if remaining_pv > 0:
                export_kw = remaining_pv

        # Battery SOC floor
        if self.soc_batt <= BESS_SOC_MIN and batt_state == "DISCHARGING":
            self._log_alert("ALERT: Battery SOC at minimum")
            batt_state = "IDLING"
            batt_kw    = 0.0

        # Send commands
        self._cmd_battery(batt_state, abs(batt_kw))
        cmd(f"Edit Load.EV kW={max(p_ev, 0.001):.3f}")

        # Solve
        cmd(f"Set Time={step * 0.25:.4f}")
        cmd("Solve")

        # Update SOC
        self._update_soc_manual(batt_state, abs(batt_kw), sc_state, abs(sc_kw))

        # Voltages + derived metrics
        voltages = self._calc_voltages(step)

        # NEW: check voltages against safe limits and log any violations
        voltage_violations = self._check_voltages(voltages, step)

        dt = 0.25
        if batt_state == "CHARGING":
            self.bess_charged_kwh    += abs(batt_kw) * dt
        elif batt_state == "DISCHARGING":
            self.bess_discharged_kwh += abs(batt_kw) * dt
        self.ev_energy_kwh_cum   += p_ev * dt
        self.pv_total_kwh_cum    += p_pv * dt
        self.grid_import_kwh_cum += grid_kw * dt
        co2_step = round(p_pv * dt * 0.72, 3)
        self.co2_saved_cum       += co2_step
        tx_loading = round((p_load + p_ev) / 1000.0 * 100.0, 2)
        ss_pct     = round(max(0.0,(p_load+p_ev-grid_kw)/max(p_load+p_ev,0.001)*100),1)
        net_grid   = round(grid_kw - export_kw, 2)

        self.prev_p_load = p_load
        self.prev_p_pv   = p_pv

        row = {
            "step": step, "time": t, "mode": mode,
            "p_pv_kw": round(p_pv,2), "p_load_kw": round(p_load,2),
            "p_ev_kw": round(p_ev,2), "batt_state": batt_state,
            "batt_kw": round(batt_kw,2), "soc_batt_pct": round(self.soc_batt,2),
            "sc_state": sc_state, "sc_kw": round(sc_kw,2),
            "soc_sc_pct": round(self.soc_sc,2), "grid_kw": round(grid_kw,2),
            "export_kw": round(export_kw,2), "net_grid_kw": net_grid,
            "peak_shave_kw": round(peak_shave_kw,2),
            "ev_alert": "YES" if ev_alert else "",
            "evening": "YES" if is_evening(step) else "",
            "voltage_violation": "YES" if voltage_violations else "",   # NEW column
            "transformer_loading_pct": tx_loading,
            "self_sufficiency_pct": ss_pct,
            "bess_charged_kwh_cum": round(self.bess_charged_kwh,2),
            "bess_discharged_kwh_cum": round(self.bess_discharged_kwh,2),
            "ev_energy_kwh_cum": round(self.ev_energy_kwh_cum,2),
            "pv_total_kwh_cum": round(self.pv_total_kwh_cum,2),
            "grid_import_kwh_cum": round(self.grid_import_kwh_cum,2),
            "co2_saved_kg_step": co2_step,
            "co2_saved_kg_cum": round(self.co2_saved_cum,2),
            **{f"v_{bus}_pu": voltages.get(bus,0.0) for bus in _BUS_CABLES},
        }
        self.log.append(row)

        batt_disp = f"{batt_kw:+.1f}kW" if batt_state != "IDLING" else "IDLE"
        print(f"  [{t}] {mode:<12} PV={p_pv:7.1f} Load={p_load:6.1f} "
              f"EV={p_ev:5.1f} BESS={batt_disp}({self.soc_batt:.0f}%) "
              f"Grid={grid_kw:6.1f}"
              f"{' SPIKE' if sc_state=='DISCHARGING' else ''}"
              f" V_Gym={voltages.get('gymbus',0.0):.3f}pu SS={ss_pct:.0f}%"
              f"{' SPIKE' if sc_state=='DISCHARGING' else ''}"
              f"{' EV-ALERT' if ev_alert else ''}"
              f"{' V-VIOLATION' if voltage_violations else ''}")
        return row

    def _calc_voltages(self, step):
        """Calculate voltage at all 24 LV buses analytically."""
        pv_irr = float(_CLEAR_DAY_PU[step] * self.pv_scale)
        p_ev   = float(_EV_PROFILE_KW[step] * self.ev_scale)
        profile_map = {
            "teaching"  : float(_LS_TEACHING[step]),
            "hostel"    : float(_LS_HOSTEL[step]),
            "canteen"   : float(_LS_CANTEEN[step]),
            "gym"       : float(_LS_GYM[step]),
            "workshop"  : float(_LS_WORKSHOP[step]),
            "guesthouse": float(_LS_GUESTHOUSE[step]),
            "utility"   : float(_LS_UTILITY[step]),
            "ev"        : 1.0 if p_ev > 0 else 0.0,
            "flat"      : 0.0,
        }
        voltages = {}
        for bus, data in _BUS_CABLES.items():
            pval   = profile_map.get(data["profile"], 0.0)
            net_kw = data["pv_kwp"] * pv_irr - data["load_peak"] * pval
            dV     = (net_kw * data["R"]) / (0.415**2 * 1000)
            voltages[bus] = round(1.000 + dV, 4)
        return voltages

    def save_results(self, filename="EMS_simulation.csv"):
        path = os.path.join(RESULTS_DIR, filename)
        if not self.log:
            return
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.log[0].keys()))
            writer.writeheader()
            writer.writerows(self.log)
        print(f"\n  Results saved -> {path}")
        alert_path = os.path.join(RESULTS_DIR, "EMS_alerts.txt")
        with open(alert_path, "w") as f:
            f.write("EMS ALERT LOG\n" + "="*50 + "\n")
            for a in self.alerts:
                f.write(a + "\n")
            if not self.alerts:
                f.write("No alerts.\n")
        print(f"  Alerts saved  -> {alert_path}")

    def print_summary(self):
        if not self.log:
            return
        dt = 0.25
        pv    = sum(r["p_pv_kw"]   for r in self.log) * dt
        load  = sum(r["p_load_kw"] for r in self.log) * dt
        ev    = sum(r["p_ev_kw"]   for r in self.log) * dt
        grid  = sum(r["grid_kw"]   for r in self.log) * dt
        exp   = sum(r["export_kw"] for r in self.log) * dt
        ps    = sum(1 for r in self.log if r["peak_shave_kw"] > 0)
        total = max(load + ev, 1)
        print("\n" + "="*70)
        print("  EMS DAILY SUMMARY")
        print("="*70)
        print(f"  PV generation     : {pv:.1f} kWh")
        print(f"  Faculty load      : {load:.1f} kWh")
        print(f"  EV load           : {ev:.1f} kWh")
        print(f"  Grid import       : {grid:.1f} kWh")
        print(f"  Grid export       : {exp:.1f} kWh")
        print(f"  Self-sufficiency  : {(1-grid/total)*100:.1f}%")
        print(f"  Peak shave steps  : {ps} x 15min")
        print(f"  EV alerts         : {sum(1 for r in self.log if r['ev_alert']=='YES')}")
        print(f"  Voltage violation steps : {self.voltage_violation_steps} x 15min")  # NEW
        print(f"  Final battery SOC : {self.log[-1]['soc_batt_pct']:.1f}%")
        print(f"  Final SC SOC      : {self.log[-1]['soc_sc_pct']:.1f}%")
        print("="*70)
