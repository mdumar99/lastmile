"""
rolling_milp.py
Runs MILP hub optimisation on a rolling 30-day window.
Every 30 days of simulated time, re-solves the facility
location problem using only the most recent 30 days of orders.

Output: data/orders/rolling_hubs.csv
  day, hub_id, node_id, x, y, lat, lon, local_demand

Also outputs: data/orders/rolling_hubs_latest.csv
  The most recent hub solution (used by the simulation engine)
"""

import pandas as pd
import numpy as np
import highspy
import os
import time

NODES_FILE   = "data/osm/graph_nodes.csv"
ORDERS_FILE  = "data/orders/orders.csv"
ROLLING_OUT  = "data/orders/rolling_hubs.csv"
LATEST_OUT   = "data/orders/rolling_hubs_latest.csv"

NUM_HUBS       = 3
NUM_CANDIDATES = 50
WINDOW_DAYS    = 30
RANDOM_SEED    = 42

np.random.seed(RANDOM_SEED)

print("Loading data...")
nodes  = pd.read_csv(NODES_FILE).set_index("node_id")
orders = pd.read_csv(ORDERS_FILE)
total_days = int(orders['day'].max()) + 1
print(f"  {len(nodes):,} nodes, {len(orders):,} orders, {total_days} days")

def solve_milp(demand, candidates, nodes_idx, window_label):
    """Solve facility location MILP for a demand snapshot."""
    D  = demand[["x","y"]].values
    C  = candidates[["x","y"]].values
    dm = np.sqrt(((D[:,None,:] - C[None,:,:])**2).sum(axis=2))
    w  = demand["count"].values.astype(float)
    M, N = len(demand), len(candidates)

    h = highspy.Highs()
    h.silent()

    num_vars = N + M * N
    lb    = np.zeros(num_vars)
    ub    = np.ones(num_vars)
    costs = np.zeros(num_vars)
    for i in range(M):
        for j in range(N):
            costs[N + i*N + j] = w[i] * dm[i, j]

    h.addVars(num_vars, lb, ub)
    h.changeColsCost(num_vars,
                     np.arange(num_vars, dtype=np.int32),
                     costs)
    for j in range(N):
        h.changeColIntegrality(j, highspy.HighsVarType.kInteger)

    # Constraints
    h.addRow(float(NUM_HUBS), float(NUM_HUBS),
             N, np.arange(N, dtype=np.int32),
             np.ones(N, dtype=np.float64))

    for i in range(M):
        idx  = np.array([N+i*N+j for j in range(N)], dtype=np.int32)
        h.addRow(1.0, 1.0, N, idx, np.ones(N, dtype=np.float64))

    for i in range(M):
        for j in range(N):
            idx  = np.array([N+i*N+j, j], dtype=np.int32)
            vals = np.array([1.0, -1.0],  dtype=np.float64)
            h.addRow(-highspy.kHighsInf, 0.0, 2, idx, vals)

    h.run()

    sol      = h.getSolution()
    selected = [j for j in range(N) if sol.col_value[j] > 0.5]
    obj      = h.getInfoValue("objective_function_value")[1]

    results = []
    for rank, j in enumerate(selected):
        row = candidates.iloc[j]
        nid = int(row.node_id)
        results.append({
            "hub_id":       rank,
            "node_id":      nid,
            "x":            round(row.x, 2),
            "y":            round(row.y, 2),
            "lat":          round(nodes_idx.loc[nid, "lat"], 7),
            "lon":          round(nodes_idx.loc[nid, "lon"], 7),
            "local_demand": int(row["count"]),
            "objective":    round(obj, 0),
        })
    return results

# ── Rolling windows ────────────────────────────────────────────
all_results = []
windows = range(WINDOW_DAYS, total_days + 1, WINDOW_DAYS)

print(f"\nRunning rolling MILP every {WINDOW_DAYS} days...")
print(f"  Windows: {list(windows)}\n")

prev_hubs = None

for end_day in windows:
    start_day = end_day - WINDOW_DAYS
    label     = f"Day {start_day}-{end_day}"

    # Filter orders to this window
    window_orders = orders[
        (orders['day'] >= start_day) &
        (orders['day'] <  end_day)
    ]

    # Aggregate demand
    demand = window_orders.groupby("node_id").size().reset_index(name="count")
    demand = demand.merge(
        nodes[["x","y"]].reset_index(), on="node_id")

    # Candidates from top demand nodes
    top    = demand.nlargest(200, "count")
    cands  = top.sample(
        n=min(NUM_CANDIDATES, len(top)),
        random_state=end_day
    ).reset_index(drop=True)

    t0      = time.time()
    results = solve_milp(demand, cands, nodes, label)
    elapsed = time.time() - t0

    # Detect hub shifts
    shift_note = ""
    if prev_hubs is not None:
        prev_coords = set((r["x"], r["y"]) for r in prev_hubs)
        curr_coords = set((r["x"], r["y"]) for r in results)
        changed = len(prev_coords - curr_coords)
        shift_note = f"  {changed} hub(s) relocated" if changed else "  no change"

    print(f"  {label}: obj={results[0]['objective']:,.0f}  "
          f"solve={elapsed:.1f}s{shift_note}")
    for r in results:
        print(f"    Hub {r['hub_id']}: node={r['node_id']} "
              f"x={r['x']:.1f} y={r['y']:.1f} "
              f"demand={r['local_demand']}")

    for r in results:
        all_results.append({"day": end_day, **r})

    prev_hubs = results

# ── Save rolling history ───────────────────────────────────────
os.makedirs("data/orders", exist_ok=True)
rolling_df = pd.DataFrame(all_results)
rolling_df.to_csv(ROLLING_OUT, index=False)
print(f"\nSaved rolling history → {ROLLING_OUT}")
print(f"  {len(rolling_df)} rows ({len(windows)} windows x {NUM_HUBS} hubs)")

# ── Save latest hubs for simulation ───────────────────────────
latest = rolling_df[rolling_df['day'] == rolling_df['day'].max()]
latest[["hub_id","node_id","x","y","lat","lon","local_demand"]]\
    .to_csv(LATEST_OUT, index=False)
print(f"Saved latest hubs    → {LATEST_OUT}")

# ── Summary: how much did hubs move? ──────────────────────────
print(f"\nHub movement summary:")
for hub_id in range(NUM_HUBS):
    hub_history = rolling_df[rolling_df['hub_id'] == hub_id]
    unique_locs = hub_history[['x','y']].drop_duplicates()
    x_range = hub_history['x'].max() - hub_history['x'].min()
    y_range = hub_history['y'].max() - hub_history['y'].min()
    print(f"  Hub {hub_id}: {len(unique_locs)} unique locations, "
          f"moved {x_range:.0f}m (x) x {y_range:.0f}m (y)")
