"""
opendss_interface.py
================================================================================
University of Ruhuna — Faculty of Engineering
OpenDSS Interface — all OpenDSS read/write operations in one place

This file wraps every OpenDSS interaction so ems_controller.py never
calls OpenDSS directly. If you switch from opendssdirect to win32com,
you only change this file — nothing else.

USAGE:
    from opendss_interface import OpenDSSInterface
    dss_if = OpenDSSInterface()
    dss_if.compile("path/to/Master.dss")
    p_pv = dss_if.get_total_pv_kw()
================================================================================
"""

import os
import opendssdirect as dss


class OpenDSSInterface:
    """
    Clean wrapper around opendssdirect.
    All EMS reads and writes go through this class.
    """

    def __init__(self):
        self._compiled = False

    # ── Initialise and compile ────────────────────────────────────────────────
    def compile(self, master_dss_path):
        """Load and compile the OpenDSS Master.dss file."""
        if not os.path.exists(master_dss_path):
            raise FileNotFoundError(f"Master.dss not found: {master_dss_path}")

        dss.run_command("Clear")
        result = dss.run_command(f"Compile [{master_dss_path}]")
        self._compiled = True

        print(f"  OpenDSS compiled: {os.path.basename(master_dss_path)}")
        print(f"  Circuit : {dss.Circuit.Name()}")
        print(f"  Buses   : {dss.Circuit.NumBuses()}")
        print(f"  Elements: {dss.Circuit.NumCktElements()}")
        if result:
            print(f"  Message : {result}")
        return result

    def set_daily_mode(self, stepsize="15m", algorithm="Newton"):
        """Configure OpenDSS for daily 15-min stepping."""
        dss.run_command(f"Set Mode=Daily")
        dss.run_command(f"Set StepSize={stepsize}")
        dss.run_command(f"Set Number=1")
        dss.run_command(f"Set Algorithm={algorithm}")
        dss.run_command(f"Set MaxIter=100")
        dss.run_command(f"Set Tolerance=0.0001")
        dss.run_command(f"Set FreqHz=50")

    def set_snapshot_mode(self):
        """Configure OpenDSS for single snapshot solve (for testing)."""
        dss.run_command("Set Mode=Snapshot")

    def solve(self):
        """Run one power flow solve."""
        dss.run_command("Solve")
        return dss.Solution.Converged()

    # ── READ — power measurements ─────────────────────────────────────────────
    def get_total_pv_kw(self):
        """
        Return total PV generation in kW across all 18 buildings.
        PVSystem output is negative in OpenDSS convention → take abs().
        """
        total = 0.0
        try:
            flag = dss.PVsystems.First()
            while flag > 0:
                total += abs(dss.PVsystems.kW())
                flag = dss.PVsystems.Next()
        except Exception:
            total = 0.0
        return round(total, 3)

    def get_faculty_load_kw(self):
        """
        Return total faculty building load in kW (excludes EV loads).
        """
        total = 0.0
        try:
            flag = dss.Loads.First()
            while flag > 0:
                name = dss.Loads.Name().upper()
                if "EV" not in name:
                    total += dss.Loads.kW()
                flag = dss.Loads.Next()
        except Exception:
            total = 0.0
        return round(total, 3)

    def get_ev_load_kw(self):
        """Return current EV load in kW."""
        total = 0.0
        try:
            flag = dss.Loads.First()
            while flag > 0:
                if "EV" in dss.Loads.Name().upper():
                    total += dss.Loads.kW()
                flag = dss.Loads.Next()
        except Exception:
            total = 0.0
        return round(total, 3)

    def get_battery_soc(self):
        """Return battery SOC as percentage (0–100)."""
        try:
            dss.run_command("? Storage.Battery.%stored")
            return float(dss.run_command(""))
        except Exception:
            # Alternative direct access
            try:
                flag = dss.Storages.First()
                while flag > 0:
                    if dss.Storages.Name().lower() == "battery":
                        return dss.Storages.puSOC() * 100.0
                    flag = dss.Storages.Next()
            except Exception:
                return 50.0  # fallback default

    def get_sc_soc(self):
        """Return supercapacitor SOC as percentage."""
        try:
            flag = dss.Storages.First()
            while flag > 0:
                if "supercap" in dss.Storages.Name().lower():
                    return dss.Storages.puSOC() * 100.0
                flag = dss.Storages.Next()
        except Exception:
            return 80.0
        return 80.0

    def get_grid_power_kw(self):
        """
        Return power drawn from grid (kW).
        Positive = import from grid, Negative = export to grid.
        Read from the Vsource element at SourceBus.
        """
        try:
            powers = dss.Circuit.TotalPower()
            # TotalPower returns [P_total, Q_total] — negative = source supplying
            return round(-powers[0], 3)
        except Exception:
            return 0.0

    def get_bus_voltage_pu(self, bus_name):
        """Return per-unit voltage at a named bus (average of phases)."""
        try:
            dss.run_command(f"? Bus.{bus_name}.puVmagAngle")
            result = dss.run_command("")
            # Parse result string — space separated values
            vals = [float(x) for x in result.split() if x]
            # puVmagAngle returns [mag1, ang1, mag2, ang2, mag3, ang3]
            magnitudes = vals[0::2]  # every other starting at 0
            return round(sum(magnitudes) / len(magnitudes), 5) if magnitudes else 1.0
        except Exception:
            return 1.0

    def get_transformer_loading_pct(self):
        """
        Return transformer loading as % of rated kVA.
        Read from the MainTransformer element.
        """
        try:
            dss.run_command("? Transformer.MainTransformer.%loaded")
            return float(dss.run_command(""))
        except Exception:
            # Alternative: compute from total power
            try:
                p = abs(self.get_grid_power_kw())
                return round(p / 1000.0 * 100.0, 2)  # 1000 kVA rated
            except Exception:
                return 0.0

    def get_all_bus_voltages(self):
        """Return dict of {bus_name: voltage_pu} for all buses."""
        voltages = {}
        try:
            names = dss.Circuit.AllBusNames()
            vmags = dss.Circuit.AllBusMagPu()
            # vmags is flat list — 3 values per bus (one per phase)
            idx = 0
            for name in names:
                phases = []
                for _ in range(3):
                    if idx < len(vmags) and vmags[idx] > 0:
                        phases.append(vmags[idx])
                    idx += 1
                if phases:
                    voltages[name] = round(sum(phases) / len(phases), 5)
        except Exception:
            pass
        return voltages

    # ── WRITE — commands to OpenDSS ───────────────────────────────────────────
    def set_battery_charging(self, kw):
        """Command battery to charge at kw (kW). Capped at rated power."""
        kw = min(abs(kw), 100.0)  # 100 kW rated
        dss.run_command(f"Edit Storage.Battery State=CHARGING kW={kw:.3f}")

    def set_battery_discharging(self, kw):
        """Command battery to discharge at kw (kW)."""
        kw = min(abs(kw), 100.0)
        dss.run_command(f"Edit Storage.Battery State=DISCHARGING kW={kw:.3f}")

    def set_battery_idle(self):
        """Command battery to idle (no charge or discharge)."""
        dss.run_command("Edit Storage.Battery State=IDLING kW=0")

    def set_sc_discharging(self, kw):
        """Command supercapacitor to discharge at kw (kW)."""
        kw = min(abs(kw), 100.0)
        dss.run_command(f"Edit Storage.SuperCap State=DISCHARGING kW={kw:.3f}")

    def set_sc_charging(self, kw):
        """Command supercapacitor to charge at kw (kW)."""
        kw = min(abs(kw), 100.0)
        dss.run_command(f"Edit Storage.SuperCap State=CHARGING kW={kw:.3f}")

    def set_sc_idle(self):
        dss.run_command("Edit Storage.SuperCap State=IDLING kW=0")

    def set_ev_load(self, kw):
        """
        Set EV charger active power.
        kw = 0 → no EV charging
        kw = 44 → both 22 kW chargers active
        """
        kw = max(kw, 0.001)  # OpenDSS does not accept exactly 0
        dss.run_command(f"Edit Load.EV_22kW kW={kw:.3f}")

    def enable_pv(self):
        """Enable all PV systems (restore after cloudy scenario)."""
        dss.run_command("BatchEdit PVSystem..* enabled=Yes")

    def disable_pv(self):
        """Disable all PV systems (for no-solar scenario)."""
        dss.run_command("BatchEdit PVSystem..* enabled=No")

    def scale_pv(self, factor):
        """
        Scale PV output by factor (e.g. 0.3 for cloudy = 30% output).
        Factor 1.0 = normal (clear day).
        """
        dss.run_command(f"BatchEdit PVSystem..* irradiance={factor:.3f}")

    def scale_loads(self, factor):
        """Scale all building loads by factor (for high/low load scenarios)."""
        dss.run_command(f"BatchEdit Load..* %growth=0")
        # Use AllocationFactor for scaling
        flag = dss.Loads.First()
        while flag > 0:
            if "EV" not in dss.Loads.Name().upper():
                base_kw = dss.Loads.kW()
                dss.Loads.kW(base_kw * factor)
            flag = dss.Loads.Next()

    def export_monitors(self, output_dir):
        """Export all OpenDSS monitor data to CSV files in output_dir."""
        os.makedirs(output_dir, exist_ok=True)
        dss.run_command(f"Set DataPath={output_dir}")
        dss.run_command("Export Monitors")
        print(f"  Monitor data exported to: {output_dir}")

    # ── Snapshot test helper ──────────────────────────────────────────────────
    def run_snapshot_test(self):
        """
        Quick sanity check — run a single snapshot solve and report
        key voltages and transformer loading.
        Call this BEFORE starting the daily simulation to verify DSS model.
        """
        print("\n" + "="*60)
        print("  SNAPSHOT POWER FLOW TEST")
        print("="*60)
        self.set_snapshot_mode()
        converged = self.solve()
        print(f"  Converged : {converged}")
        print(f"  Grid power: {self.get_grid_power_kw():.1f} kW")
        print(f"  PV output : {self.get_total_pv_kw():.1f} kW")
        print(f"  TX loading: {self.get_transformer_loading_pct():.1f}%")

        # Check key bus voltages
        key_buses = [
            "MainBus", "PanelBus", "GymBus", "BoysHostelWBus",
            "ElecDeptBus", "GirlsHostelBus",
        ]
        print(f"\n  Key bus voltages:")
        for bus in key_buses:
            v = self.get_bus_voltage_pu(bus)
            flag = "✓" if 0.94 <= v <= 1.06 else "⚠ VIOLATION"
            print(f"    {bus:<22} {v:.4f} pu  {flag}")

        print("="*60 + "\n")
        return converged
