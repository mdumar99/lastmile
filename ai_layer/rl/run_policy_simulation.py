"""
run_policy_simulation.py
Phase D + E: Hooks the trained RL policy into the C++ engine
and runs a real simulation. Compares against rule-based baseline
with identical parameters and reports real delivery/energy numbers.
"""

import sys
sys.path.insert(0, ".")
import lastmile
import torch
import torch.nn as nn
import numpy as np
import json
import time

MODEL_FILE = "ai_layer/rl/policy_v2.pt"
MEAN_FILE  = "ai_layer/rl/state_mean_v2.npy"
STD_FILE   = "ai_layer/rl/state_std_v2.npy"

ROBOTS   = 100
DURATION = 28800
SEEDS    = 3   # run each scenario 3 times for statistical validity

# ── Load policy ────────────────────────────────────────────────
class ResidualBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim,dim), nn.LayerNorm(dim), nn.GELU(), nn.Dropout(0.2),
            nn.Linear(dim,dim), nn.LayerNorm(dim))
        self.act = nn.GELU()
    def forward(self, x): return self.act(x + self.block(x))

class ResMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.input  = nn.Linear(9, 256)
        self.res1   = ResidualBlock(256)
        self.res2   = ResidualBlock(256)
        self.res3   = ResidualBlock(256)
        self.output = nn.Linear(256, 3)
    def forward(self, x):
        x = torch.relu(self.input(x))
        x = self.res1(x); x = self.res2(x); x = self.res3(x)
        return self.output(x)

print("Loading policy...")
model = ResMLP()
model.load_state_dict(torch.load(MODEL_FILE))
model.eval()

state_mean = np.load(MEAN_FILE)
state_std  = np.load(STD_FILE)

hubs_np = np.array([[92.57,  74.63],
                    [498.45, 797.77],
                    [820.34, 286.75]])

# ── Policy function ────────────────────────────────────────────
decision_count = [0]
deliver_count  = [0]
recharge_count = [0]
wait_count     = [0]

