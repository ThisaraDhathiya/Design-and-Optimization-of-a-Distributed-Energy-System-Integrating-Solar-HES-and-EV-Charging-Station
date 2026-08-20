"""
generate_plots.py
================================================================================
University of Ruhuna - Faculty of Engineering
EV Charging Station HESS - Thesis Results Plot Generator

HOW TO RUN:
    cd 03_Python_EMS
    python generate_plots.py

OUTPUT:
    All plots saved to: 05_Results/Plots/
================================================================================
"""

import os, sys, numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Paths ─────────────────────────────────────────────────────────────────────
RESULTS_DIR = os.path.join("C:\\", "Users", "HP", "Desktop",
              "University_EV_Charging_OpenDSS", "05_Results")
PLOTS_DIR   = os.path.join(RESULTS_DIR, "Plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

CSV_FILES = {
    'S1: Clear Day'  : os.path.join(RESULTS_DIR, "EMS_clear_day_normal_load.csv"),
    'S2: Cloudy Day' : os.path.join(RESULTS_DIR, "EMS_cloudy_day.csv"),
    'S3: High Load'  : os.path.join(RESULTS_DIR, "EMS_high_load.csv"),
    'S4: No EV'      : os.path.join(RESULTS_DIR, "EMS_no_ev.csv"),
    'S5: No Solar'   : os.path.join(RESULTS_DIR, "EMS_no_solar.csv"),
}

COLORS = {
    'S1: Clear Day'  : '#2196F3',
    'S2: Cloudy Day' : '#FF9800',
    'S3: High Load'  : '#F44336',
    'S4: No EV'      : '#4CAF50',
    'S5: No Solar'   : '#9C27B0',
}

plt.rcParams.update({
    'figure.dpi'      : 150,
    'font.size'       : 10,
    'axes.titlesize'  : 12,
    'axes.titleweight': 'bold',
    'axes.labelsize'  : 10,
    'axes.grid'       : True,
    'grid.alpha'      : 0.3,
    'legend.fontsize' : 9,
    'lines.linewidth' : 1.8,
})

# ── Load CSVs ─────────────────────────────────────────────────────────────────
print("Loading CSV files...")
dfs = {}
for name, path in CSV_FILES.items():
    if os.path.exists(path):
        dfs[name] = pd.read_csv(path)
        print("  OK: " + name)
    else:
        print("  MISSING: " + path)

if not dfs:
    print("No CSV files found.")
    sys.exit(1)

hours = np.arange(96) * 0.25
xticks      = list(range(0, 25, 2))
xticklabels = [str(h).zfill(2) + ":00" for h in xticks]

def save(fig, name):
    path = os.path.join(PLOTS_DIR, name)
    fig.savefig(path, bbox_inches='tight', dpi=150)
    plt.close(fig)
    print("  Saved: " + name)

TITLE_SUFFIX = "\nUniversity of Ruhuna EV Charging Station HESS"

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 1 — Daily Power Flow S1 Clear Day
# ══════════════════════════════════════════════════════════════════════════════
print("\nPlot 1: Daily Power Flow — S1 Clear Day")
if 'S1: Clear Day' in dfs:
    df  = dfs['S1: Clear Day']
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle("Daily Power Flow — S1: Clear Day" + TITLE_SUFFIX, fontsize=13, fontweight='bold')

    ax1.fill_between(hours, df['p_pv_kw'],   alpha=0.4, color='#FFC107', label='PV Generation')
    ax1.fill_between(hours, df['p_load_kw'], alpha=0.3, color='#F44336', label='Building Load')
    ax1.fill_between(hours, df['p_ev_kw'],   alpha=0.4, color='#9C27B0', label='EV Charging')
    ax1.plot(hours, df['grid_kw'].clip(lower=0), color='#F44336', lw=2, ls='--', label='Grid Import')
    ax1.plot(hours, df['export_kw'],              color='#4CAF50', lw=1.5, ls=':',  label='Grid Export')
    ax1.set_ylabel('Power (kW)')
    ax1.set_title('Power Flow')
    ax1.legend(loc='upper left', ncol=3, fontsize=8)
    ax1.set_ylim(bottom=0)

    ax2.fill_between(hours, df['soc_batt_pct'], alpha=0.4, color='#2196F3', label='BESS SOC')
    ax2.plot(hours, df['soc_batt_pct'], color='#1565C0', lw=2)
    ax2.axhline(90, color='red',    ls='--', lw=1, alpha=0.7, label='Max SOC (90%)')
    ax2.axhline(15, color='orange', ls='--', lw=1, alpha=0.7, label='Min SOC (15%)')
    ax2.set_xlabel('Time of Day')
    ax2.set_ylabel('SOC (%)')
    ax2.set_title('Battery State of Charge')
    ax2.legend(loc='upper left', fontsize=8)
    ax2.set_ylim(0, 100)
    ax2.set_xticks(xticks)
    ax2.set_xticklabels(xticklabels, rotation=45)
    plt.tight_layout()
    save(fig, 'Plot1_Daily_Power_Flow_S1.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 2 — Scenario Comparison Bar Chart
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 2: Scenario Comparison Bar Chart")
metrics = {
    'PV Generation\n(kWh)' : lambda d: d['p_pv_kw'].sum() * 0.25,
    'Grid Import\n(kWh)'   : lambda d: d['grid_kw'].clip(lower=0).sum() * 0.25,
    'Faculty Load\n(kWh)'  : lambda d: d['p_load_kw'].sum() * 0.25,
    'EV Energy\n(kWh)'     : lambda d: d['p_ev_kw'].sum() * 0.25,
}
fig, axes = plt.subplots(1, 4, figsize=(14, 5))
fig.suptitle("Scenario Comparison — Key Energy Metrics" + TITLE_SUFFIX, fontsize=13, fontweight='bold')
for ax, (label, fn) in zip(axes, metrics.items()):
    vals  = [fn(dfs[s]) for s in dfs]
    names = [s.replace(': ', '\n') for s in dfs]
    cols  = [COLORS[s] for s in dfs]
    bars  = ax.bar(names, vals, color=cols, edgecolor='white', linewidth=0.8)
    ax.set_title(label)
    ax.set_ylabel('kWh')
    mx = max(vals) if max(vals) > 0 else 1
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + mx*0.01,
                str(round(val)), ha='center', va='bottom', fontsize=8, fontweight='bold')
    ax.tick_params(axis='x', labelsize=7)
plt.tight_layout()
save(fig, 'Plot2_Scenario_Comparison_Bar.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 3 — BESS SOC All Scenarios
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 3: BESS SOC All Scenarios")
fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle("Battery SOC Profile — All Scenarios" + TITLE_SUFFIX, fontsize=13, fontweight='bold')
for name, df in dfs.items():
    ax.plot(hours, df['soc_batt_pct'], color=COLORS[name], label=name, lw=2)
ax.axhline(90, color='red',    ls='--', lw=1.2, alpha=0.6, label='Max SOC (90%)')
ax.axhline(15, color='orange', ls='--', lw=1.2, alpha=0.6, label='Min SOC (15%)')
ax.fill_between(hours, 15, 90, alpha=0.03, color='green')
ax.set_xlabel('Time of Day')
ax.set_ylabel('Battery SOC (%)')
ax.set_ylim(0, 100)
ax.set_xticks(xticks)
ax.set_xticklabels(xticklabels, rotation=45)
ax.legend(ncol=2, fontsize=9)
plt.tight_layout()
save(fig, 'Plot3_BESS_SOC_All_Scenarios.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 4 — Self-Sufficiency
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 4: Self-Sufficiency")
fig, ax = plt.subplots(figsize=(8, 5))
fig.suptitle("Daily Self-Sufficiency — All Scenarios" + TITLE_SUFFIX, fontsize=13, fontweight='bold')
names_ss, ss_vals, cols_ss = [], [], []
for name, df in dfs.items():
    demand = df['p_load_kw'].sum() + df['p_ev_kw'].sum()
    grid   = df['grid_kw'].clip(lower=0).sum()
    ss     = (demand - grid) / demand * 100 if demand > 0 else 0
    names_ss.append(name.replace(': ', '\n'))
    ss_vals.append(ss)
    cols_ss.append(COLORS[name])
bars = ax.bar(names_ss, ss_vals, color=cols_ss, edgecolor='white', linewidth=0.8)
ax.axhline(100, color='green', ls='--', lw=1, alpha=0.5)
ax.set_ylabel('Self-Sufficiency (%)')
ax.set_ylim(0, 110)
for bar, val in zip(bars, ss_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            str(round(val, 1)) + '%', ha='center', va='bottom', fontsize=10, fontweight='bold')
plt.tight_layout()
save(fig, 'Plot4_Self_Sufficiency.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 5 — Grid Import S1 vs S5
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 5: Grid Import S1 vs S5")
fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle("Grid Import: Clear Day vs No Solar" + TITLE_SUFFIX, fontsize=13, fontweight='bold')
if 'S1: Clear Day' in dfs:
    g1 = dfs['S1: Clear Day']['grid_kw'].clip(lower=0)
    ax.fill_between(hours, g1, alpha=0.4, color='#2196F3', label='S1: Clear Day')
    ax.plot(hours, g1, color='#1565C0', lw=2)
if 'S5: No Solar' in dfs:
    g5 = dfs['S5: No Solar']['grid_kw'].clip(lower=0)
    ax.fill_between(hours, g5, alpha=0.3, color='#9C27B0', label='S5: No Solar')
    ax.plot(hours, g5, color='#6A1B9A', lw=2)
ax.set_xlabel('Time of Day')
ax.set_ylabel('Grid Import (kW)')
ax.set_xticks(xticks)
ax.set_xticklabels(xticklabels, rotation=45)
ax.legend(fontsize=10)
ax.set_ylim(bottom=0)
plt.tight_layout()
save(fig, 'Plot5_Grid_Import_S1_vs_S5.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 6 — EV vs PV
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 6: EV vs PV")
if 'S1: Clear Day' in dfs:
    df = dfs['S1: Clear Day']
    fig, ax = plt.subplots(figsize=(12, 5))
    fig.suptitle("EV Charging vs PV Generation — S1: Clear Day" + TITLE_SUFFIX, fontsize=13, fontweight='bold')
    ax2 = ax.twinx()
    ax.fill_between(hours, df['p_pv_kw'], alpha=0.3, color='#FFC107', label='PV Generation')
    ax.plot(hours, df['p_pv_kw'], color='#F57F17', lw=2)
    ax2.fill_between(hours, df['p_ev_kw'], alpha=0.5, color='#9C27B0', label='EV Charging')
    ax2.plot(hours, df['p_ev_kw'], color='#6A1B9A', lw=2)
    ax.set_xlabel('Time of Day')
    ax.set_ylabel('PV Generation (kW)', color='#F57F17')
    ax2.set_ylabel('EV Charging (kW)', color='#6A1B9A')
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels, rotation=45)
    p1 = mpatches.Patch(color='#FFC107', alpha=0.6, label='PV Generation')
    p2 = mpatches.Patch(color='#9C27B0', alpha=0.6, label='EV Charging')
    ax.legend(handles=[p1, p2], loc='upper left')
    plt.tight_layout()
    save(fig, 'Plot6_EV_vs_PV.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 7 — PV Generation All Scenarios
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 7: PV Generation All Scenarios")
fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle("PV Generation Profile — All Scenarios" + TITLE_SUFFIX, fontsize=13, fontweight='bold')
for name, df in dfs.items():
    ax.plot(hours, df['p_pv_kw'], color=COLORS[name], label=name, lw=2)
ax.set_xlabel('Time of Day')
ax.set_ylabel('PV Generation (kW)')
ax.set_xticks(xticks)
ax.set_xticklabels(xticklabels, rotation=45)
ax.legend(ncol=2, fontsize=9)
ax.set_ylim(bottom=0)
plt.tight_layout()
save(fig, 'Plot7_PV_Generation_All_Scenarios.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 8 — Grid Import/Export Summary
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 8: Grid Import/Export Summary")
fig, ax = plt.subplots(figsize=(9, 5))
fig.suptitle("Daily Grid Import & Export — All Scenarios" + TITLE_SUFFIX, fontsize=13, fontweight='bold')
snames  = [s.replace(': ', '\n') for s in dfs]
imports = [dfs[s]['grid_kw'].clip(lower=0).sum() * 0.25 for s in dfs]
exports = [dfs[s]['export_kw'].sum() * 0.25 for s in dfs]
x = np.arange(len(snames))
w = 0.35
b1 = ax.bar(x - w/2, imports, w, label='Grid Import (kWh)',  color='#F44336', alpha=0.8)
b2 = ax.bar(x + w/2, exports, w, label='Grid Export (kWh)',  color='#4CAF50', alpha=0.8)
ax.set_ylabel('Energy (kWh)')
ax.set_xticks(x)
ax.set_xticklabels(snames, fontsize=9)
ax.legend()
for bar, val in zip(b1, imports):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
            str(round(val)), ha='center', va='bottom', fontsize=8, fontweight='bold', color='#B71C1C')
for bar, val in zip(b2, exports):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
            str(round(val)), ha='center', va='bottom', fontsize=8, fontweight='bold', color='#1B5E20')
plt.tight_layout()
save(fig, 'Plot8_Grid_Import_Export.png')

# ══════════════════════════════════════════════════════════════════════════════
# PLOT 9 — CO2 Savings
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 9: CO2 Savings")
EMISSION_FACTOR = 0.718  # kg CO2/kWh — Sri Lanka CEB grid 2023

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
fig.suptitle("CO2 Savings — All Scenarios" + TITLE_SUFFIX, fontsize=13, fontweight='bold')

co2_saved, co2_grid, names_co2 = [], [], []
for name, df in dfs.items():
    pv_kwh  = df['p_pv_kw'].sum() * 0.25
    g_kwh   = df['grid_kw'].clip(lower=0).sum() * 0.25
    co2_saved.append(pv_kwh * EMISSION_FACTOR)
    co2_grid.append(g_kwh  * EMISSION_FACTOR)
    names_co2.append(name.replace(': ', '\n'))

x = np.arange(len(names_co2))
w = 0.35
b1 = ax1.bar(x - w/2, co2_saved, w, label='CO2 Avoided by PV (kg)', color='#4CAF50', alpha=0.85)
b2 = ax1.bar(x + w/2, co2_grid,  w, label='CO2 from Grid Import (kg)', color='#F44336', alpha=0.85)
ax1.set_ylabel('CO2 (kg/day)')
ax1.set_title('Daily CO2 Avoided vs Grid CO2')
ax1.set_xticks(x)
ax1.set_xticklabels(names_co2, fontsize=8)
ax1.legend(fontsize=8)
mx1 = max(max(co2_saved), max(co2_grid)) if co2_saved else 1
for bar, val in zip(b1, co2_saved):
    if val > 0:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + mx1*0.01,
                str(round(val)), ha='center', va='bottom', fontsize=7, fontweight='bold', color='#1B5E20')
for bar, val in zip(b2, co2_grid):
    if val > 0:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + mx1*0.01,
                str(round(val)), ha='center', va='bottom', fontsize=7, fontweight='bold', color='#B71C1C')

net_co2  = [s - g for s, g in zip(co2_saved, co2_grid)]
cols_net = ['#4CAF50' if v >= 0 else '#F44336' for v in net_co2]
b3 = ax2.bar(names_co2, net_co2, color=cols_net, alpha=0.85, edgecolor='white')
ax2.axhline(0, color='black', lw=0.8)
ax2.set_ylabel('Net CO2 Benefit (kg/day)')
ax2.set_title('Net CO2 Benefit\n(PV Avoided minus Grid Emissions)')
mn = min(net_co2)
for bar, val in zip(b3, net_co2):
    offset = abs(mn) * 0.02 if val >= 0 else -abs(mn) * 0.08
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + offset,
            str(round(val)) + ' kg', ha='center', va='bottom', fontsize=8, fontweight='bold')
ax2.text(0.98, 0.02,
         'Emission factor: ' + str(EMISSION_FACTOR) + ' kg CO2/kWh\n(Sri Lanka CEB grid, 2023)',
         transform=ax2.transAxes, fontsize=7, ha='right', va='bottom', color='gray', style='italic')
plt.tight_layout()
save(fig, 'Plot9_CO2_Savings.png')

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("  ALL 9 PLOTS SAVED TO:")
print("  " + PLOTS_DIR)
print("="*55)
plots = [
    "Plot1_Daily_Power_Flow_S1.png",
    "Plot2_Scenario_Comparison_Bar.png",
    "Plot3_BESS_SOC_All_Scenarios.png",
    "Plot4_Self_Sufficiency.png",
    "Plot5_Grid_Import_S1_vs_S5.png",
    "Plot6_EV_vs_PV.png",
    "Plot7_PV_Generation_All_Scenarios.png",
    "Plot8_Grid_Import_Export.png",
    "Plot9_CO2_Savings.png",
]
for p in plots:
    print("  " + p)
