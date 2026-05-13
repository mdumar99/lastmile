"""
collect_experience_v2.py
Enhanced experience collection with 9 state features:

State vector:
  [0] battery %                    (0-1)
  [1] dist to nearest hub          (0-1, normalised)
  [2] weather speed multiplier     (0-1)
  [3] hour of day                  (0-1)
  [4] deliveries completed so far  (0-1)
  [5] recharges so far             (0-1)
  [6] nearby robot density         (robots within 300m, 0-1)
  [7] hub queue pressure           (max hub queue / num_robots, 0-1)
  [8] time since last recharge     (0-1, normalised)

Collected across multiple runs with different seeds for robustness.
"""

import pandas as pd
import numpy as np
import json
import os
import sys
sys.path.insert(0, ".")
import lastmile

os.makedirs("ai_layer/rl", exist_ok=True)

RUNS       = 5      # multiple seeds for robustness
ROBOTS     = 300
DURATION   = 28800

hubs = np.array([[92.57,  74.63],
                 [498.45, 797.77],
                 [820.34, 286.75]])

MAX_DIST      = 3000.0
MAX_DEL       = 500.0
MAX_RECHARGE  = 30.0
DENSITY_RADIUS= 300.0   # metres
MAX_DENSITY   = 20.0    # robots within radius
MAX_RECHARGE_T= 3600.0  # seconds since last recharge

def compute_density(robot_x, robot_y, all_states):
    """Count robots within DENSITY_RADIUS of this robot."""
    positions = np.array([[s[0], s[1]] for s in all_states])
    dists = np.sqrt(((positions - [robot_x, robot_y])**2).sum(axis=1))
    return (dists < DENSITY_RADIUS).sum() - 1  # exclude self

all_experiences = []

for run_idx in range(RUNS):
    seed = 42 + run_idx * 7
    print(f"\nRun {run_idx+1}/{RUNS} (seed variation {seed})...")

    # Vary parameters slightly across runs for robustness
    jam_prob  = 0.01 + run_idx * 0.01
    fail_prob = 0.03 + run_idx * 0.01

    e = lastmile.SimEngine(robots=ROBOTS, duration=DURATION,
                           low_battery=20.0,
                           jam_prob=jam_prob,
                           fail_prob=fail_prob)
    e.set_log_path(f"data/logs/rl_v2_run{run_idx}.csv")
    e.run()
    s = e.get_stats()

    # Get final robot states for density computation
    final_states = e.get_robot_states()
    hub_queues   = e.get_hub_queue_lengths()

    print(f"  Deliveries: {s['deliveries']:,}  "
          f"Jams: {s['traffic_jams']:,}  "
          f"Fails: {s['delivery_fails']:,}")

    df = pd.read_csv(f"data/logs/rl_v2_run{run_idx}.csv")
    df['note'] = df['note'].fillna('')
    print(f"  {len(df):,} raw events")

    robot_deliveries   = {}
    robot_recharges    = {}
    robot_last_recharge= {}
    run_experiences    = []

    for rid in df['robot_id'].unique():
        robot_df = df[df['robot_id'] == rid].sort_values('time').reset_index(drop=True)
        robot_deliveries[rid]    = 0
        robot_recharges[rid]     = 0
        robot_last_recharge[rid] = 0.0

        for _, row in robot_df.iterrows():
            x, y     = row['x'], row['y']
            battery  = row['battery']
            sim_time = row['time']
            note     = str(row['note'])

            # Core features
            dists    = np.sqrt(((hubs - [x, y])**2).sum(axis=1))
            hub_dist = dists.min()
            hour     = int((sim_time % 86400) // 3600) % 24
            n_del    = robot_deliveries[rid]
            n_rech   = robot_recharges[rid]

            # New feature: nearby robot density (from final state snapshot)
            # Approximation — use final positions as proxy
            density = compute_density(x, y, final_states)

            # New feature: hub queue pressure
            max_queue = max(hub_queues) if hub_queues else 0
            queue_pressure = max_queue / max(ROBOTS * 0.1, 1.0)

            # New feature: time since last recharge
            time_since_recharge = sim_time - robot_last_recharge[rid]

            state = [
                battery / 100.0,
                min(hub_dist / MAX_DIST, 1.0),
                0.7,  # weather (simplified)
                hour / 23.0,
                min(n_del  / MAX_DEL,      1.0),
                min(n_rech / MAX_RECHARGE, 1.0),
                min(density / MAX_DENSITY, 1.0),
                min(queue_pressure,        1.0),
                min(time_since_recharge / MAX_RECHARGE_T, 1.0),
            ]

            if note == 'depart->deliver':
                action, reward = 0, 0.0
            elif note == 'low_battery->hub':
                action, reward = 1, -0.1
                robot_recharges[rid] += 1
            elif 'traffic_jam' in note:
                action, reward = 2, 0.0
            elif note == 'delivered':
                action, reward = 0, +1.0
                robot_deliveries[rid] += 1
            elif note == 'delivery_failed':
                action, reward = 0, -0.5
            elif note == 'fully_charged':
                robot_last_recharge[rid] = sim_time
                continue
            else:
                continue

            run_experiences.append({
                "state":  state,
                "action": action,
                "reward": reward,
            })

    all_experiences.extend(run_experiences)
    print(f"  {len(run_experiences):,} tuples from this run")

print(f"\nTotal: {len(all_experiences):,} experience tuples")

actions = [e["action"] for e in all_experiences]
for a, label in [(0,"DELIVER"),(1,"RECHARGE"),(2,"WAIT")]:
    count = actions.count(a)
    print(f"  Action {a} ({label:8s}): {count:>7,} ({count/len(actions)*100:.1f}%)")

out_path = "ai_layer/rl/experience_v2.json"
with open(out_path, "w") as f:
    json.dump(all_experiences, f)

size_mb = os.path.getsize(out_path) / 1024 / 1024
print(f"\nSaved -> {out_path} ({size_mb:.1f} MB)")
print(f"State features: 9 (was 6)")
print(f"Runs: {RUNS} x {ROBOTS} robots x {DURATION}s")
