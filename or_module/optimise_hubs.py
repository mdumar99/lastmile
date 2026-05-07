"""
optimise_hubs.py — Facility Location MILP via HiGHS
"""
import pandas as pd
import numpy as np
import highspy
import os, time

NODES_FILE     = "data/osm/graph_nodes.csv"
ORDERS_FILE    = "data/orders/orders.csv"
HUBS_OUT       = "data/orders/hubs_optimised.csv"
NUM_HUBS       = 3
NUM_CANDIDATES = 50
RANDOM_SEED    = 42
np.random.seed(RANDOM_SEED)

print("Loading data...")
nodes  = pd.read_csv(NODES_FILE).set_index("node_id")
orders = pd.read_csv(ORDERS_FILE)
print(f"  {len(nodes):,} nodes, {len(orders):,} orders")

print("Aggregating demand...")
demand = orders.groupby("node_id").size().reset_index(name="count")
demand = demand.merge(nodes[["x","y"]].reset_index(), on="node_id")
print(f"  {len(demand):,} demand nodes")

print(f"Selecting {NUM_CANDIDATES} candidates...")
candidates = demand.nlargest(200, "count").sample(
    n=min(NUM_CANDIDATES, 200), random_state=RANDOM_SEED
).reset_index(drop=True)

print("Computing distance matrix...")
D  = demand[["x","y"]].values
C  = candidates[["x","y"]].values
dm = np.sqrt(((D[:,None,:] - C[None,:,:])**2).sum(axis=2))
w  = demand["count"].values.astype(float)
M, N = len(demand), len(candidates)
print(f"  {M} x {N}  max={dm.max():.0f}m  mean={dm.mean():.0f}m")

# ── HiGHS model ───────────────────────────────────────────────
print("\nBuilding MILP...")
h = highspy.Highs()
h.silent()

# Variables: y[0..N-1] binary, x[N..N+M*N-1] continuous
num_vars = N + M * N
lb = np.zeros(num_vars)
ub = np.ones(num_vars)
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

print(f"  Variables: {num_vars:,}")

# Constraint 1: sum_j y[j] = NUM_HUBS
idx  = np.arange(N, dtype=np.int32)
vals = np.ones(N, dtype=np.float64)
h.addRow(float(NUM_HUBS), float(NUM_HUBS), N, idx, vals)

# Constraint 2: sum_j x[i,j] = 1  for each i
for i in range(M):
    idx  = np.array([N + i*N + j for j in range(N)], dtype=np.int32)
    vals = np.ones(N, dtype=np.float64)
    h.addRow(1.0, 1.0, N, idx, vals)

# Constraint 3: x[i,j] - y[j] <= 0  for each i,j
for i in range(M):
    for j in range(N):
        idx  = np.array([N + i*N + j, j], dtype=np.int32)
        vals = np.array([1.0, -1.0],      dtype=np.float64)
        h.addRow(-highspy.kHighsInf, 0.0, 2, idx, vals)

print(f"  Constraints: {1 + M + M*N:,}")

# ── Solve ─────────────────────────────────────────────────────
print("\nSolving (30-120s)...")
t0 = time.time()
h.run()
print(f"  Status    : {h.getModelStatus()}")
print(f"  Solve time: {time.time()-t0:.1f}s")
print(f"  Objective : {h.getInfoValue('objective_function_value')[1]:,.0f}")

# ── Extract hubs ──────────────────────────────────────────────
sol      = h.getSolution()
selected = [j for j in range(N) if sol.col_value[j] > 0.5]

print(f"\nSelected {len(selected)} hubs:")
results = []
for rank, j in enumerate(selected):
    row = candidates.iloc[j]
    nid = int(row.node_id)
    print(f"  Hub {rank}: node={nid} x={row.x:.1f} y={row.y:.1f} "
          f"demand={row['count']}")
    results.append({
        "hub_id": rank, "node_id": nid,
        "x": round(row.x,2), "y": round(row.y,2),
        "lat": round(nodes.loc[nid,"lat"],7),
        "lon": round(nodes.loc[nid,"lon"],7),
        "local_demand": int(row["count"]),
    })

# ── Before vs After ───────────────────────────────────────────
def wcost(hubs, pts, weights):
    hc = np.array(hubs)
    return sum(weights[i] * np.sqrt(((hc - pts[i])**2).sum(axis=1)).min()
               for i in range(len(pts)))

hardcoded  = [[92.57,74.63],[538.61,745.44],[820.34,286.75]]
opt_coords = [[r["x"],r["y"]] for r in results]
base = wcost(hardcoded,  D, w)
opt  = wcost(opt_coords, D, w)
pct  = (base - opt) / base * 100

print(f"\n{'='*50}")
print(f"  Baseline (hardcoded hubs) : {base:>14,.0f}")
print(f"  Optimised (MILP hubs)     : {opt:>14,.0f}")
print(f"  Improvement               : {pct:>13.1f}%")
print(f"{'='*50}")

os.makedirs("data/orders", exist_ok=True)
pd.DataFrame(results).to_csv(HUBS_OUT, index=False)
print(f"\nSaved → {HUBS_OUT}")
