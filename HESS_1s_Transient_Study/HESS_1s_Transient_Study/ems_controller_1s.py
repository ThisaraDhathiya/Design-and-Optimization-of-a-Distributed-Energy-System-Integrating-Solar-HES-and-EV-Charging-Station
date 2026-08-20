"""
ems_controller_1s.py
================================================================================
1-second resolution EMS controller for the HESS transient / supercapacitor
study — University of Ruhuna, Faculty of Engineering.

This mirrors the dispatch logic in your main thesis project's
03_Python_EMS/ems_controller.py (peak shaving, solar-first battery charging,
EV solar/battery/grid fallback, evening support, spike-triggered SC dispatch)
exactly, with two changes required by the resolution change:

  1. dt = 1 second (1/3600 h) instead of 15 minutes (0.25 h) everywhere SOC or
     energy totals are integrated.
  2. Every load/PV/EV value is read from your real per-second CSV data
     instead of the 96-step per-unit profile arrays — this is the whole point
     of the exercise: real second-by-second variability is what makes the
     supercapacitor actually do something.

Results are written into PREALLOCATED numpy arrays (never appended to a list
or written to disk inside the loop) and saved to CSV once, at the end.
================================================================================
"""
import numpy as np
import pandas as pd
from config_1s import (
    BESS_KWH, BESS_KW, BESS_SOC_MIN, BESS_SOC_MAX, BESS_SOC_INIT,
    SC_KWH, SC_KW, SC_SOC_MIN, SC_SOC_MAX, SC_SOC_INIT, SC_SOC_HARD_MIN,
    EMS_SC_SPIKE_KW, EMS_PEAK_SHAVE_LIMIT,
    EVENING_START_STEP, EVENING_END_STEP, EMS_EVENING_SOC_MIN,
    PV_TOTAL_KWP, DT_HOURS, SIM_STEPS, V_MIN_PU, V_MAX_PU,
    BUS_CABLES, SRI_LANKA_CO2,
    SC_DISPATCH_MODE, SC_FILTER_TAU_S, SC_IDLE_THRESHOLD_KW,
    SC_TARGET_SOC_LOW, SC_TARGET_SOC_HIGH, SC_RECOVERY_KW,
    USE_OPENDSS_SOLVE, MASTER_DSS, OPENDSS_SOLVE_EVERY_N,
)


def step_to_time(step):
    h = step // 3600
    m = (step % 3600) // 60
    s = step % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def is_evening(step):
    return EVENING_START_STEP <= step <= EVENING_END_STEP


