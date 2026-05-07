import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import sys

log = sys.argv[1] if len(sys.argv) > 1 else "data/logs/sim_log.csv"
df  = pd.read_csv(log)

print(f"Loaded {len(df)} events")
print(df['event'].value_counts().to_string())
print(f"\nUnique robots : {df['robot_id'].nunique()}")
print(f"Time span     : {df['time'].min():.1f}s → {df['time'].max():.1f}s")

# ── Layout ───────────────────────────────────
fig = plt.figure(figsize=(14, 10))
fig.suptitle("Last-Mile Simulation — Phase 1 Dashboard", fontsize=14, fontweight='bold')
gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

# ── 1. Deliveries over time ───────────────────
ax1 = fig.add_subplot(gs[0, 0])
delivered = df[df['note'] == 'delivered'].copy()
delivered['bin'] = pd.cut(delivered['time'],
                           bins=20, labels=False)
throughput = delivered.groupby('bin').size()
ax1.bar(throughput.index, throughput.values, color='steelblue', width=0.8)
ax1.set_title("Deliveries per Time Bucket")
ax1.set_xlabel("Time bucket (0 = start, 19 = end of hour)")
ax1.set_ylabel("Deliveries")

# ── 2. Battery distribution at depart ────────
ax2 = fig.add_subplot(gs[0, 1])
departs = df[df['event'] == 'DEPART']
ax2.hist(departs['battery'], bins=20, color='seagreen', edgecolor='white')
ax2.set_title("Battery Level at Departure")
ax2.set_xlabel("Battery %")
ax2.set_ylabel("Count")

# ── 3. Robot position heatmap ─────────────────
ax3 = fig.add_subplot(gs[1, 0])
h = ax3.hist2d(df['x'], df['y'], bins=30,
               cmap='YlOrRd')
plt.colorbar(h[3], ax=ax3, label='Event density')
ax3.plot([200], [200], 'b^', markersize=10, label='Hub 0')
ax3.plot([500], [800], 'b^', markersize=10, label='Hub 1')
ax3.plot([800], [300], 'b^', markersize=10, label='Hub 2')
ax3.legend(fontsize=7)
ax3.set_title("Congestion Heatmap")
ax3.set_xlabel("X (metres)")
ax3.set_ylabel("Y (metres)")

# ── 4. Event type breakdown ───────────────────
ax4 = fig.add_subplot(gs[1, 1])
counts = df['event'].value_counts()
colors = ['steelblue', 'seagreen', 'tomato']
ax4.pie(counts.values, labels=counts.index,
        autopct='%1.1f%%', colors=colors,
        startangle=90)
ax4.set_title("Event Type Distribution")

plt.savefig("data/logs/dashboard.png", dpi=150, bbox_inches='tight')
print("\nDashboard saved → data/logs/dashboard.png")
plt.show()