def rl_policy(robot_id, battery, x, y, hub_dist,
              weather, sim_time, deliveries, recharges,
              nearby, max_queue):
    """Called by C++ engine at each DEPART decision."""
    state = np.array([
        battery / 100.0,
        min(hub_dist / 3000.0, 1.0),
        float(weather),
        (int((sim_time % 86400) // 3600) % 24) / 23.0,
        min(deliveries / 500.0, 1.0),
        min(recharges  / 30.0,  1.0),
        min(nearby     / 20.0,  1.0),
        min(max_queue  / 10.0,  1.0),
        0.5,  # time_since_recharge (not tracked per-robot here)
    ], dtype=np.float32)

    state_norm = (state - state_mean) / (state_std + 1e-8)
    with torch.no_grad():
        logits = model(torch.tensor(state_norm).unsqueeze(0))
        action = int(logits.argmax(1).item())

    decision_count[0] += 1
    if action == 0: deliver_count[0]  += 1
    elif action == 1: recharge_count[0] += 1
    else:             wait_count[0]     += 1
    return action

# ── Run experiments ────────────────────────────────────────────
print(f"\nRunning {SEEDS} seeds x 2 scenarios "
      f"({ROBOTS} robots, {DURATION}s each)...\n")

rb_results  = []   # rule-based
rl_results  = []   # RL policy

for seed in range(SEEDS):
    jam_prob  = 0.02
    fail_prob = 0.05

    # ── Rule-based run ────────────────────────────────────────
    print(f"Seed {seed+1}/{SEEDS} — Rule-based...")
    e1 = lastmile.SimEngine(robots=ROBOTS, duration=DURATION,
                             jam_prob=jam_prob, fail_prob=fail_prob)
    e1.set_log_path(f"data/logs/eval_rb_seed{seed}.csv")
    t0 = time.time()
    e1.run()
    rb_time = time.time() - t0
    s1 = e1.get_stats()
    rb_results.append(s1)
    print(f"  Deliveries: {s1['deliveries']:>6,}  "
          f"Energy: {s1['energy_kwh']:>7.2f} kWh  "
          f"Recharges: {s1['recharges']:>4}  "
          f"({rb_time:.1f}s)")

    # ── RL policy run ─────────────────────────────────────────
    print(f"Seed {seed+1}/{SEEDS} — RL policy...")
    decision_count[0] = deliver_count[0] = 0
    recharge_count[0] = wait_count[0]    = 0

    e2 = lastmile.SimEngine(robots=ROBOTS, duration=DURATION,
                             jam_prob=jam_prob, fail_prob=fail_prob)
    e2.set_log_path(f"data/logs/eval_rl_seed{seed}.csv")
    e2.set_policy(rl_policy)
    t0 = time.time()
    e2.run()
    rl_time = time.time() - t0
    s2 = e2.get_stats()
    rl_results.append(s2)
    print(f"  Deliveries: {s2['deliveries']:>6,}  "
          f"Energy: {s2['energy_kwh']:>7.2f} kWh  "
          f"Recharges: {s2['recharges']:>4}  "
          f"({rl_time:.1f}s)")
    print(f"  Policy decisions: {decision_count[0]:,}  "
          f"DELIVER={deliver_count[0]:,} "
          f"RECHARGE={recharge_count[0]:,} "
          f"WAIT={wait_count[0]:,}")
    print()

# ── Aggregate results ──────────────────────────────────────────
def mean_std(results, key):
    vals = [r[key] for r in results]
    return np.mean(vals), np.std(vals)

rb_del_m,  rb_del_s  = mean_std(rb_results,  "deliveries")
rl_del_m,  rl_del_s  = mean_std(rl_results,  "deliveries")
rb_eng_m,  rb_eng_s  = mean_std(rb_results,  "energy_kwh")
rl_eng_m,  rl_eng_s  = mean_std(rl_results,  "energy_kwh")
rb_rech_m, rb_rech_s = mean_std(rb_results,  "recharges")
rl_rech_m, rl_rech_s = mean_std(rl_results,  "recharges")
rb_fail_m, rb_fail_s = mean_std(rb_results,  "delivery_fails")
rl_fail_m, rl_fail_s = mean_std(rl_results,  "delivery_fails")

del_delta  = rl_del_m  - rb_del_m
del_pct    = del_delta  / rb_del_m * 100
eng_delta  = rl_eng_m  - rb_eng_m
eng_pct    = eng_delta  / rb_eng_m * 100
rech_delta = rl_rech_m - rb_rech_m

print(f"\n{'='*60}")
print(f"REAL SIMULATION RESULTS ({SEEDS} seeds, {ROBOTS} robots, 8h)")
print(f"{'='*60}")
print(f"\n{'Metric':<22} {'Rule-Based':>15} {'RL Policy':>15} {'Delta':>12}")
print(f"{'-'*64}")
print(f"{'Deliveries':<22} "
      f"{rb_del_m:>12.1f}±{rb_del_s:.0f} "
      f"{rl_del_m:>12.1f}±{rl_del_s:.0f} "
      f"{del_delta:>+10.1f} ({del_pct:+.1f}%)")
print(f"{'Energy (kWh)':<22} "
      f"{rb_eng_m:>12.1f}±{rb_eng_s:.0f} "
      f"{rl_eng_m:>12.1f}±{rl_eng_s:.0f} "
      f"{eng_delta:>+10.1f} ({eng_pct:+.1f}%)")
print(f"{'Recharges':<22} "
      f"{rb_rech_m:>12.1f}±{rb_rech_s:.0f} "
      f"{rl_rech_m:>12.1f}±{rl_rech_s:.0f} "
      f"{rech_delta:>+10.1f}")
print(f"{'Delivery fails':<22} "
      f"{rb_fail_m:>12.1f}±{rb_fail_s:.0f} "
      f"{rl_fail_m:>12.1f}±{rl_fail_s:.0f}")
print(f"{'='*60}")

verdict = "BETTER" if del_pct > 0 else "WORSE"
print(f"\nVerdict: RL policy is {verdict} than rule-based")
print(f"  Delivery improvement : {del_pct:+.2f}%")
print(f"  Energy change        : {eng_pct:+.2f}%")

# Save results
results_out = {
    "config": {"robots": ROBOTS, "duration": DURATION, "seeds": SEEDS},
    "rule_based": {
        "deliveries_mean": rb_del_m, "deliveries_std": rb_del_s,
        "energy_mean":     rb_eng_m, "energy_std":     rb_eng_s,
        "recharges_mean":  rb_rech_m,
    },
    "rl_policy": {
        "deliveries_mean": rl_del_m, "deliveries_std": rl_del_s,
        "energy_mean":     rl_eng_m, "energy_std":     rl_eng_s,
        "recharges_mean":  rl_rech_m,
    },
    "delta": {
        "deliveries_pct": del_pct,
        "energy_pct":     eng_pct,
        "recharges":      rech_delta,
    }
}

with open("ai_layer/rl/real_eval_results.json", "w") as f:
    json.dump(results_out, f, indent=2)
print(f"\nSaved -> ai_layer/rl/real_eval_results.json")
