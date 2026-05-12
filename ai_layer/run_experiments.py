"""
run_experiments.py
Uses the pybind11 bridge to run multiple simulation experiments
from Python, varying parameters and comparing results.
This replaces the manual before/after workflow with a
programmatic experiment runner.
"""

import sys
sys.path.insert(0, ".")   # finds lastmile.so in project root

import lastmile
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

os.makedirs("data/logs", exist_ok=True)

# ── Experiment 1: Robot count scaling ─────────────────────────
print("=" * 55)
print("Experiment 1: Throughput vs Fleet Size")
print("=" * 55)

robot_counts = [10, 25, 50, 100, 150, 200]
results_scale = []

for n in robot_counts:
    e = lastmile.SimEngine(robots=n, duration=3600)
    e.set_log_path(f"data/logs/exp_scale_{n}.csv")
    e.run()
    s = e.get_stats()
    dph = s['deliveries'] / 1.0   # per hour
    epd = s['energy_kwh'] / max(s['deliveries'], 1)
    results_scale.append({
        "robots":        n,
        "deliveries":    s['deliveries'],
        "energy_kwh":    round(s['energy_kwh'], 2),
        "delivery_rate": round(dph, 1),
        "energy_per_delivery": round(epd, 4),
    })
    print(f"  {n:>3} robots → {s['deliveries']:>5} deliveries  "
          f"{s['energy_kwh']:>7.2f} kWh  "
          f"{epd:.4f} kWh/delivery")

# ── Experiment 2: Hub strategy comparison ─────────────────────
print(f"\n{'=' * 55}")
print("Experiment 2: Hub Strategy vs Duration")
print("=" * 55)

durations = [1800, 3600, 7200, 14400, 28800]
results_hub = []

for dur in durations:
    # Hardcoded
    e1 = lastmile.SimEngine(robots=50, duration=dur)
    e1.set_log_path(f"data/logs/exp_base_{dur}.csv")
    e1.run()
    s1 = e1.get_stats()

    # MILP
    e2 = lastmile.SimEngine(robots=50, duration=dur)
    e2.set_hubs_csv("data/orders/hubs_optimised.csv")
    e2.set_log_path(f"data/logs/exp_milp_{dur}.csv")
    e2.run()
    s2 = e2.get_stats()

    delta = s2['deliveries'] - s1['deliveries']
    pct   = delta / max(s1['deliveries'], 1) * 100
    results_hub.append({
        "duration_h":    dur / 3600,
        "base_del":      s1['deliveries'],
        "milp_del":      s2['deliveries'],
        "delta":         delta,
        "improvement_%": round(pct, 1),
    })
    print(f"  {dur/3600:.1f}h → base={s1['deliveries']:>5}  "
          f"milp={s2['deliveries']:>5}  "
          f"delta=+{delta:>4}  ({pct:.1f}%)")

# ── Experiment 3: Battery threshold sensitivity ────────────────
print(f"\n{'=' * 55}")
print("Experiment 3: Battery Threshold Sensitivity")
print("=" * 55)

thresholds = [5, 10, 15, 20, 30, 40]
results_batt = []

for thr in thresholds:
    e = lastmile.SimEngine(robots=50, duration=3600, low_battery=thr)
    e.set_log_path(f"data/logs/exp_batt_{thr}.csv")
    e.run()
    s = e.get_stats()
    results_batt.append({
        "threshold_%": thr,
        "deliveries":  s['deliveries'],
        "recharges":   s['recharges'],
        "energy_kwh":  round(s['energy_kwh'], 2),
    })
    print(f"  threshold={thr:>2}% → {s['deliveries']:>5} deliveries  "
          f"{s['recharges']:>4} recharges  "
          f"{s['energy_kwh']:.2f} kWh")

# ── Plot results ───────────────────────────────────────────────
print("\nGenerating experiment dashboard...")

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.patch.set_facecolor("#0f1117")
fig.suptitle("Simulation Experiments — Python AI Layer via pybind11 Bridge",
             color="white", fontsize=13, fontweight="bold")

BG, CARD = "#0f1117", "#1a1a2e"
BLUE, GRN, YLW = "#3a7bd5", "#2ecc71", "#f6c90e"

# Plot 1: scaling
ax = axes[0]
ax.set_facecolor(CARD)
df1 = pd.DataFrame(results_scale)
ax.bar(df1['robots'], df1['deliveries'], color=BLUE, alpha=0.85)
ax2 = ax.twinx()
ax2.plot(df1['robots'], df1['energy_per_delivery'],
         'o-', color=YLW, linewidth=2, markersize=6)
ax.set_title("Fleet Size vs Throughput", color="white")
ax.set_xlabel("Number of robots", color="white")
ax.set_ylabel("Deliveries / hour", color="white")
ax2.set_ylabel("kWh per delivery", color=YLW)
ax.tick_params(colors="white")
ax2.tick_params(colors=YLW)
for s in ax.spines.values(): s.set_edgecolor("#333355")

# Plot 2: hub strategy
ax = axes[1]
ax.set_facecolor(CARD)
df2  = pd.DataFrame(results_hub)
xpos = np.arange(len(df2))
w    = 0.35
ax.bar(xpos - w/2, df2['base_del'], w, color="#e74c3c",
       alpha=0.85, label="Hardcoded")
ax.bar(xpos + w/2, df2['milp_del'], w, color=GRN,
       alpha=0.85, label="MILP")
ax.set_xticks(xpos)
ax.set_xticklabels([f"{h}h" for h in df2['duration_h']], color="white")
ax.set_title("Hub Strategy vs Duration", color="white")
ax.set_xlabel("Simulation duration", color="white")
ax.set_ylabel("Deliveries", color="white")
ax.legend(facecolor=CARD, labelcolor="white", fontsize=9)
ax.tick_params(colors="white")
for s in ax.spines.values(): s.set_edgecolor("#333355")

# Plot 3: battery threshold
ax = axes[2]
ax.set_facecolor(CARD)
df3 = pd.DataFrame(results_batt)
ax.plot(df3['threshold_%'], df3['deliveries'],
        'o-', color=BLUE, linewidth=2, markersize=7, label="Deliveries")
ax2 = ax.twinx()
ax2.plot(df3['threshold_%'], df3['recharges'],
         's--', color=YLW, linewidth=2, markersize=7, label="Recharges")
ax.set_title("Battery Threshold Sensitivity", color="white")
ax.set_xlabel("Low-battery threshold (%)", color="white")
ax.set_ylabel("Deliveries", color=BLUE)
ax2.set_ylabel("Recharge events", color=YLW)
ax.tick_params(colors="white")
ax2.tick_params(colors=YLW)
for s in ax.spines.values(): s.set_edgecolor("#333355")

plt.tight_layout()
plt.savefig("data/logs/experiments.png", dpi=150,
            facecolor=BG, bbox_inches="tight")
print("Saved → data/logs/experiments.png")
