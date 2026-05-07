"""
visualize_comparison.py
Before vs After dashboard — hardcoded hubs vs MILP optimised hubs.
This is the "Management Dashboard" output for the project.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.collections as mc
import matplotlib.patches as mpatches
import numpy as np

BASELINE_LOG  = "data/logs/sim_baseline.csv"
OPTIMISED_LOG = "data/logs/sim_optimised.csv"
NODES_FILE    = "data/osm/graph_nodes.csv"
EDGES_FILE    = "data/osm/graph_edges.csv"

print("Loading logs...")
base = pd.read_csv(BASELINE_LOG)
opt  = pd.read_csv(OPTIMISED_LOG)
nodes = pd.read_csv(NODES_FILE).set_index("node_id")
edges = pd.read_csv(EDGES_FILE)

# Road network lines
lines = []
for row in edges.itertuples(index=False):
    if row.from_id in nodes.index and row.to_id in nodes.index:
        x1,y1 = nodes.loc[row.from_id,["x","y"]]
        x2,y2 = nodes.loc[row.to_id,  ["x","y"]]
        lines.append([(x1,y1),(x2,y2)])

# ── Stats ─────────────────────────────────────
def sim_stats(df):
    delivered  = df[df['note']=='delivered']
    energy_total = df.groupby('robot_id')['battery'].apply(
        lambda b: max(0, 100 - b.min())
    ).sum() * 0.01  # crude kWh proxy
    recharges  = (df['note']=='arrived_hub').sum()
    # throughput per hour
    df2 = delivered.copy()
    df2['hour'] = (df2['time'] // 3600).astype(int)
    throughput = df2.groupby('hour').size()
    return {
        'total_deliveries': len(delivered),
        'recharges':        recharges,
        'throughput':       throughput,
        'delivered_df':     delivered,
    }

bs = sim_stats(base)
os = sim_stats(opt)

base_hubs = [(92.57,74.63),(538.61,745.44),(820.34,286.75)]
opt_hubs  = [(65.29,819.57),(996.27,841.45),(927.77,407.83)]

# ── Figure ────────────────────────────────────
fig = plt.figure(figsize=(20, 14))
fig.patch.set_facecolor("#0f1117")
fig.suptitle("Last-Mile Delivery — Management Dashboard\n"
             "Hardcoded Hubs  vs  MILP Optimised Hubs",
             color="white", fontsize=15, fontweight="bold", y=0.98)

gs = fig.add_gridspec(3, 4, hspace=0.45, wspace=0.35)

BG   = "#0f1117"
CARD = "#1a1a2e"
BLUE = "#3a7bd5"
GRN  = "#2ecc71"
RED  = "#e74c3c"
YLW  = "#f6c90e"
GRY  = "#95a5a6"

def dark_ax(ax):
    ax.set_facecolor(CARD)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for s in ax.spines.values():
        s.set_edgecolor("#333355")

# ── Row 0: KPI cards ──────────────────────────
kpis = [
    ("Total Deliveries",
     f"{bs['total_deliveries']:,}",
     f"{os['total_deliveries']:,}",
     f"+{os['total_deliveries']-bs['total_deliveries']:,}",
     GRN),
    ("Improvement",
     "Baseline",
     "MILP",
     f"+{(os['total_deliveries']-bs['total_deliveries'])/bs['total_deliveries']*100:.1f}%",
     GRN),
    ("Recharge Events",
     f"{bs['recharges']:,}",
     f"{os['recharges']:,}",
     f"{os['recharges']-bs['recharges']:+,}",
     GRY),
    ("MILP Cost Saving",
     "8,235,794",
     "6,095,001",
     "−26.0%",
     GRN),
]

for col, (title, bval, oval, delta, col_) in enumerate(kpis):
    ax = fig.add_subplot(gs[0, col])
    ax.set_facecolor(CARD)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_edgecolor("#333355")
    ax.text(0.5, 0.88, title,  ha="center", va="top",
            transform=ax.transAxes, color=GRY,  fontsize=9)
    ax.text(0.5, 0.62, bval,   ha="center", va="top",
            transform=ax.transAxes, color=RED,  fontsize=13, fontweight="bold")
    ax.text(0.5, 0.38, oval,   ha="center", va="top",
            transform=ax.transAxes, color=GRN,  fontsize=13, fontweight="bold")
    ax.text(0.5, 0.10, delta,  ha="center", va="top",
            transform=ax.transAxes, color=col_, fontsize=11, fontweight="bold")
    ax.text(0.18, 0.62, "●", ha="center", va="top",
            transform=ax.transAxes, color=RED, fontsize=10)
    ax.text(0.18, 0.38, "●", ha="center", va="top",
            transform=ax.transAxes, color=GRN, fontsize=10)

# ── Row 1: Throughput comparison ──────────────
ax_t = fig.add_subplot(gs[1, :2])
dark_ax(ax_t)
hours = list(range(8))
bv = [bs['throughput'].get(h,0) for h in hours]
ov = [os['throughput'].get(h,0) for h in hours]
x  = np.arange(len(hours))
w  = 0.35
ax_t.bar(x - w/2, bv, w, color=RED,  alpha=0.8, label="Hardcoded hubs")
ax_t.bar(x + w/2, ov, w, color=GRN,  alpha=0.8, label="MILP hubs")
ax_t.set_title("Throughput — Deliveries per Simulated Hour")
ax_t.set_xlabel("Hour of simulation")
ax_t.set_ylabel("Deliveries")
ax_t.set_xticks(x)
ax_t.set_xticklabels([f"H{h}" for h in hours])
ax_t.legend(facecolor=CARD, labelcolor="white", fontsize=8)

# ── Row 1: Battery distribution ───────────────
ax_b = fig.add_subplot(gs[1, 2:])
dark_ax(ax_b)
base_dep = base[base['note']=='depart->deliver']['battery']
opt_dep  = opt [opt ['note']=='depart->deliver']['battery']
ax_b.hist(base_dep, bins=20, alpha=0.6, color=RED, label="Hardcoded hubs")
ax_b.hist(opt_dep,  bins=20, alpha=0.6, color=GRN, label="MILP hubs")
ax_b.set_title("Battery Level at Departure")
ax_b.set_xlabel("Battery %")
ax_b.set_ylabel("Count")
ax_b.legend(facecolor=CARD, labelcolor="white", fontsize=8)

# ── Row 2: Heatmaps on real roads ─────────────
for col, (df, hubs, label, clr) in enumerate([
    (base, base_hubs, "Hardcoded Hubs", RED),
    (opt,  opt_hubs,  "MILP Optimised Hubs", GRN),
]):
    ax = fig.add_subplot(gs[2, col*2:(col+1)*2])
    ax.set_facecolor(BG)
    lc = mc.LineCollection(lines, colors="#1a3a6a", linewidths=0.3, alpha=0.5)
    ax.add_collection(lc)

    delivered = df[df['note']=='delivered']
    if len(delivered) > 0:
        hb = ax.hexbin(delivered['x'], delivered['y'],
                       gridsize=30, cmap='YlOrRd',
                       mincnt=1, alpha=0.75)
        plt.colorbar(hb, ax=ax, label='Deliveries',
                     shrink=0.8).ax.yaxis.label.set_color('white')

    for i,(hx,hy) in enumerate(hubs):
        ax.plot(hx, hy, "^", color=YLW, markersize=14,
                zorder=5, label=f"Hub {i}")

    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title(f"Delivery Heatmap — {label}", color="white", fontsize=11)
    ax.tick_params(colors="white")
    ax.set_xlabel("X (metres)", color="white")
    ax.set_ylabel("Y (metres)", color="white")
    for s in ax.spines.values(): s.set_edgecolor("#333355")
    ax.legend(facecolor=CARD, labelcolor="white", fontsize=7)
    ax.annotate(f"{len(delivered):,} deliveries",
                xy=(0.02,0.96), xycoords="axes fraction",
                color="white", fontsize=9,
                bbox=dict(boxstyle="round", facecolor=CARD, alpha=0.8))

plt.savefig("data/logs/comparison_dashboard.png",
            dpi=150, facecolor=BG, bbox_inches="tight")
print("Saved → data/logs/comparison_dashboard.png")
