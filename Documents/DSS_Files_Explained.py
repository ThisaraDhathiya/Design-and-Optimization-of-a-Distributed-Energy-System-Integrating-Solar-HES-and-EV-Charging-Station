# ============================================================
# ALL DSS FILES — EXPLAINED LINE BY LINE
# University of Ruhuna — EV Charging Station HESS
# Folder: 01_OpenDSS_Model\
# ============================================================
# OpenDSS reads DSS files like a script — top to bottom.
# Each line creates or sets something in the network model.
# Master.dss is the starting point — it calls all other files.
# ============================================================


# ════════════════════════════════════════════════════════════
# FILE 1: Master.dss  (21 active lines)
# PURPOSE: The main entry point. Defines the circuit and
#          calls all other DSS files in the correct order.
# ════════════════════════════════════════════════════════════

Clear
# Wipe OpenDSS memory clean before starting.
# Ensures no leftover data from a previous run.

New Circuit.RuhunaEngineering basekv=33 pu=1.00 angle=0 frequency=50 phases=3 bus1=SourceBus R1=0.001 X1=0.010
# Create the main circuit called "RuhunaEngineering".
# basekv=33        → the source voltage is 33 kV (CEB supply)
# pu=1.00          → voltage is exactly 1.0 per unit (normal, no sag)
# angle=0          → voltage angle = 0 degrees (reference bus)
# frequency=50     → Sri Lanka uses 50 Hz power system
# phases=3         → three-phase system
# bus1=SourceBus   → the grid connects at a bus called "SourceBus"
# R1=0.001 X1=0.010 → grid impedance (very small = strong grid source)
# This line represents the CEB 33kV feeder coming into campus.

Set DefaultBaseFreq=50
# Set 50 Hz as the default for all elements.

Set VoltageBases=[33, 0.415, 0.24]
# Tell OpenDSS what voltage levels exist in this network:
# 33 kV    → the 33kV high voltage side (CEB supply)
# 0.415 kV → the 415V LV network (3-phase campus distribution)
# 0.24 kV  → the 240V single-phase (canteens, security)
# OpenDSS uses this to calculate per-unit voltages correctly.

Set Algorithm=Newton
# Use Newton-Raphson power flow method.
# Most accurate method for LV networks.

Set MaxIter=100
# Maximum 100 iterations before giving up.
# Normal solution converges in 3-5 iterations.

Set Tolerance=0.0001
# Stop iterating when voltage change < 0.01% between iterations.
# This ensures accurate results.

Set Mode=Daily
# Time-series simulation mode.
# OpenDSS will use loadshapes to vary loads over 24 hours.

Set StepSize=15m
# Each time step = 15 minutes.
# 96 steps × 15 minutes = 24 hours.

New Transformer.TX_Main
~ Buses=[SourceBus, MainBus]
~ kVs=[33, 0.415]
~ kVAs=[1000, 1000]
~ %Z=5.04
~ Conn=Dyn11
# The 1000 kVA step-down transformer.
# Buses=[SourceBus, MainBus] → connects 33kV side to 415V side
# kVs=[33, 0.415]            → 33kV primary, 415V secondary
# kVAs=[1000, 1000]          → 1000 kVA rating on both sides
# %Z=5.04                    → transformer impedance 5.04% (nameplate value)
# Conn=Dyn11                 → Delta primary, Star secondary, 11 o'clock shift
# This is the campus main transformer that feeds the whole LV network.

Redirect Lines.dss
# Load the Lines.dss file now.
# This creates all 23 cable segments in the network.

Redirect Loads.dss
# Load the Loads.dss file now.
# This creates all 21 building loads.

Redirect PVSystem.dss
# Load PVSystem.dss now.
# This creates all 15 PV systems.

Redirect LoadShapes.dss
# Load LoadShapes.dss now.
# This creates all 14 load profiles (real + assumed + solar).

Redirect Battery.dss
# Load Battery.dss now.
# This creates the 600 kWh / 100 kW BESS.

Redirect SuperCap.dss
# Load SuperCap.dss now.
# This creates the 1.0 kWh / 100 kW supercapacitor.

