"""
collect_experience.py
Runs the rule-based simulation and extracts (state, action, reward)
tuples for offline RL training.

State vector (6 features):
  [0] battery %            (normalised 0-1)
  [1] dist to nearest hub  (normalised 0-1)
  [2] weather multiplier   (0.4-1.0)
  [3] hour of day          (normalised 0-1)
  [4] deliveries so far    (normalised 0-1)
  [5] recharges so far     (normalised 0-1)

Action:
  0 = DELIVER
  1 = RECHARGE
  2 = WAIT (traffic jam)

Reward:
  +1.0  delivered
  -0.5  delivery failed
  -0.1  went to recharge
   0.0  waited
"""

import pandas as pd
import numpy as np
import json
import os
import sys
sys.path.insert(0, ".")
import lastmile

os.makedirs("ai_layer/rl", exist_ok=True)

print("Running simulation for experience collection...")
e = lastmile.SimEngine(robots=200, duration=28800,
                       low_battery=20.0,
                       jam_prob=0.02,
                       fail_prob=0.05)
e.set_log_path("data/logs/rl_collection.csv")
e.run()
stats = e.get_stats()
print(f"  Deliveries  : {stats['deliveries']:,}")
print(f"  Jams        : {stats['traffic_jams']:,}")
print(f"  Fails       : {stats['delivery_fails']:,}")

print("\nProcessing log into experience tuples...")
df = pd.read_csv("data/logs/rl_collection.csv")
df['note'] = df['note'].fillna('')   # replace NaN with empty string
print(f"  {len(df):,} raw events")

hubs = np.array([[92.57,  74.63],
                 [498.45, 797.77],
                 [820.34, 286.75]])

MAX_DIST     = 3000.0
MAX_DEL      = 200.0
MAX_RECHARGE = 20.0

experiences      = []
robot_deliveries = {}
robot_recharges  = {}

for rid in df['robot_id'].unique():
    robot_df = df[df['robot_id'] == rid].sort_values('time').reset_index(drop=True)
    robot_deliveries[rid] = 0
    robot_recharges[rid]  = 0

    for _, row in robot_df.iterrows():
        x, y     = row['x'], row['y']
        battery  = row['battery']
        sim_time = row['time']
        note     = str(row['note'])

        dists    = np.sqrt(((hubs - [x, y])**2).sum(axis=1))
        hub_dist = dists.min()
        hour     = int((sim_time % 86400) // 3600) % 24
        n_del    = robot_deliveries[rid]
        n_rech   = robot_recharges[rid]

        state = [
            battery / 100.0,
            min(hub_dist / MAX_DIST, 1.0),
            0.7,
            hour / 23.0,
            min(n_del  / MAX_DEL,      1.0),
            min(n_rech / MAX_RECHARGE, 1.0),
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
        else:
            continue

        experiences.append({
            "state":  state,
            "action": action,
            "reward": reward,
        })

print(f"  {len(experiences):,} experience tuples extracted")

actions = [e["action"] for e in experiences]
for a, label in [(0,"DELIVER"),(1,"RECHARGE"),(2,"WAIT")]:
    count = actions.count(a)
    print(f"  Action {a} ({label:8s}): {count:>6,} ({count/len(actions)*100:.1f}%)")

out_path = "ai_layer/rl/experience.json"
with open(out_path, "w") as f:
    json.dump(experiences, f)

print(f"\nSaved -> {out_path} ({os.path.getsize(out_path)//1024} KB)")
