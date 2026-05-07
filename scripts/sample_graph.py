"""
sample_graph.py
Extracts a connected subgraph of ~5000 nodes from the full Singapore
road network, centred on the main island.
Outputs:
  data/osm/graph_nodes.csv  — node_id, lat, lon, x, y
  data/osm/graph_edges.csv  — from_id, to_id, distance_m
"""

import pandas as pd
import networkx as nx
import math
from collections import deque

NODES_IN   = "data/osm/nodes.csv"
EDGES_IN   = "data/osm/edges.csv"
NODES_OUT  = "data/osm/graph_nodes.csv"
EDGES_OUT  = "data/osm/graph_edges.csv"

TARGET_NODES = 5000

# Singapore main island centre
CENTRE_LAT = 1.3521
CENTRE_LON = 103.8198

def latlon_to_xy(lat, lon, ref_lat, ref_lon):
    """Convert lat/lon to local XY metres relative to reference point."""
    x = (lon - ref_lon) * math.cos(math.radians(ref_lat)) * 111_320
    y = (lat - ref_lat) * 111_320
    return round(x, 2), round(y, 2)

print("Loading nodes...")
nodes_df = pd.read_csv(NODES_IN)
print(f"  {len(nodes_df):,} nodes loaded")

print("Loading edges...")
edges_df = pd.read_csv(EDGES_IN)
print(f"  {len(edges_df):,} edges loaded")

# Index nodes by id for fast lookup
nodes_idx = nodes_df.set_index("node_id")

# Find the node closest to Singapore centre as BFS seed
print("Finding seed node...")
nodes_df["dist_to_centre"] = (
    (nodes_df["lat"] - CENTRE_LAT).abs() +
    (nodes_df["lon"] - CENTRE_LON).abs()
)
seed_id = int(nodes_df.loc[nodes_df["dist_to_centre"].idxmin(), "node_id"])
print(f"  Seed node: {seed_id} "
      f"({nodes_idx.loc[seed_id, 'lat']:.4f}, "
      f"{nodes_idx.loc[seed_id, 'lon']:.4f})")

# Build adjacency for BFS
print("Building adjacency list...")
adj = {}
for row in edges_df.itertuples(index=False):
    if row.from_id not in adj:
        adj[row.from_id] = []
    adj[row.from_id].append((row.to_id, row.distance_m))

# BFS outward from seed until we have TARGET_NODES
print(f"BFS sampling {TARGET_NODES} connected nodes...")
visited = set()
queue   = deque([seed_id])
visited.add(seed_id)

while queue and len(visited) < TARGET_NODES:
    node = queue.popleft()
    for neighbour, _ in adj.get(node, []):
        if neighbour not in visited and neighbour in nodes_idx.index:
            visited.add(neighbour)
            queue.append(neighbour)
            if len(visited) >= TARGET_NODES:
                break

print(f"  Sampled {len(visited):,} connected nodes")

# Filter edges to only those within sampled nodes
print("Filtering edges...")
mask = (edges_df["from_id"].isin(visited) &
        edges_df["to_id"].isin(visited))
sub_edges = edges_df[mask].copy()
print(f"  {len(sub_edges):,} edges retained")

# Convert lat/lon to local XY metres
print("Converting to local XY coordinates...")
sub_nodes = nodes_df[nodes_df["node_id"].isin(visited)].copy()
sub_nodes[["x", "y"]] = sub_nodes.apply(
    lambda r: pd.Series(latlon_to_xy(r.lat, r.lon, CENTRE_LAT, CENTRE_LON)),
    axis=1
)

# Write output
print("Writing graph_nodes.csv...")
sub_nodes[["node_id", "lat", "lon", "x", "y"]].to_csv(NODES_OUT, index=False)

print("Writing graph_edges.csv...")
sub_edges[["from_id", "to_id", "distance_m"]].to_csv(EDGES_OUT, index=False)

# Quick sanity check using networkx
print("Verifying connectivity...")
G = nx.DiGraph()
for row in sub_edges.itertuples(index=False):
    G.add_edge(row.from_id, row.to_id, weight=row.distance_m)
print(f"  Nodes in graph : {G.number_of_nodes():,}")
print(f"  Edges in graph : {G.number_of_edges():,}")
print(f"  Is weakly connected: {nx.is_weakly_connected(G)}")

x_vals = sub_nodes["x"]
y_vals = sub_nodes["y"]
print(f"\n  X range: {x_vals.min():.0f}m to {x_vals.max():.0f}m")
print(f"  Y range: {y_vals.min():.0f}m to {y_vals.max():.0f}m")
print(f"\nDone.")
print(f"  graph_nodes.csv : {len(sub_nodes):,} rows")
print(f"  graph_edges.csv : {len(sub_edges):,} rows")