CalcVoltageBases
# Calculate per-unit voltage base at every bus automatically.
# Must be called after all elements are defined.
# After this, all voltages can be expressed in per-unit (pu).

Set ControlMode=OFF
# Turn off OpenDSS automatic controllers.
# Python EMS controls everything manually — no auto switching.

Solve
# Run an initial power flow to check the circuit compiled correctly.
# If this succeeds, the model is ready for simulation.


# ════════════════════════════════════════════════════════════
# FILE 2: Lines.dss  (33 active lines)
# PURPOSE: Defines all cable types (linecodes) and all
#          cable segments connecting buildings to the network.
# ════════════════════════════════════════════════════════════

# ── SECTION A: LINECODES (cable type definitions) ──────────
# A linecode defines the electrical properties of one cable size.
# You define it once, then reference it by name for each cable segment.

New Linecode.XLPE_50_3ph  nphases=3 R1=0.387 X1=0.082 R0=1.161 X0=0.246 units=km normamps=144 emergamps=173
# 50mm² three-phase XLPE cable.
# R1=0.387 Ω/km  → positive sequence resistance (this is what causes voltage drop)
# X1=0.082 Ω/km  → positive sequence reactance
# R0, X0         → zero sequence values (for fault calculations)
# normamps=144   → maximum continuous current = 144 A
# emergamps=173  → emergency rating = 173 A (short duration)
# Used for: EV charging station cable (50m, 50mm²)

New Linecode.XLPE_60_3ph  nphases=3 R1=0.306 X1=0.081 R0=0.918 X0=0.243 units=km normamps=163 emergamps=196
# 60mm² three-phase XLPE cable.
# R1=0.306 Ω/km → less resistance than 50mm² (thicker = less resistance)
# Used for: Library/Auditorium feeder, HostelF cable

New Linecode.XLPE_70_3ph  nphases=3 R1=0.268 X1=0.080 R0=0.804 X0=0.240 units=km normamps=178 emergamps=214
# 70mm² three-phase XLPE cable.
# Used for: HostelC original cable (REPLACED by 95mm² — see upgrade below)

New Linecode.XLPE_75_3ph  nphases=3 R1=0.246 X1=0.080 R0=0.738 X0=0.240 units=km normamps=196 emergamps=235
# 75mm² three-phase XLPE cable.
# Used for: Workshop, HostelD, Gym, LTDB downstream cables

New Linecode.XLPE_75_1ph  nphases=1 R1=0.246 X1=0.080 units=km normamps=196 emergamps=235
# 75mm² SINGLE-phase XLPE cable.
# Used for: Canteen connections (single phase loads)

New Linecode.XLPE_95_3ph  nphases=3 R1=0.193 X1=0.073 R0=0.579 X0=0.219 units=km normamps=220 emergamps=264
# 95mm² three-phase XLPE cable.  ← ADDED during voltage mitigation study
# R1=0.193 Ω/km → less than 70mm² (0.268) → less voltage rise
# Used for: HostelC upgraded cable (was 70mm², upgraded to reduce V from 1.079 to 1.057 pu)

New Linecode.XLPE_120_3ph nphases=3 R1=0.153 X1=0.079 R0=0.459 X0=0.237 units=km normamps=247 emergamps=296
# 120mm² three-phase XLPE cable.
# Used for: BESS connection to MainBus (10m, high current path)

New Linecode.XLPE_150_3ph nphases=3 R1=0.124 X1=0.078 R0=0.372 X0=0.234 units=km normamps=272 emergamps=326
# 150mm² three-phase XLPE cable. Largest cable, lowest resistance.
# Used for: transformer to panel, department feeder, LTDB feeder

# ── SECTION B: CABLE SEGMENTS (actual connections) ─────────
# Format: New Line.Name  Bus1=FROM  Bus2=TO  LineCode=TYPE  Length=X  units=km

New Line.Tx_to_Panel      Bus1=MainBus      Bus2=PanelBus          LineCode=XLPE_150_3ph Length=0.008   units=km phases=3
# Transformer secondary (MainBus) to main LV panel room (PanelBus).
# Length = 8m, 150mm² — very short, heavy cable (high current from transformer)

