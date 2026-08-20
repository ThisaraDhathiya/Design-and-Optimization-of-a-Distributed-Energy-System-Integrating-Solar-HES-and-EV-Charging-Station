"""
opendss_bridge_1s.py
================================================================================
REAL OpenDSS integration for the 1-second simulation, using opendssdirect.py
(same interface your main project's opendss_interface.py uses).

By default (config_1s.USE_OPENDSS_SOLVE = False) the EMS uses the analytical
voltage formula only (see ems_controller_1s.py _calc_voltages), which was
shown to reproduce your project's voltage results without the runtime cost
of 86,400 power-flow solves — because your original ems_controller.py never
actually reads voltages back from OpenDSS's own Solve() output either.

This module is for when you want OpenDSS's real Newton-Raphson power flow
actually in the loop — e.g. as a formal cross-check against the analytical
formula for your thesis, or because your supervisor wants genuine OpenDSS
solves. It compiles your real 01_OpenDSS_Model/Master.dss and pushes your
real per-second building/EV/PV/storage values into it every step.

Since real power-flow solves have per-call overhead, this module supports
DECIMATED solving via config_1s.OPENDSS_SOLVE_EVERY_N — e.g. solving every
10th second and holding the voltage result in between — see the timing
benchmark this script prints when run directly.
================================================================================
"""
import os
import opendssdirect as dss


class OpenDSSBridge1s:
    """Thin wrapper around opendssdirect.py for the 1-second simulation loop."""

    def __init__(self, master_dss_path):
        self.master_dss_path = master_dss_path
        self._compiled = False
        self.total_pv_kwp_dss = 0.0

    def compile(self):
        if not os.path.exists(self.master_dss_path):
            raise FileNotFoundError(f"Master.dss not found: {self.master_dss_path}")

        dss.Command("Clear")
        result = dss.Command(f"Compile [{self.master_dss_path}]")
        dss.Command("Set Mode=Snapshot")  # we drive every step manually — no internal auto-stepping
        self._compiled = True

        total = 0.0
        flag = dss.PVsystems.First()
        while flag > 0:
            total += dss.PVsystems.Pmpp()
            flag = dss.PVsystems.Next()
        self.total_pv_kwp_dss = total

        print(f"  [OpenDSS] Compiled: {os.path.basename(self.master_dss_path)}")
        print(f"  [OpenDSS] Circuit: {dss.Circuit.Name()}  "
              f"Buses: {dss.Circuit.NumBuses()}  Elements: {dss.Circuit.NumCktElements()}")
        print(f"  [OpenDSS] Total installed PV (Pmpp sum): {self.total_pv_kwp_dss:.2f} kWp")
        if result:
            print(f"  [OpenDSS] Compile message: {result}")

    def push_and_solve(self, building_loads, ev_kw, pv_total_kw,
                        batt_kw, batt_state, sc_kw, sc_state):
        """
        Push this step's real values into OpenDSS and solve.

        building_loads : dict {BuildingName: kW}  — must match Loads.dss names exactly
        ev_kw          : EV station kW this step
        pv_total_kw    : total campus PV kW this step (converted to a uniform
                          irradiance p.u. applied to every PVSystem, matching
                          the analytical model's uniform-irradiance assumption)
        batt_kw, sc_kw : magnitude (sign doesn't matter, state sets direction)
        batt_state, sc_state : "CHARGING" / "DISCHARGING" / "IDLING"

        Returns: (converged: bool, voltages: dict{bus_name: pu})
        """
        for name, kw in building_loads.items():
            dss.Command(f"Edit Load.{name} kW={max(kw, 0.001):.4f}")
        dss.Command(f"Edit Load.EV kW={max(ev_kw, 0.001):.4f}")

        irr_pu = 0.0 if self.total_pv_kwp_dss == 0 else min(max(pv_total_kw / self.total_pv_kwp_dss, 0.0), 1.3)
        dss.Command(f"BatchEdit PVSystem..* irradiance={irr_pu:.4f}")

        dss.Command(f"Edit Storage.Battery State={batt_state} kW={abs(batt_kw):.3f}")
        dss.Command(f"Edit Storage.SuperCap State={sc_state} kW={abs(sc_kw):.3f}")

        dss.Command("Solve")
        converged = dss.Solution.Converged()

        # Per-bus lookup (NOT a flat AllBusMagPu() scan) — buses have a
        # variable number of phases/nodes (e.g. LowerCanteenBus is 1-phase),
        # so a fixed "3 values per bus" assumption desyncs and corrupts every
        # bus after the first irregular one. SetActiveBus + puVmagAngle is
        # the robust per-bus approach (same as your main project's
        # opendss_interface.py get_bus_voltage_pu).
        voltages = {}
        try:
            for bus_name in dss.Circuit.AllBusNames():
                dss.Circuit.SetActiveBus(bus_name)
                vmag_ang = dss.Bus.puVmagAngle()  # [mag1, ang1, mag2, ang2, ...]
                mags = vmag_ang[0::2]
                mags = [m for m in mags if m > 0]
                if mags:
                    voltages[bus_name] = sum(mags) / len(mags)
        except Exception:
            pass
        return converged, voltages


def benchmark(master_dss_path, n_steps=200):
    """Quick timing test — run this file directly to see real solves/second
    on your machine before committing to a full 86,400-step OpenDSS run."""
    import time
    bridge = OpenDSSBridge1s(master_dss_path)
    bridge.compile()

    dummy_loads = {"ElecDept": 20.0, "Library": 5.0}  # partial dict is fine for a timing test
    t0 = time.time()
    for i in range(n_steps):
        bridge.push_and_solve(dummy_loads, ev_kw=10.0, pv_total_kw=500.0,
                               batt_kw=10.0, batt_state="CHARGING",
                               sc_kw=5.0, sc_state="IDLING")
    elapsed = time.time() - t0
    per_step_ms = elapsed / n_steps * 1000
    print(f"\n{n_steps} real OpenDSS solves in {elapsed:.2f}s "
          f"({per_step_ms:.2f} ms/step)")
    full_day_est_s = per_step_ms / 1000 * 86400
    print(f"Estimated full 86,400-step day: {full_day_est_s:.1f}s "
          f"({full_day_est_s/60:.1f} min)")
    print("If that's too slow, set OPENDSS_SOLVE_EVERY_N > 1 in config_1s.py "
          "to decimate (e.g. 10 = solve every 10th second, hold voltages between).")


if __name__ == "__main__":
    import config_1s
    benchmark(config_1s.MASTER_DSS)
