"""
visualize_graph.py
Quick sanity check — plots the road network subgraph
so we can confirm it looks like real Singapore streets.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.collections as mc

NODES_FILE = "data/osm/graph_nodes.csv"
EDGES_FILE = "data/osm/graph_edges.csv"

print("Loading graph...")
nodes = pd.read_csv(NODES_FILE).set_index("node_id")
edges = pd.read_csv(EDGES_FILE)

print(f"  {len(nodes):,} nodes, {len(edges):,} edges")

# Build line segments for edges
print("Building edge lines...")
lines = []
for row in edges.itertuples(index=False):
    if row.from_id in nodes.index and row.to_id in nodes.index:
        x1, y1 = nodes.loc[row.from_id, ["x", "y"]]
        x2, y2 = nodes.loc[row.to_id,   ["x", "y"]]
        lines.append([(x1, y1), (x2, y2)])

print(f"  {len(lines):,} lines to draw")

fig, ax = plt.subplots(figsize=(12, 12))
fig.patch.set_facecolor("#0f1117")
ax.set_facecolor("#0f1117")

# Draw edges
lc = mc.LineCollection(lines, colors="#3a7bd5", linewidths=0.4, alpha=0.6)
ax.add_collection(lc)

# Draw nodes
ax.scatter(nodes["x"], nodes["y"],
           s=0.8, c="#ffffff", alpha=0.4, linewidths=0)

# Hub positions (same as Simulation.cpp hardcoded hubs)
hubs = [(200, 200), (500, 800), (800, 300)]
for i, (hx, hy) in enumerate(hubs):
    ax.plot(hx, hy, "^", color="#f6c90e",
            markersize=12, label=f"Hub {i}")

ax.autoscale()
ax.set_aspect("equal")
ax.set_title("Singapore Road Network — Simulation Subgraph",
             color="white", fontsize=13, pad=12)
ax.tick_params(colors="white")
for spine in ax.spines.values():
    spine.set_edgecolor("#333333")
ax.set_xlabel("X (metres from centre)", color="white")
ax.set_ylabel("Y (metres from centre)", color="white")
ax.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=9)

plt.tight_layout()
plt.savefig("data/logs/road_network.png", dpi=150,
            facecolor="#0f1117", bbox_inches="tight")
print("Saved → data/logs/road_network.png")
