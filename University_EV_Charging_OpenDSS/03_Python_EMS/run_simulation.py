"""
run_simulation.py
================================================================================
University of Ruhuna - Faculty of Engineering
Main simulation entry point

HOW TO RUN:
    cd 03_Python_EMS
    python run_simulation.py
================================================================================
"""

import opendssdirect as dss
from config import MASTER_DSS, SIM_STEPS, SIM_STEPSIZE, SIM_ALGORITHM
from ems_controller import EMSController

EV_SCHEDULE = [False] * 96
for s in range(32, 57):
    EV_SCHEDULE[s] = True

def cmd(text):
    dss.Text.Command(text)

def init_opendss():
    print("Initialising OpenDSS...")
    cmd("Clear")
    cmd(f"Compile [{MASTER_DSS}]")
    cmd(f"Set Algorithm={SIM_ALGORITHM}")
    cmd("Set MaxIter=100")
    cmd("Set Tolerance=0.0001")
    cmd("Set Number=1")
    cmd(f"Set Stepsize={SIM_STEPSIZE}")
    print(f"  Circuit: {dss.Circuit.Name()}")
    print(f"  Buses  : {dss.Circuit.NumBuses()}")
    print(f"  Loads  : {dss.Loads.Count()}")
    print()

def run_daily_simulation(scenario_name="working_day", ev_schedule=None,
                         pv_scale=1.0, ev_scale=1.0, load_scale=1.0):
    if ev_schedule is None:
        ev_schedule = EV_SCHEDULE

    print(f"\n{'='*70}")
    print(f"  SCENARIO: {scenario_name.upper()}")
    print(f"  pv_scale={pv_scale}  ev_scale={ev_scale}  load_scale={load_scale}")
    print(f"{'='*70}\n")

    # Pass scenario parameters to EMS
    ems = EMSController(pv_scale=pv_scale, ev_scale=ev_scale, load_scale=load_scale)

    cmd("Set Mode=Daily")
    cmd("Set Number=1")

    for step in range(SIM_STEPS):
        ev_connected = ev_schedule[step] if ev_schedule else False
        ems.run_step(step, ev_connected=ev_connected)

    ems.print_summary()
    ems.save_results(filename=f"EMS_{scenario_name}.csv")
    return ems.log

# ── Scenario functions ────────────────────────────────────────────────────────

def scenario_clear_day():
    """S1: Clear day, normal load, EV charging active"""
    return run_daily_simulation("clear_day_normal_load",
                                ev_schedule=EV_SCHEDULE,
                                pv_scale=1.0, ev_scale=1.0, load_scale=1.0)

def scenario_cloudy_day():
    """S2: Cloudy day — PV reduced to 30% of clear day"""
    return run_daily_simulation("cloudy_day",
                                ev_schedule=EV_SCHEDULE,
                                pv_scale=0.3, ev_scale=1.0, load_scale=1.0)

def scenario_high_load():
    """S3: High load day — all building loads scaled x1.15"""
    return run_daily_simulation("high_load",
                                ev_schedule=EV_SCHEDULE,
                                pv_scale=1.0, ev_scale=1.0, load_scale=1.15)

def scenario_no_ev():
    """S4: No EV charging — EV demand set to zero"""
    return run_daily_simulation("no_ev",
                                ev_schedule=[False]*96,
                                pv_scale=1.0, ev_scale=0.0, load_scale=1.0)

def scenario_no_solar():
    """S5: No solar — PV generation set to zero (grid baseline)"""
    return run_daily_simulation("no_solar",
                                ev_schedule=EV_SCHEDULE,
                                pv_scale=0.0, ev_scale=1.0, load_scale=1.0)

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  UNIVERSITY OF RUHUNA - FACULTY OF ENGINEERING")
    print("  EV Charging Station EMS Simulation")
    print("="*70 + "\n")

    init_opendss()

    # All 5 scenarios run automatically
    scenario_clear_day()
    scenario_cloudy_day()
    scenario_high_load()
    scenario_no_ev()
    scenario_no_solar()

    print("\nSimulation complete.")
