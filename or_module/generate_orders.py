"""
generate_orders.py
Generates 3 months of simulated delivery orders across the
Toa Payoh / Novena / Bishan road network.

Demand is not uniform — it follows realistic patterns:
  - Higher demand near MRT stations and town centres
  - Morning and evening peaks
  - Weekdays busier than weekends

Output: data/orders/orders.csv
  order_id, day, hour, node_id, lat, lon, x, y, demand_weight
"""

import pandas as pd
import numpy as np
import random
import os

NODES_FILE  = "data/osm/graph_nodes.csv"
ORDERS_OUT  = "data/orders/orders.csv"
RANDOM_SEED = 42

np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

print("Loading road nodes...")
nodes = pd.read_csv(NODES_FILE)
print(f"  {len(nodes):,} nodes loaded")

# ── Demand hotspots (approximate XY coords of busy areas) ──────
# These represent MRT stations / town centres in the subgraph area
hotspots = [
    (538.0,  745.0, 3.0),   # Toa Payoh MRT area
    (92.0,   74.0,  2.5),   # Novena area
    (820.0,  286.0, 2.0),   # Bishan area
    (300.0,  500.0, 1.5),   # Mid-residential
    (700.0,  900.0, 1.5),   # North residential
    (400.0,  100.0, 1.0),   # South edge
    (900.0,  700.0, 1.0),   # East residential
    (150.0,  800.0, 1.0),   # West residential
]

def demand_weight(x, y):
    """Higher weight = more orders generated near this node."""
    w = 0.2  # baseline
    for hx, hy, strength in hotspots:
        dist = np.sqrt((x - hx)**2 + (y - hy)**2)
        w += strength * np.exp(-dist / 300.0)
    return w

print("Computing demand weights for each node...")
nodes["weight"] = nodes.apply(
    lambda r: demand_weight(r.x, r.y), axis=1)
nodes["weight"] /= nodes["weight"].sum()  # normalise to probability

# ── Generate orders ────────────────────────────────────────────
DAYS        = 90    # 3 months
BASE_ORDERS = 200   # base orders per day

print(f"Generating orders for {DAYS} days...")
orders = []
order_id = 0

for day in range(DAYS):
    is_weekend = (day % 7) >= 5

    # Weekends have 70% of weekday demand
    daily_total = int(BASE_ORDERS * (0.7 if is_weekend else 1.0))

    # Hour distribution: peaks at 9-11am and 6-8pm
    hour_weights = np.array([
        0.5, 0.3, 0.2, 0.2, 0.3, 0.5,   # 0-5
        1.0, 2.0, 3.0, 4.0, 4.0, 3.5,   # 6-11
        3.0, 2.5, 2.0, 2.0, 2.5, 4.0,   # 12-17
        4.5, 4.0, 3.0, 2.0, 1.0, 0.5,   # 18-23
    ])
    hour_weights /= hour_weights.sum()

    # Sample hours for each order
    hours = np.random.choice(24, size=daily_total, p=hour_weights)

    # Sample destination nodes based on demand weight
    dest_nodes = nodes.sample(
        n=daily_total,
        weights="weight",
        replace=True,
        random_state=day
    )

    for i, (hour, (_, node_row)) in enumerate(
            zip(hours, dest_nodes.iterrows())):
        orders.append({
            "order_id":      order_id,
            "day":           day,
            "hour":          int(hour),
            "node_id":       int(node_row.node_id),
            "lat":           round(node_row.lat, 7),
            "lon":           round(node_row.lon, 7),
            "x":             round(node_row.x, 2),
            "y":             round(node_row.y, 2),
            "demand_weight": round(node_row.weight * 1000, 4),
        })
        order_id += 1

os.makedirs("data/orders", exist_ok=True)
df = pd.DataFrame(orders)
df.to_csv(ORDERS_OUT, index=False)

print(f"\nDone.")
print(f"  Total orders     : {len(df):,}")
print(f"  Days covered     : {DAYS}")
print(f"  Avg orders/day   : {len(df)/DAYS:.0f}")
print(f"  Unique nodes used: {df['node_id'].nunique():,}")
print(f"\n  Hourly distribution:")
print(df.groupby('hour').size().to_string())
print(f"\nSaved → {ORDERS_OUT}")