New Line.Panel_Workshop   Bus1=PanelBus     Bus2=MechWorkshopBus   LineCode=XLPE_75_3ph  Length=0.02452 units=km phases=3
# Panel room to Mechanical Workshop. Length = 24.52m, 75mm².

New Line.Panel_HostelF    Bus1=PanelBus     Bus2=HostelFBus        LineCode=XLPE_60_3ph  Length=0.05297 units=km phases=3
# Panel room to Middle Hostel (HostelF). Length = 52.97m, 60mm².

New Line.Panel_GuestHouse Bus1=PanelBus     Bus2=GuestHouseBus     LineCode=XLPE_60_3ph  Length=0.08538 units=km phases=3
# Panel room to Guest House. Length = 85.38m, 60mm².

New Line.Panel_Auditorium Bus1=PanelBus     Bus2=AuditoriumBus     LineCode=XLPE_60_3ph  Length=0.16024 units=km phases=3
# Panel room to Auditorium. Length = 160.24m, 60mm².
# AuditoriumBus has 210 kWp PV — voltage rises to 1.073 pu at noon.

New Line.Panel_Library    Bus1=PanelBus     Bus2=LibraryBus        LineCode=XLPE_60_3ph  Length=0.25409 units=km phases=3
# Panel room to Library. Length = 254.09m, 60mm².
# LibraryBus has 125.1 kWp PV — voltage rises to 1.072 pu at noon.

New Line.Panel_CivilDept  Bus1=PanelBus     Bus2=CivilDeptBus      LineCode=XLPE_150_3ph Length=0.07187 units=km phases=3
New Line.Panel_MechDept   Bus1=PanelBus     Bus2=MechDeptBus       LineCode=XLPE_150_3ph Length=0.11326 units=km phases=3
New Line.Panel_ElecDept   Bus1=PanelBus     Bus2=ElecDeptBus       LineCode=XLPE_150_3ph Length=0.16446 units=km phases=3
# Department feeder: Panel → Civil(72m) → Mech(113m) → Elec(164m)
# 150mm² throughout — large cable because 3 big departments + 3 large PV systems.
# ElecDeptBus OK: 172.8 kWp PV on short 164m cable with 33.33 kW load → V=1.018 pu only.

New Line.Panel_LTDB       Bus1=PanelBus     Bus2=LTDBus            LineCode=XLPE_150_3ph Length=0.17649 units=km phases=3
# Panel to LT Distribution Board. Length = 176.49m, 150mm².
# LTDB is a second distribution point feeding Admin, LecTheatre, Hostels A/B, Canteens.

New Line.Panel_HostelC    Bus1=PanelBus     Bus2=HostelCBus        LineCode=XLPE_95_3ph  Length=0.37688 units=km phases=3
# Panel to HostelC. Length = 376.88m.
# UPGRADED from XLPE_70_3ph to XLPE_95_3ph (June 2026).
# Reason: 135.3 kWp PV caused 1.079 pu with 70mm² cable.
# After upgrade: V = 1.057 pu (within 1.06 pu limit). ← voltage mitigation

New Line.Panel_HostelD    Bus1=PanelBus     Bus2=HostelDBus        LineCode=XLPE_75_3ph  Length=0.57625 units=km phases=3
# Panel to HostelD. Length = 576.25m — very long feeder.
# HostelD PV (111.45 kWp) DISABLED because this long cable caused 1.086 pu.

New Line.HostelD_Gym      Bus1=HostelDBus   Bus2=GymBus            LineCode=XLPE_75_3ph  Length=0.13377 units=km phases=3
# HostelD to Gym. Length = 133.77m. Total from panel = 709m.
# Gym PV (171.8 kWp) DISABLED. Long cable caused 1.174 pu — worst violation.

New Line.Panel_EVBus      Bus1=PanelBus     Bus2=EVBus             LineCode=XLPE_50_3ph  Length=0.050   units=km phases=3
# Panel to EV charging station. Length = 50m, 50mm².
# EV charger modelled as a Load element that Python updates each step.

