"""
run_policy_simulation_v2.py
Same as v1 but with a safety constraint on the policy:
  - Policy can only choose RECHARGE if battery < 40%
  - Above 40%, policy can only choose DELIVER or WAIT
  - This prevents covariate shift causing over-recharging
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

ROBOTS              = 100
DURATION            = 28800
SEEDS               = 3
RECHARGE_GATE       = 40.0   # only allow RECHARGE below this battery %
RULE_BASED_FALLBACK = 20.0   # hard rule-based fallback below this %

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

decision_stats = {"deliver": 0, "recharge": 0, "wait": 0,
                  "forced_deliver": 0, "forced_recharge": 0}

def rl_policy_v2(robot_id, battery, x, y, hub_dist,
                 weather, sim_time, deliveries, recharges,
                 nearby, max_queue):
    # Hard rule: below 20% always recharge (rule-based safety)
    if battery < RULE_BASED_FALLBACK:
        decision_stats["forced_recharge"] += 1
        return 1

    state = np.array([
        battery / 100.0,
        min(hub_dist / 3000.0, 1.0),
        float(weather),
        (int((sim_time % 86400) // 3600) % 24) / 23.0,
        min(deliveries / 500.0, 1.0),
        min(recharges  / 30.0,  1.0),
        min(nearby     / 20.0,  1.0),
        min(max_queue  / 10.0,  1.0),
        0.5,
    ], dtype=np.float32)

    state_norm = (state - state_mean) / (state_std + 1e-8)
    with torch.no_grad():
        logits = model(torch.tensor(state_norm).unsqueeze(0))

        # Gate: if battery >= RECHARGE_GATE, mask out RECHARGE action
        if battery >= RECHARGE_GATE:
            logits[0, 1] = -1e9   # suppress RECHARGE
            decision_stats["forced_deliver"] += 1

        action = int(logits.argmax(1).item())

    if action == 0:   decision_stats["deliver"]  += 1
    elif action == 1: decision_stats["recharge"] += 1
    else:             decision_stats["wait"]      += 1
    return action

# ── Run experiments ────────────────────────────────────────────
print(f"\nRunning {SEEDS} seeds x 2 scenarios "
      f"({ROBOTS} robots, {DURATION}s)")
print(f"Recharge gate: {RECHARGE_GATE}%  "
      f"Rule-based fallback: {RULE_BASED_FALLBACK}%\n")

rb_results, rl_results = [], []

for seed in range(SEEDS):
    # Reset stats
    for k in decision_stats: decision_stats[k] = 0

    print(f"Seed {seed+1}/{SEEDS} — Rule-based...")
    e1 = lastmile.SimEngine(robots=ROBOTS, duration=DURATION)
    e1.set_log_path(f"data/logs/eval_v2_rb_seed{seed}.csv")
    t0 = time.time()
    e1.run()
    s1 = e1.get_stats()
    rb_results.append(s1)
    print(f"  Deliveries: {s1['deliveries']:>6,}  "
          f"Energy: {s1['energy_kwh']:>7.2f} kWh  "
          f"Recharges: {s1['recharges']:>4}  "
          f"({time.time()-t0:.1f}s)")

    print(f"Seed {seed+1}/{SEEDS} — RL policy v2 (gated)...")
    e2 = lastmile.SimEngine(robots=ROBOTS, duration=DURATION)
    e2.set_log_path(f"data/logs/eval_v2_rl_seed{seed}.csv")
    e2.set_policy(rl_policy_v2)
    t0 = time.time()
    e2.run()
    s2 = e2.get_stats()
    rl_results.append(s2)
    print(f"  Deliveries: {s2['deliveries']:>6,}  "
          f"Energy: {s2['energy_kwh']:>7.2f} kWh  "
          f"Recharges: {s2['recharges']:>4}  "
          f"({time.time()-t0:.1f}s)")
    print(f"  Decisions — DELIVER:{decision_stats['deliver']:,}  "
          f"RECHARGE:{decision_stats['recharge']:,}  "
          f"WAIT:{decision_stats['wait']:,}")
    print(f"  Forced    — deliver(gate):{decision_stats['forced_deliver']:,}  "
          f"recharge(rule):{decision_stats['forced_recharge']:,}")
    print()

# ── Results ────────────────────────────────────────────────────
def ms(results, key):
    v = [r[key] for r in results]
    return np.mean(v), np.std(v)

rb_del_m, rb_del_s = ms(rb_results, "deliveries")
rl_del_m, rl_del_s = ms(rl_results, "deliveries")
rb_eng_m, rb_eng_s = ms(rb_results, "energy_kwh")
rl_eng_m, rl_eng_s = ms(rl_results, "energy_kwh")
rb_rch_m, rb_rch_s = ms(rb_results, "recharges")
rl_rch_m, rl_rch_s = ms(rl_results, "recharges")

del_pct = (rl_del_m - rb_del_m) / rb_del_m * 100
eng_pct = (rl_eng_m - rb_eng_m) / rb_eng_m * 100

print(f"\n{'='*62}")
print(f"REAL SIMULATION RESULTS v2 — Gated Policy")
print(f"({SEEDS} seeds, {ROBOTS} robots, 8h, recharge gate={RECHARGE_GATE}%)")
print(f"{'='*62}")
print(f"\n{'Metric':<22} {'Rule-Based':>16} {'RL Gated':>16} {'Delta':>10}")
print(f"{'-'*66}")
print(f"{'Deliveries':<22} "
      f"{rb_del_m:>13.1f}±{rb_del_s:.0f} "
      f"{rl_del_m:>13.1f}±{rl_del_s:.0f} "
      f"{del_pct:>+9.1f}%")
print(f"{'Energy (kWh)':<22} "
      f"{rb_eng_m:>13.1f}±{rb_eng_s:.0f} "
      f"{rl_eng_m:>13.1f}±{rl_eng_s:.0f} "
      f"{eng_pct:>+9.1f}%")
print(f"{'Recharges':<22} "
      f"{rb_rch_m:>13.1f}±{rb_rch_s:.0f} "
      f"{rl_rch_m:>13.1f}±{rl_rch_s:.0f}")
print(f"{'='*62}")

verdict = "BETTER" if del_pct > 0 else "WORSE"
print(f"\nVerdict: RL gated policy is {verdict} than rule-based")
print(f"  Delivery delta : {del_pct:+.2f}%")
print(f"  Energy delta   : {eng_pct:+.2f}%")

results_out = {
    "version": "v2_gated",
    "config": {"robots": ROBOTS, "duration": DURATION,
               "seeds": SEEDS, "recharge_gate": RECHARGE_GATE},
    "rule_based": {"del_mean": rb_del_m, "del_std": rb_del_s,
                   "eng_mean": rb_eng_m, "eng_std": rb_eng_s},
    "rl_gated":   {"del_mean": rl_del_m, "del_std": rl_del_s,
                   "eng_mean": rl_eng_m, "eng_std": rl_eng_s},
    "delta": {"deliveries_pct": del_pct, "energy_pct": eng_pct}
}
with open("ai_layer/rl/real_eval_results_v2.json", "w") as f:
    json.dump(results_out, f, indent=2)
print(f"\nSaved -> ai_layer/rl/real_eval_results_v2.json")
