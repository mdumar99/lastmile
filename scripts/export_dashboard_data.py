"""
export_dashboard_data.py
Exports simulation data as JSON for the Deck.gl dashboard.
"""

import sys
sys.path.insert(0, ".")
import lastmile
import pandas as pd
import numpy as np
import json
import os
import math

os.makedirs("dashboard/public/data", exist_ok=True)

CENTRE_LAT = 1.3521
CENTRE_LON = 103.8198

def xy_to_latlon(x, y):
    lat = CENTRE_LAT + y / 111_320
    lon = CENTRE_LON + x / (111_320 * math.cos(math.radians(CENTRE_LAT)))
    return round(lat, 7), round(lon, 7)

def safe(v, fallback=0):
    """Replace NaN/inf with a safe fallback."""
    try:
        if math.isnan(v) or math.isinf(v):
            return fallback
    except (TypeError, ValueError):
        pass
    return v

# ── Run simulations ────────────────────────────────────────────
print("Running baseline simulation...")
e1 = lastmile.SimEngine(robots=50, duration=28800)
e1.set_log_path("data/logs/dash_baseline.csv")
e1.run()
s1 = e1.get_stats()

print("Running MILP simulation...")
e2 = lastmile.SimEngine(robots=50, duration=28800)
e2.set_hubs_csv("data/orders/hubs_optimised.csv")
e2.set_log_path("data/logs/dash_optimised.csv")
e2.run()
s2 = e2.get_stats()

# ── Process logs ───────────────────────────────────────────────
print("Processing logs...")

def process_log(df, label):
    delivered = df[df['note'] == 'delivered'].copy()
    delivered['hour'] = (delivered['time'] // 3600).astype(int)
    throughput = delivered.groupby('hour').size().reset_index(name='count')

    # Heatmap points
    heatmap = []
    for _, row in delivered.iterrows():
        lat, lon = xy_to_latlon(row['x'], row['y'])
        heatmap.append({"lat": lat, "lon": lon, "weight": 1})

    # Battery by hour
    departs = df[df['note'] == 'depart->deliver'].copy()
    departs['hour'] = (departs['time'] // 3600).astype(int)
    battery_by_hour = departs.groupby('hour')['battery'].mean().reset_index()
    battery_by_hour['battery'] = battery_by_hour['battery'].fillna(0)

    # Robot last positions — sanitise all float fields
    tracks = []
    for rid in df['robot_id'].unique():
        robot_df = df[df['robot_id'] == rid].tail(1)
        if len(robot_df) > 0:
            row = robot_df.iloc[0]
            lat, lon = xy_to_latlon(
                safe(float(row['x'])),
                safe(float(row['y']))
            )
            tracks.append({
                "id":      int(rid),
                "lat":     lat,
                "lon":     lon,
                "battery": safe(round(float(row['battery']), 1)),
                "status":  str(row['status'])
            })

    return {
        "label":      label,
        "throughput": throughput.to_dict(orient='records'),
        "heatmap":    heatmap[:5000],
        "battery":    [
            {"hour": int(r.hour),
             "battery": safe(round(float(r.battery), 1))}
            for r in battery_by_hour.itertuples()
        ],
        "tracks": tracks,
    }

def hub_latlon(x, y):
    lat, lon = xy_to_latlon(x, y)
    return {"lat": lat, "lon": lon}

base_hubs = [hub_latlon(92.57,74.63), hub_latlon(538.61,745.44), hub_latlon(820.34,286.75)]
milp_hubs = [hub_latlon(65.29,819.57), hub_latlon(996.27,841.45), hub_latlon(927.77,407.83)]

output = {
    "baseline": {
        **process_log(pd.read_csv("data/logs/dash_baseline.csv"), "Hardcoded Hubs"),
        "stats": s1,
        "hubs":  base_hubs,
    },
    "optimised": {
        **process_log(pd.read_csv("data/logs/dash_optimised.csv"), "MILP Optimised"),
        "stats": s2,
        "hubs":  milp_hubs,
    },
    "meta": {
        "robots":   50,
        "duration": 28800,
        "area":     "Toa Payoh / Novena / Bishan, Singapore",
        "centre":   {"lat": CENTRE_LAT, "lon": CENTRE_LON},
    }
}

out_path = "dashboard/public/data/simulation.json"
with open(out_path, "w") as f:
    json.dump(output, f, allow_nan=False)

size_kb = os.path.getsize(out_path) / 1024
print(f"\nExported → {out_path} ({size_kb:.0f} KB)")
print(f"  Baseline : {s1['deliveries']:,} deliveries")
print(f"  Optimised: {s2['deliveries']:,} deliveries")