New Line.Panel_BESS       Bus1=PanelBus     Bus2=MainBus           LineCode=XLPE_120_3ph Length=0.010   units=km phases=3
# Panel to BESS. Length = 10m, 120mm². Short but heavy current cable.

New Line.LTDB_LecTheatre  Bus1=LTDBus       Bus2=LectureTheatreBus LineCode=XLPE_75_3ph  Length=0.01046 units=km phases=3
New Line.LTDB_Admin       Bus1=LTDBus       Bus2=AdminBus          LineCode=XLPE_75_3ph  Length=0.064   units=km phases=3
New Line.LTDB_PumpHouse   Bus1=LTDBus       Bus2=PumpHouseBus      LineCode=XLPE_75_3ph  Length=0.1306  units=km phases=3
New Line.LTDB_Security    Bus1=LTDBus       Bus2=SecurityBus       LineCode=XLPE_75_3ph  Length=0.16546 units=km phases=3
# LTDB downstream connections to teaching + utility buildings.

New Line.LTDB_UpperCanteen  Bus1=LTDBus.1         Bus2=UpperCanteenBus.1  LineCode=XLPE_75_1ph Length=0.10697 units=km phases=1
New Line.Upper_LowerCanteen Bus1=UpperCanteenBus.1 Bus2=LowerCanteenBus.1 LineCode=XLPE_75_1ph Length=0.03842 units=km phases=1
# Single-phase canteen feeds. .1 means phase 1 only.

New Line.LTDB_HostelB     Bus1=LTDBus       Bus2=BoysHostelBBus    LineCode=XLPE_75_3ph  Length=0.21008 units=km phases=3
New Line.LTDB_HostelA     Bus1=LTDBus       Bus2=GirlsHostelBus    LineCode=XLPE_75_3ph  Length=0.24411 units=km phases=3
New Line.LTDB_HostelBlock Bus1=LTDBus       Bus2=HostelBlockBus    LineCode=XLPE_75_3ph  Length=0.050   units=km phases=3
# Hostel connections from LTDB.


# ════════════════════════════════════════════════════════════
# FILE 3: Loads.dss  (21 active lines)
# PURPOSE: Defines all building electrical loads.
#          Each line = one building connected to the network.
# ════════════════════════════════════════════════════════════
# Format: New Load.Name  Bus1=BUS  Phases=  kV=  kW=  kvar=  pf=  Daily=PROFILE
#
# kW    = peak active power demand of this building
# kvar  = peak reactive power demand (from power factor)
# pf    = power factor (0 to 1.0)
# Daily = which loadshape profile to use (from LoadShapes.dss)
# model=1 = constant power load model (standard)

# ── REAL DATA LOGGER VALUES ─────────────────────────────────────────────────
New Load.ElecDept  Bus1=ElecDeptBus   Phases=3 kV=0.415 kW=33.33 kvar=7.45  pf=0.9759 Daily=LS_ElecDept
# Electrical Dept: REAL measured peak 33.33 kW (was assumed 23.69 kW, +41% higher)
# pf=0.9759 — REAL measured power factor (was assumed 0.90)
# Uses LS_ElecDept loadshape (real 96-step profile from data logger)

New Load.Workshop  Bus1=MechWorkshopBus Phases=3 kV=0.415 kW=3.51  kvar=5.90  pf=0.5114 Daily=LS_Workshop_Real
# Mechanical Workshop: REAL measured peak 3.51 kW (Phase 1 CT was reversed — corrected)
# pf=0.5114 — very low PF because of heavy inductive motors (lathes, drills)
# Uses LS_Workshop_Real loadshape (CT corrected real data)

New Load.CivilDept Bus1=CivilDeptBus  Phases=3 kV=0.415 kW=13.50 kvar=7.83  pf=0.8649 Daily=LS_Civil_Real
# Civil Dept: REAL measured peak 13.50 kW (was assumed 23.69 kW, -43% lower)
# Uses LS_Civil_Real loadshape (real data from logger)

