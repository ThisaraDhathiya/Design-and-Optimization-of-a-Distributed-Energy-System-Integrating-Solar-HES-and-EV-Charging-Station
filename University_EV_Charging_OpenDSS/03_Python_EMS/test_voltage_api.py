"""
test_voltage_api.py - Fixed version
Finds actual bus names then tests voltage reading methods
"""
import opendssdirect as dss
import math

MASTER = r"C:\Users\HP\Desktop\University_EV_Charging_OpenDSS\01_OpenDSS_Model\Master.dss"
BASE_LN_KV = 0.23960

print("Compiling and solving...")
dss.Text.Command("Clear")
dss.Text.Command(f"Compile [{MASTER}]")
dss.Text.Command("Set Mode=Snapshot")
dss.Text.Command("Solve")
print(f"Circuit: {dss.Circuit.Name()}  Buses: {dss.Circuit.NumBuses()}")
print()

# Step 1 - list ALL actual bus names
all_names = dss.Circuit.AllBusNames()
print("ALL BUS NAMES in circuit:")
for n in all_names:
    print(f"  [{n}]")
print()

# Step 2 - find gym bus name
gym_bus = None
for n in all_names:
    if "gym" in n.lower():
        gym_bus = n
        print(f"Found gym bus: [{gym_bus}]")

panel_bus = None
for n in all_names:
    if "panel" in n.lower():
        panel_bus = n
        print(f"Found panel bus: [{panel_bus}]")
print()

if not gym_bus:
    print("GymBus not found - check bus names above")
else:
    # Test Method A - AllBusMagPu with correction
    print(f"Method A: AllBusMagPu (corrected for 33kV base)")
    names_lower = [n.lower() for n in all_names]
    vpu = dss.Circuit.AllBusMagPu()
    idx = names_lower.index(gym_bus.lower())
    v_pu_wrong = vpu[idx * 3]
    v_pu_real  = v_pu_wrong * (33.0 / BASE_LN_KV)
    print(f"  Raw pu (33kV base): {v_pu_wrong:.6f}")
    print(f"  Real pu (0.24kV base): {v_pu_real:.4f}")
    print()

    # Test Method B - AllBusVmag (in Volts)
    print(f"Method B: AllBusVmag (in Volts)")
    try:
        vmag = dss.Circuit.AllBusVmag()
        v_volts = vmag[idx * 3]
        v_pu = v_volts / (BASE_LN_KV * 1000)
        print(f"  Vmag: {v_volts:.4f}  (if Volts -> {v_pu:.4f} pu)")
    except Exception as e:
        print(f"  Error: {e}")
    print()

    # Test Method C - SetActiveBus + Bus.Voltages
    print(f"Method C: SetActiveBus({gym_bus}) + Bus.Voltages()")
    try:
        dss.Circuit.SetActiveBus(gym_bus)
        v = dss.Bus.Voltages()  # complex [re,im,re,im,re,im]
        if v and len(v) >= 2:
            mag = math.sqrt(v[0]**2 + v[1]**2)
            pu  = mag / (BASE_LN_KV * 1000)
            print(f"  Complex[0,1]: {v[0]:.2f}, {v[1]:.2f}")
            print(f"  |V| phase1: {mag:.2f} V = {pu:.4f} pu")
        else:
            print(f"  Result: {v}")
    except Exception as e:
        print(f"  Error: {e}")
    print()

    # Test Method D - SetActiveBus + Bus.VMagAngle
    print(f"Method D: SetActiveBus({gym_bus}) + Bus.VMagAngle()")
    try:
        dss.Circuit.SetActiveBus(gym_bus)
        v = dss.Bus.VMagAngle()  # [mag1,ang1,mag2,ang2,mag3,ang3] in Volts
        if v and len(v) >= 1:
            print(f"  Result: {v[:4]}")
            pu = v[0] / (BASE_LN_KV * 1000)
            print(f"  Vmag phase1: {v[0]:.2f} V = {pu:.4f} pu")
        else:
            print(f"  Result: {v}")
    except Exception as e:
        print(f"  Error: {e}")
    print()

    # Test Method E - SetActiveBus + Bus.puVmagAngle
    print(f"Method E: SetActiveBus({gym_bus}) + Bus.puVmagAngle()")
    try:
        dss.Circuit.SetActiveBus(gym_bus)
        v = dss.Bus.puVmagAngle()
        if v and len(v) >= 1:
            print(f"  Result (raw pu): {v[:4]}")
            # Correct for wrong base
            pu_corrected = v[0] * (33.0 / BASE_LN_KV)
            print(f"  Real pu corrected: {pu_corrected:.4f}")
        else:
            print(f"  Result: {v}")
    except Exception as e:
        print(f"  Error: {e}")

print()
print("Done - send me this output!")
