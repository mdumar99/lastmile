"""
visualize_overlay.py
Overlays robot event positions on top of the real road network.
Shows WHERE deliveries happen on actual Singapore streets.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.collections as mc
import numpy as np

NODES_FILE = "data/osm/graph_nodes.csv"
EDGES_FILE = "data/osm/graph_edges.csv"
LOG_FILE   = "data/logs/sim_log.csv"

print("Loading graph...")
nodes = pd.read_csv(NODES_FILE).set_index("node_id")
edges = pd.read_csv(EDGES_FILE)
df    = pd.read_csv(LOG_FILE)

# Build road edge lines
lines = []
for row in edges.itertuples(index=False):
    if row.from_id in nodes.index and row.to_id in nodes.index:
        x1, y1 = nodes.loc[row.from_id, ["x", "y"]]
        x2, y2 = nodes.loc[row.to_id,   ["x", "y"]]
        lines.append([(x1, y1), (x2, y2)])

fig, axes = plt.subplots(1, 2, figsize=(18, 9))
fig.patch.set_facecolor("#0f1117")

titles = ["Delivery Heatmap on Real Roads",
          "Recharge Events on Real Roads"]
filters = ["delivered", "arrived_hub"]
cmaps   = ["YlOrRd", "Blues"]

for ax, title, note_filter, cmap in zip(axes, titles, filters, cmaps):
    ax.set_facecolor("#0f1117")

    # Draw road network underneath
    lc = mc.LineCollection(lines, colors="#2a4a7a",
                           linewidths=0.3, alpha=0.5)
    ax.add_collection(lc)

    # Filter events
    subset = df[df['note'] == note_filter]

    if len(subset) > 0:
        # Hexbin heatmap over roads
        hb = ax.hexbin(subset['x'], subset['y'],
                       gridsize=35, cmap=cmap,
                       mincnt=1, alpha=0.75)
        plt.colorbar(hb, ax=ax, label='Event count',
                     shrink=0.8).ax.yaxis.label.set_color('white')

    # Hub markers
    hub_coords = [(92.57, 74.63), (538.61, 745.44), (820.34, 286.75)]
    for i, (hx, hy) in enumerate(hub_coords):
        ax.plot(hx, hy, '^', color='#f6c90e',
                markersize=14, zorder=5, label=f'Hub {i}')

    ax.autoscale()
    ax.set_aspect('equal')
    ax.set_title(title, color='white', fontsize=12, pad=10)
    ax.tick_params(colors='white')
    ax.set_xlabel("X (metres)", color='white')
    ax.set_ylabel("Y (metres)", color='white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#333333')
    ax.legend(facecolor='#1a1a2e', labelcolor='white',
              fontsize=8, loc='upper right')
    ax.annotate(f"{len(subset):,} events",
                xy=(0.02, 0.96), xycoords='axes fraction',
                color='white', fontsize=9,
                bbox=dict(boxstyle='round', facecolor='#1a1a2e', alpha=0.7))

plt.suptitle("Last-Mile Simulation — Robot Activity on Singapore Roads\n"
             "Toa Payoh / Novena / Bishan Area",
             color='white', fontsize=13, y=1.01)
plt.tight_layout()
plt.savefig("data/logs/overlay.png", dpi=150,
            facecolor="#0f1117", bbox_inches="tight")
print("Saved → data/logs/overlay.png")