# ── ASSUMED PROFILES (no logger data yet) ───────────────────────────────────
New Load.MechDept   Bus1=MechDeptBus       Phases=3 kV=0.415 kW=23.69 kvar=11.47 pf=0.90 Daily=LS_Teaching
New Load.Auditorium Bus1=AuditoriumBus     Phases=3 kV=0.415 kW=28.79 kvar=13.93 pf=0.90 Daily=LS_Teaching
New Load.LecTheatre Bus1=LectureTheatreBus Phases=3 kV=0.415 kW=28.79 kvar=13.93 pf=0.90 Daily=LS_Teaching
New Load.Admin      Bus1=AdminBus          Phases=3 kV=0.415 kW=20.81 kvar=10.07 pf=0.90 Daily=LS_Teaching
# Teaching buildings: assumed peak loads, pf=0.90 assumed, LS_Teaching profile

New Load.Library    Bus1=LibraryBus        Phases=3 kV=0.415 kW=12.11 kvar=5.86  pf=0.90 Daily=LS_Library
New Load.GuestHouse Bus1=GuestHouseBus     Phases=3 kV=0.415 kW=10.04 kvar=4.86  pf=0.90 Daily=LS_GuestHouse
New Load.HostelD    Bus1=HostelDBus        Phases=3 kV=0.415 kW=21.68 kvar=10.49 pf=0.90 Daily=LS_Hostel
New Load.HostelBlock Bus1=HostelBlockBus   Phases=3 kV=0.415 kW=6.27  kvar=3.03  pf=0.90 Daily=LS_Hostel
New Load.HostelF    Bus1=HostelFBus        Phases=3 kV=0.415 kW=0.02  kvar=0.01  pf=0.90 Daily=LS_Hostel
New Load.BoysHostelB Bus1=BoysHostelBBus   Phases=3 kV=0.415 kW=3.07  kvar=1.49  pf=0.90 Daily=LS_Hostel
New Load.GirlsHostel Bus1=GirlsHostelBus   Phases=3 kV=0.415 kW=5.68  kvar=2.75  pf=0.90 Daily=LS_Hostel
New Load.HostelC    Bus1=HostelCBus        Phases=3 kV=0.415 kW=4.58  kvar=2.22  pf=0.90 Daily=LS_Hostel
New Load.Gym        Bus1=GymBus            Phases=3 kV=0.415 kW=0.15  kvar=0.07  pf=0.90 Daily=LS_Gym
New Load.PumpHouse  Bus1=PumpHouseBus      Phases=3 kV=0.415 kW=0.12  kvar=0.06  pf=0.90 Daily=LS_Utility
New Load.Security   Bus1=SecurityBus       Phases=1 kV=0.24  kW=0.45  kvar=0.22  pf=0.90 Daily=LS_Utility
New Load.UpperCanteen Bus1=UpperCanteenBus.1 Phases=1 kV=0.24 kW=5.62 kvar=2.72  pf=0.90 Daily=LS_Canteen
New Load.LowerCanteen Bus1=LowerCanteenBus.1 Phases=1 kV=0.24 kW=0.17 kvar=0.08  pf=0.90 Daily=LS_Canteen

New Load.EV  Bus1=EVBus  Phases=3 kV=0.415 kW=0.001 kvar=0.001 pf=0.95 Daily=LS_Teaching model=1
# EV Charging Station: starts at 0.001 kW (almost zero — placeholder)
# Python EMS updates this every step: cmd("Edit Load.EV kW=82.8")
# pf=0.95 — modern EV chargers have active power factor correction
# This is not a fixed load — it changes every 15 minutes based on real profile