class EMSController1s:

    def __init__(self, loads_dict, ev_array, pv_array, dispatch_mode=None):
        self.loads = loads_dict
        self.ev_arr = ev_array
        self.pv_arr = pv_array
        # Which SC control logic to use this run — defaults to config_1s.SC_DISPATCH_MODE,
        # but can be overridden (e.g. by run_comparison_1s.py to run both modes back-to-back).
        self.sc_dispatch_mode = dispatch_mode if dispatch_mode is not None else SC_DISPATCH_MODE
        # Campus total load, vectorised once (not summed per-step in the loop)
        self.total_load_arr = np.sum(list(loads_dict.values()), axis=0)

        self.soc_batt = BESS_SOC_INIT
        self.soc_sc   = SC_SOC_INIT
        self.evening_grid_mode = False
        self.prev_p_load = 0.0
        self.prev_p_pv   = 0.0
        self.batt_target_ema = 0.0  # causal low-pass filter state, for SC_DISPATCH_MODE="filter"

        self.bess_charged_kwh    = 0.0
        self.bess_discharged_kwh = 0.0
        self.ev_energy_kwh_cum   = 0.0
        self.pv_total_kwh_cum    = 0.0
        self.grid_import_kwh_cum = 0.0
        self.co2_saved_cum       = 0.0
        self.voltage_violation_steps = 0
        self.alert_log = []

        n = SIM_STEPS
        self.res = {
            "step": np.arange(n),
            "p_pv_kw": np.zeros(n), "p_load_kw": np.zeros(n), "p_ev_kw": np.zeros(n),
            "p_net_kw": np.zeros(n),
            "batt_kw": np.zeros(n), "soc_batt_pct": np.zeros(n),
            "sc_kw": np.zeros(n), "soc_sc_pct": np.zeros(n),
            "grid_kw": np.zeros(n), "export_kw": np.zeros(n),
            "peak_shave_kw": np.zeros(n),
            "v_mainbus_pu": np.zeros(n),
            "ev_alert": np.zeros(n, dtype=bool),
            "voltage_violation": np.zeros(n, dtype=bool),
            "self_sufficiency_pct": np.zeros(n),
        }

        # ── Optional real OpenDSS integration ────────────────────────────────
        # Off by default (see config_1s.USE_OPENDSS_SOLVE docstring for why the
        # analytical formula is sufficient). When enabled, compiles your real
        # 01_OpenDSS_Model/Master.dss and solves it for real each step (or every
        # OPENDSS_SOLVE_EVERY_N steps, decimated).
        self.dss_bridge = None
        self._last_dss_voltages = {}
        if USE_OPENDSS_SOLVE:
            from opendss_bridge_1s import OpenDSSBridge1s
            self.dss_bridge = OpenDSSBridge1s(MASTER_DSS)
            self.dss_bridge.compile()

        print("=" * 70)
        print("  EMS Controller (1-second resolution) initialised")
        print(f"  Battery : {BESS_KWH} kWh / {BESS_KW} kW  SOC {BESS_SOC_MIN}-{BESS_SOC_MAX}%  init={BESS_SOC_INIT}%")
        print(f"  SC      : {SC_KWH} kWh / {SC_KW} kW  SOC {SC_SOC_MIN}-{SC_SOC_MAX}%  init={SC_SOC_INIT}%")
        mode_detail = {
            "filter": f"  (tau={SC_FILTER_TAU_S}s)",
            "threshold": f"  (spike>{EMS_SC_SPIKE_KW}kW)",
            "none": "  (SC DISABLED - ablation test)",
        }.get(self.sc_dispatch_mode, "")
        print(f"  SC dispatch mode : {self.sc_dispatch_mode.upper()}{mode_detail}")
        print(f"  Steps   : {SIM_STEPS} x 1s = 24h")
        print(f"  Campus peak load (from data) : {self.total_load_arr.max():.1f} kW")
        print(f"  PV peak (from data)          : {self.pv_arr.max():.1f} kW")
        print(f"  EV peak (from data)          : {self.ev_arr.max():.1f} kW")
        print("=" * 70)

    # ── Supercapacitor spike-detection logic (THRESHOLD mode — original) ────
    def _run_sc_logic_threshold(self, p_load, p_pv):
        spike = max(abs(p_load - self.prev_p_load), abs(p_pv - self.prev_p_pv))

        if spike > EMS_SC_SPIKE_KW and self.soc_sc > SC_SOC_HARD_MIN:
            sc_kw, sc_state = min(spike, SC_KW), "DISCHARGING"
        elif self.soc_sc < SC_SOC_MAX:
            sc_kw, sc_state = 5.0, "CHARGING"
        else:
            sc_kw, sc_state = 0.0, "IDLING"

        if self.soc_sc <= SC_SOC_HARD_MIN:
            sc_kw, sc_state = 0.0, "IDLING"

        return (sc_kw if sc_state == "DISCHARGING" else -sc_kw), sc_state

    # ── Supercapacitor filter-based dispatch (FILTER mode — recommended) ────
    #
    # Layer 1 (power allocation): a causal first-order low-pass filter (the
    # online/real-time equivalent of an RC filter) tracks the SLOW component
    # of net demand -> that's what the BESS is expected to cover. Whatever's
    # left over each second (the FAST residual) goes to the SC automatically
    # — no arbitrary spike threshold, just frequency separation.
    #
    # Layer 2 (SOC recovery): when the SC isn't actively responding to a
    # transient, a gentle bias nudges its SOC back toward a target band
    # (SC_TARGET_SOC_LOW - SC_TARGET_SOC_HIGH) so it's always ready for the
    # next event, without that recovery itself creating a new transient.
    def _run_sc_logic_filter(self, p_net):
        dt_s = 1.0  # this controller runs at 1-second steps
        alpha = dt_s / (SC_FILTER_TAU_S + dt_s)
        self.batt_target_ema += alpha * (p_net - self.batt_target_ema)
        p_sc_raw = p_net - self.batt_target_ema  # fast residual

        if abs(p_sc_raw) < SC_IDLE_THRESHOLD_KW:
            # No active transient -> SOC recovery layer takes over
            if self.soc_sc < SC_TARGET_SOC_LOW:
                p_sc_raw = -SC_RECOVERY_KW    # gentle trickle charge
            elif self.soc_sc > SC_TARGET_SOC_HIGH:
                p_sc_raw = SC_RECOVERY_KW     # gentle bleed-down
            else:
                p_sc_raw = 0.0

        sc_kw = float(np.clip(p_sc_raw, -SC_KW, SC_KW))

        # Hard SOC limit protection
        if sc_kw > 0 and self.soc_sc <= SC_SOC_HARD_MIN:
            sc_kw = 0.0
        if sc_kw < 0 and self.soc_sc >= SC_SOC_MAX:
            sc_kw = 0.0

        sc_state = "DISCHARGING" if sc_kw > 0 else ("CHARGING" if sc_kw < 0 else "IDLING")
        return sc_kw, sc_state

    def _run_sc_logic(self, p_load, p_pv, p_net):
        """Dispatches to the configured SC control mode (see config_1s.SC_DISPATCH_MODE,
        or the dispatch_mode passed to __init__).
        "none" fully disables the SC (always 0 kW) — used for the ablation test
        that asks "what changes if the supercapacitor isn't there at all?"."""
        if self.sc_dispatch_mode == "none":
            return 0.0, "IDLING"
        if self.sc_dispatch_mode == "filter":
            return self._run_sc_logic_filter(p_net)
        return self._run_sc_logic_threshold(p_load, p_pv)

    def _update_soc(self, batt_state, batt_kw_abs, sc_state, sc_kw_abs):
        dt = DT_HOURS
        EFF_CH, EFF_DC = 0.97, 0.97
        if batt_state == "CHARGING":
            self.soc_batt = min(self.soc_batt + (batt_kw_abs * EFF_CH * dt) / BESS_KWH * 100.0, BESS_SOC_MAX)
        elif batt_state == "DISCHARGING":
            self.soc_batt = max(self.soc_batt - (batt_kw_abs / EFF_DC * dt) / BESS_KWH * 100.0, BESS_SOC_MIN)

        if sc_state == "CHARGING":
            self.soc_sc = min(self.soc_sc + (sc_kw_abs * EFF_CH * dt) / SC_KWH * 100.0, SC_SOC_MAX)
        elif sc_state == "DISCHARGING":
            self.soc_sc = max(self.soc_sc - (sc_kw_abs / EFF_DC * dt) / SC_KWH * 100.0, SC_SOC_HARD_MIN)

    TRANSFORMER_KVA = 1000.0   # real nameplate rating (Transformer.dss)
    TRANSFORMER_PCT_Z = 5.04   # real nameplate %Z (Transformer.dss)

    def _calc_voltages(self, step, p_pv, grid_kw=None, export_kw=None):
        """
        Analytical bus voltage estimate — same R x P formula as your main
        project's _calc_voltages(), but now driven by real per-building kW
        from the loaded CSV data instead of a per-unit profile lookup.

        MainBus special case: in the original formula, MainBus has no
        building or PV directly attached to it (BUS_CABLES["mainbus"]:
        building=None, pv_kwp=0), so its own local net_kw is always 0 and
        its voltage is always exactly 1.0 pu — constant, and not useful for
        showing how battery/SC activity affects the common coupling point.

        MainBus sits immediately downstream of the 1000 kVA, %Z=5.04%
        MainTransformer (Bus1=MainBus in both Battery.dss and SuperCap.dss,
        i.e. the common coupling point). Its voltage is therefore estimated
        from the real transformer nameplate impedance and the net power
        flowing through it (export_kw - grid_kw), NOT the downstream cable
        resistance table used for individual buildings — reusing a cable R
        calibrated for single-building loads (tens of kW) against the full
        campus aggregate flow (up to ~1600 kW) produced physically
        implausible results (tens of per-unit) during initial testing.
            dV_pu = (net_kw / rated_kVA) x (%Z / 100)
        This is a first-order estimate (ignores power factor, treats
        kW~=kVA) but uses the real nameplate rating and impedance rather
        than an arbitrary or reused value.
        """
        irr_pu = 0.0 if PV_TOTAL_KWP == 0 else min(max(p_pv / PV_TOTAL_KWP, 0.0), 1.3)
        voltages = {}
        for bus, data in BUS_CABLES.items():
            if bus == "mainbus" and grid_kw is not None and export_kw is not None:
                net_kw = export_kw - grid_kw  # positive = net export (voltage rise)
                dV = (net_kw / self.TRANSFORMER_KVA) * (self.TRANSFORMER_PCT_Z / 100.0)
                voltages[bus] = 1.0 + dV
                continue
            building = data["building"]
            if building == "EV":
                load_kw = self.ev_arr[step]
            elif building is not None:
                load_kw = self.loads[building][step]
            else:
                load_kw = 0.0
            net_kw = data["pv_kwp"] * irr_pu - load_kw
            dV = (net_kw * data["R"]) / (0.415 ** 2 * 1000)
            voltages[bus] = 1.0 + dV
        return voltages

    def run_step(self, step):
        p_load = float(self.total_load_arr[step])
        p_ev   = float(self.ev_arr[step])
        p_pv   = float(self.pv_arr[step])
        p_net  = p_load + p_ev - p_pv   # total demand storage must cover, before SC/BESS/grid split

        sc_kw, sc_state = self._run_sc_logic(p_load, p_pv, p_net)
        sc_support = max(0.0, sc_kw)

        batt_kw, batt_state = 0.0, "IDLING"
        grid_kw, export_kw = 0.0, 0.0
        ev_alert = False

        total_demand  = p_load + p_ev
        net_demand    = total_demand - p_pv - sc_support
        peak_shave_kw = 0.0

        # ── Peak shaving ──────────────────────────────────────────────────
        if net_demand > EMS_PEAK_SHAVE_LIMIT and self.soc_batt > BESS_SOC_MIN:
            peak_shave_kw = min(net_demand - EMS_PEAK_SHAVE_LIMIT, BESS_KW)

        # ── Evening support ───────────────────────────────────────────────
        evening_now = is_evening(step)
        if evening_now and not self.evening_grid_mode:
            if self.soc_batt <= EMS_EVENING_SOC_MIN:
                self.evening_grid_mode = True
                self._log_alert(step, "ALERT: Evening SOC reached floor - grid taking over")
        if step > EVENING_END_STEP:
            self.evening_grid_mode = False

        # ── Power dispatch (same order as main project: peak-shave > BESS
        #     solar charge > EV solar/battery/grid > faculty load > export) ─
        remaining_pv = p_pv
        ev_session_active = p_ev > 0.05

        if peak_shave_kw > 0:
            batt_state, batt_kw = "DISCHARGING", -peak_shave_kw
        else:
            batt_at_max = self.soc_batt >= BESS_SOC_MAX
            batt_at_min = self.soc_batt <= BESS_SOC_MIN

            # B1 — charge battery from solar first
            if remaining_pv > 0 and not batt_at_max:
                charge_kw = min(remaining_pv, BESS_KW)
                batt_state, batt_kw = "CHARGING", charge_kw
                remaining_pv -= charge_kw

            # B2 — EV from remaining solar, else battery, else grid (flagged)
            if ev_session_active:
                if remaining_pv > 0:
                    ev_solar = min(remaining_pv, p_ev)
                    remaining_pv -= ev_solar
                    shortfall = p_ev - ev_solar
                    if shortfall > 0 and not batt_at_min:
                        ev_batt = min(shortfall, BESS_KW - abs(batt_kw))
                        batt_state = "DISCHARGING"
                        batt_kw   -= ev_batt
                        shortfall -= ev_batt
                    if shortfall > 0:
                        ev_alert = True
                elif not batt_at_min:
                    ev_batt = min(p_ev, BESS_KW - abs(batt_kw))
                    batt_state = "DISCHARGING"
                    batt_kw   -= ev_batt
                else:
                    ev_alert = True

            # B3 — faculty load from remaining solar, grid, or evening battery
            faculty_solar  = min(remaining_pv, p_load)
            remaining_pv  -= faculty_solar
            faculty_short  = p_load - faculty_solar
            if (faculty_short > 0 and not batt_at_min and batt_state != "CHARGING"
                    and evening_now and not self.evening_grid_mode):
                fac_batt = min(faculty_short, BESS_KW - abs(batt_kw))
                batt_state     = "DISCHARGING"
                batt_kw       -= fac_batt
                faculty_short -= fac_batt
            grid_kw = max(0.0, faculty_short)

            # B4 — export surplus
            if remaining_pv > 0:
                export_kw = remaining_pv

        # ── Connect the SC's power to the actual grid balance ──────────────
        # Previously, sc_kw only affected whether peak-shaving triggered (line
        # ~231) — it never actually reduced grid import or export, so the SC
        # could be fully active and change nothing measurable downstream.
        # The SC sits on the same AC bus as everything else: when it
        # discharges, that power directly reduces what the grid must supply
        # (or increases export if there's already a surplus); when it
        # charges, it directly increases grid import (or reduces export).
        # Applied last since the SC is the fastest-acting device, correcting
        # the balance the slower BESS/grid accounting above already set up.
        net_after_sc = grid_kw - export_kw - sc_kw
        grid_kw = max(0.0, net_after_sc)
        export_kw = max(0.0, -net_after_sc)

        if self.soc_batt <= BESS_SOC_MIN and batt_state == "DISCHARGING":
            batt_state, batt_kw = "IDLING", 0.0

        self._update_soc(batt_state, abs(batt_kw), sc_state, abs(sc_kw))

        if self.dss_bridge is not None:
            if step % OPENDSS_SOLVE_EVERY_N == 0:
                building_loads_now = {name: float(arr[step]) for name, arr in self.loads.items()}
                converged, voltages = self.dss_bridge.push_and_solve(
                    building_loads_now, p_ev, p_pv,
                    batt_kw, batt_state, sc_kw, sc_state,
                )
                self._last_dss_voltages = voltages
                if not converged:
                    self._log_alert(step, "WARNING: OpenDSS did not converge this step")
            else:
                voltages = self._last_dss_voltages  # hold last real solve between decimated steps
        else:
            voltages = self._calc_voltages(step, p_pv, grid_kw, export_kw)

        violation = any(v > V_MAX_PU or (v < V_MIN_PU and v > 0.5) for v in voltages.values())
        if violation:
            self.voltage_violation_steps += 1

        dt = DT_HOURS
        if batt_state == "CHARGING":
            self.bess_charged_kwh += abs(batt_kw) * dt
        elif batt_state == "DISCHARGING":
            self.bess_discharged_kwh += abs(batt_kw) * dt
        self.ev_energy_kwh_cum   += p_ev * dt
        self.pv_total_kwh_cum    += p_pv * dt
        self.grid_import_kwh_cum += grid_kw * dt
        self.co2_saved_cum       += p_pv * dt * SRI_LANKA_CO2

        total  = max(p_load + p_ev, 1e-6)
        ss_pct = max(0.0, (p_load + p_ev - grid_kw) / total * 100.0)

        r = self.res
        r["p_pv_kw"][step] = p_pv
        r["p_load_kw"][step] = p_load
        r["p_ev_kw"][step] = p_ev
        r["p_net_kw"][step] = p_net
        r["batt_kw"][step] = batt_kw
        r["soc_batt_pct"][step] = self.soc_batt
        r["sc_kw"][step] = sc_kw
        r["soc_sc_pct"][step] = self.soc_sc
        r["grid_kw"][step] = grid_kw
        r["export_kw"][step] = export_kw
        r["peak_shave_kw"][step] = peak_shave_kw
        r["v_mainbus_pu"][step] = voltages.get("mainbus", float("nan"))
        r["ev_alert"][step] = ev_alert
        r["voltage_violation"][step] = violation
        r["self_sufficiency_pct"][step] = ss_pct

        self.prev_p_load = p_load
        self.prev_p_pv   = p_pv

        if step % 3600 == 0:  # print once per simulated hour, not per second
            print(f"  [{step_to_time(step)}] PV={p_pv:7.1f} Load={p_load:6.1f} EV={p_ev:5.1f} "
                  f"BESS_SOC={self.soc_batt:5.1f}% SC_SOC={self.soc_sc:5.1f}% Grid={grid_kw:6.1f}")

    def _log_alert(self, step, msg):
        self.alert_log.append(f"[{step_to_time(step)}] {msg}")

    def run_all(self):
        for step in range(SIM_STEPS):
            self.run_step(step)

    def save_results(self, path_csv, path_alerts):
        pd.DataFrame(self.res).to_csv(path_csv, index=False)
        with open(path_alerts, "w") as f:
            f.write("EMS 1-SECOND ALERT LOG\n" + "=" * 50 + "\n")
            for a in self.alert_log:
                f.write(a + "\n")
            if not self.alert_log:
                f.write("No alerts.\n")

    def print_summary(self):
        dt = DT_HOURS
        r = self.res
        pv    = r["p_pv_kw"].sum() * dt
        load  = r["p_load_kw"].sum() * dt
        ev    = r["p_ev_kw"].sum() * dt
        grid  = r["grid_kw"].sum() * dt
        exp   = r["export_kw"].sum() * dt
        total = max(load + ev, 1)
        sc_active_s = int(np.sum(r["sc_kw"] > 0))

        print("\n" + "=" * 70)
        print("  EMS 1-SECOND DAILY SUMMARY")
        print("=" * 70)
        print(f"  PV generation        : {pv:.1f} kWh")
        print(f"  Faculty load         : {load:.1f} kWh")
        print(f"  EV load              : {ev:.1f} kWh")
        print(f"  Grid import          : {grid:.1f} kWh")
        print(f"  Grid export          : {exp:.1f} kWh")
        print(f"  Self-sufficiency     : {(1 - grid / total) * 100:.1f}%")
        print(f"  SC discharge time    : {sc_active_s} s  ({sc_active_s/3600:.2f} h)")
        print(f"  Voltage violation s  : {self.voltage_violation_steps}")
        print(f"  Final BESS SOC       : {self.soc_batt:.1f}%")
        print(f"  Final SC SOC         : {self.soc_sc:.1f}%")
        print("=" * 70)