# ════════════════════════════════════════════════════════════
# FILE 4: PVSystem.dss  (15 active + 2 disabled = 17 total)
# PURPOSE: Defines one solar PV system for each building.
#          Each PV system connects to that building's bus.
# ════════════════════════════════════════════════════════════
# Format: New PVSystem.Name  Bus1=BUS  kVA=  Pmpp=  pf=  Daily=IRRADIANCE_PROFILE
#
# Pmpp  = peak DC power of panels (kWp) — this is the installed capacity
# kVA   = inverter AC rating (always slightly > Pmpp, ratio ~1.1)
# pf    = power factor (1.0 = unity, no reactive power)
# Daily = the irradiance profile (Ruhuna_Irradiance from PVGIS data)
# %cutin=5  = inverter starts when irradiance > 5% of peak
# %cutout=5 = inverter stops when irradiance drops below 5%

New PVSystem.PV_Admin        Bus1=AdminBus          Phases=3 kV=0.415 kVA=87.5  Pmpp=79.65  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
# Admin building: 79.65 kWp on AdminBus. Short cable → no overvoltage risk.

New PVSystem.PV_Library      Bus1=LibraryBus        Phases=3 kV=0.415 kVA=137.5 Pmpp=125.1  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
# Library: 125.1 kWp on LibraryBus. 254m cable → overvoltage 1.072 pu at noon.
# RECOMMENDED FIX: reduce to 97 kWp OR set pf=0.95

New PVSystem.PV_Auditorium   Bus1=AuditoriumBus     Phases=3 kV=0.415 kVA=230.8 Pmpp=210.0  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
# Auditorium: 210 kWp on AuditoriumBus. 160m cable → overvoltage 1.073 pu at noon.
# RECOMMENDED FIX: reduce to 155 kWp OR set pf=0.95

New PVSystem.PV_LectureTheatre Bus1=LectureTheatreBus Phases=3 kV=0.415 kVA=230.8 Pmpp=210.0 pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_UpperCanteen Bus1=UpperCanteenBus   Phases=3 kV=0.415 kVA=45.2  Pmpp=41.1   pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_HostelA      Bus1=GirlsHostelBus    Phases=3 kV=0.415 kVA=64.0  Pmpp=58.2   pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_HostelB      Bus1=GirlsHostelBus    Phases=3 kV=0.415 kVA=34.9  Pmpp=31.8   pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
# HostelA and HostelB both connect to GirlsHostelBus (shared connection point)
# Total at GirlsHostelBus = 58.2 + 31.8 = 90.0 kWp → OpenDSS handles this correctly

New PVSystem.PV_HostelC      Bus1=HostelCBus        Phases=3 kV=0.415 kVA=148.7 Pmpp=135.3  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
# HostelC: 135.3 kWp. Cable upgraded to 95mm² → voltage now 1.057 pu (within limit).

New PVSystem.PV_ElecDept     Bus1=ElecDeptBus       Phases=3 kV=0.415 kVA=189.9 Pmpp=172.8  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_MechDept     Bus1=MechDeptBus       Phases=3 kV=0.415 kVA=189.9 Pmpp=172.8  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_CivilDept    Bus1=CivilDeptBus      Phases=3 kV=0.415 kVA=189.9 Pmpp=172.8  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_GuestHouse   Bus1=GuestHouseBus     Phases=3 kV=0.415 kVA=56.7  Pmpp=51.6   pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_HostelBlock  Bus1=HostelBlockBus    Phases=3 kV=0.415 kVA=35.4  Pmpp=32.25  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_Workshop     Bus1=MechWorkshopBus   Phases=3 kV=0.415 kVA=223.2 Pmpp=203.1  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5
New PVSystem.PV_LowerCanteen Bus1=LowerCanteenBus   Phases=3 kV=0.415 kVA=137.5 Pmpp=125.1  pf=1.0 Daily=Ruhuna_Irradiance %cutin=5 %cutout=5

!New PVSystem.PV_Gym     Bus1=GymBus     kVA=171.8 Pmpp=156.3  pf=1.0 Daily=Ruhuna_Irradiance
!New PVSystem.PV_HostelD Bus1=HostelDBus kVA=122.5 Pmpp=111.45 pf=1.0 Daily=Ruhuna_Irradiance
# ↑ DISABLED — ! at start = comment in OpenDSS (same as # in Python)
# Gym:    156.3 kWp on 709m cable with only 0.15 kW load → caused 1.174 pu OVERVOLTAGE
# HostelD: 111.45 kWp on 576m cable → caused 1.086 pu OVERVOLTAGE
# Solution: disable PV at these two buses → voltage drops to 1.000 pu


# ════════════════════════════════════════════════════════════
# FILE 5: LoadShapes.dss  (14 active lines)
# PURPOSE: Defines time-varying profiles used by Loads and PVSystems.
#          Each profile has 96 values (one per 15-minute step).
#          Values are multiplied by the peak kW to get actual demand.
# ════════════════════════════════════════════════════════════
# Format: New LoadShape.NAME  npts=96  interval=0.25  mult=(v1 v2 v3 ... v96)
#
# npts=96       = 96 data points
# interval=0.25 = 0.25 hours = 15 minutes between points
# mult=(...)    = 96 values from 0.0 to 1.0
#                 At each step: actual kW = peak kW × mult[step]

# ── REAL DATA LOGGER PROFILES ────────────────────────────────────────────────
New LoadShape.LS_ElecDept npts=96 interval=0.25 mult=(0.6350 0.6450 ... 0.6500)
# Electrical Dept real profile. Peak = 1.0 at step 44 (11:00).
# Night base = 0.55 (labs and servers never switch off).
# Source: elec_only_final_.xlsx, real measured data.

New LoadShape.LS_Workshop_Real npts=96 interval=0.25 mult=(0.4103 0.4131 ... 0.4160)
# Workshop real profile (CT Phase 1 corrected).
# Source: workshop_corrected.xlsx.

New LoadShape.LS_Civil_Real npts=96 interval=0.25 mult=(0.4163 0.3830 ... 0.3659)
# Civil Dept real profile.
# Source: civil_only_final.xlsx.

# ── ASSUMED PROFILES (used for buildings without real data yet) ──────────────
New LoadShape.LS_Teaching npts=96 interval=0.25 mult=(0.12 0.115 ... 0.15)
# Teaching buildings pattern: 0.10 at night, rises 08:00, peak 10:00-16:00, drops 17:00.
# Used for: MechDept, Auditorium, LecTheatre, Admin.

New LoadShape.LS_Library  npts=96 interval=0.25 mult=(0.08 0.077 ... 0.10)
# Library pattern: teaching hours + evening study (18:00-21:00).

New LoadShape.LS_Hostel   npts=96 interval=0.25 mult=(0.62 0.595 ... 0.65)
# Hostel pattern: base load all day, peak 18:00-23:00 (students return).
# Used for: all 6 hostel buildings.

New LoadShape.LS_Canteen  npts=96 interval=0.25 mult=(0.08 0.077 ... 0.08)
# Canteen pattern: three peaks — breakfast (07:00), lunch (12:00), dinner (18:00).

New LoadShape.LS_Gym      npts=96 interval=0.25 mult=(0.05 0.047 ... 0.05)
# Gym pattern: very low all day, peak 17:00-21:00 (after lectures).

New LoadShape.LS_Workshop npts=96 interval=0.25 mult=(0.10 0.10 ... 0.10)
# Workshop assumed (FALLBACK — replaced by LS_Workshop_Real when available).

New LoadShape.LS_GuestHouse npts=96 interval=0.25 mult=(0.40 0.38 ... 0.45)
# Guest house pattern: fairly constant with slight evening rise.

New LoadShape.LS_Utility  npts=96 interval=0.25 mult=(0.80 0.80 ... 0.80)
# Utility (pump, security): nearly flat all day (always running).

New LoadShape.Ruhuna_Irradiance npts=96 interval=0.25 mult=(0.0 0.0 ... 0.0)
# Solar irradiance profile for Matara, Sri Lanka.
# Source: PVGIS satellite data + PySAM processing.
# 0.0 from 18:00 to 05:15. Peaks at 1.0 at 12:00 noon.
# Used by ALL PVSystem elements (Daily=Ruhuna_Irradiance).

New LoadShape.FacultyWorkDay npts=96 interval=0.25 mult=(0.20 0.20 ... 0.20)
# Alternative full-day faculty profile (legacy, not currently used in main simulation).

New LoadShape.FacultyHoliday npts=96 interval=0.25 mult=(0.10 0.10 ... 0.10)
# Holiday pattern with reduced loads (legacy, not currently used).


# ════════════════════════════════════════════════════════════
# FILE 6: Battery.dss  (15 active lines)
# PURPOSE: Defines the 600 kWh / 100 kW BESS (LiFePO4).
#          Uses OpenDSS Storage element in EXTERNAL mode.
#          Python EMS controls all charging and discharging.
# ════════════════════════════════════════════════════════════

New Storage.Battery
~ Bus1=MainBus
# Connect BESS to MainBus (main 415V LV busbar after transformer).
# This is AC-coupled: BESS connects to AC bus via internal PCS inverter.

~ Phases=3
# Three-phase connection (balanced).

~ kV=0.415
# AC voltage = 415V line-to-line (campus LV standard).

~ kWhrated=600
# Total energy capacity = 600 kWh.
# This is the DC battery bank capacity.

~ kWrated=100
# Maximum charge AND discharge power = 100 kW.
# This is the PCS (Power Conversion System) inverter AC rating.
# Cannot charge faster than 100 kW or discharge faster than 100 kW.

~ %stored=23
# Initial SOC = 23% at the start of simulation.
# 23% of 600 kWh = 138 kWh stored at t=0.
# This was the measured SOC value when data was collected.

~ %reserve=15
# SOC floor = 15%. OpenDSS will not go below this.
# Protects LiFePO4 cells from deep discharge damage.
# 15% of 600 kWh = 90 kWh always kept in reserve.

~ %EffCharge=97
# Charging efficiency = 97%.
# When charging at 100 kW: only 97 kW actually goes into the battery.
# 3% lost as heat in the PCS inverter.

~ %EffDischarge=97
# Discharging efficiency = 97%.
# When 100 kW is needed: battery must release 100/0.97 = 103 kW.
# 3% lost as heat in the PCS inverter.
# Combined round-trip efficiency = 0.97 × 0.97 = 94.1%.

~ DispMode=EXTERNAL
# EXTERNAL mode = Python controls everything.
# OpenDSS will NOT auto-dispatch the battery.
# Python sends: cmd("Edit Storage.Battery State=CHARGING kW=50")
# If this was "DEFAULT" mode → OpenDSS would auto-charge/discharge (not what we want).

~ State=IDLING
# Start in IDLING state (not charging, not discharging).
# Python EMS will change this every step.


# ════════════════════════════════════════════════════════════
# FILE 7: SuperCap.dss  (1 active line)
# PURPOSE: Defines the 1.0 kWh / 100 kW Supercapacitor.
#          Same Storage element as battery but different sizes.
#          Also in EXTERNAL mode — Python EMS controls it.
# ════════════════════════════════════════════════════════════

New Storage.SuperCap Bus1=MainBus phases=3 kV=0.415 kWhrated=1.0 kWrated=100 %stored=80 %reserve=20 %EffCharge=97 %EffDischarge=97 DispMode=EXTERNAL State=IDLING
# Bus1=MainBus    → connects to 415V AC bus (AC-coupled, same as BESS)
# kWhrated=1.0    → only 1.0 kWh energy capacity (SC is a power device not energy device)
# kWrated=100     → 100 kW peak power (same as battery — fast response)
# %stored=80      → starts at 80% SOC (ready to respond)
# %reserve=20     → SOC floor = 20% (never drain completely)
# %EffCharge=97   → same efficiency as battery (inverter losses)
# %EffDischarge=97
# DispMode=EXTERNAL → Python controls SC dispatch, same as battery
# State=IDLING    → starts idle
#
# WHY SC?
# Battery ramp rate = 20 kW/s (safe for LiFePO4 longevity).
# EV spike = 82.8 kW in < 1 second.
# Battery needs 4.14 seconds to respond (τ = 82.8/20 = 4.14 s).
# SC covers this 4.14 second gap — SC responds in milliseconds.
# After 4.14s: battery has ramped up → SC stops → SC recharges from solar.
