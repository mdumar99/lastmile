"""
parse_osm.py
Reads the regional .pbf file, extracts Singapore's road network,
and exports two files:
  data/osm/nodes.csv  — node_id, lat, lon
  data/osm/edges.csv  — from_id, to_id, distance_m, highway_type
"""

import osmium
import math
import csv
import sys
from collections import defaultdict

PBF_FILE  = "data/osm/region.osm.pbf"
NODES_OUT = "data/osm/nodes.csv"
EDGES_OUT = "data/osm/edges.csv"

# Singapore bounding box
SG_LAT_MIN, SG_LAT_MAX = 1.1496, 1.4784
SG_LON_MIN, SG_LON_MAX = 103.5940, 104.0945

# Road types we care about (excludes motorways robots can't use)
VALID_HIGHWAYS = {
    "residential", "living_street", "service",
    "tertiary", "tertiary_link",
    "secondary", "secondary_link",
    "primary", "primary_link",
    "footway", "path", "pedestrian", "cycleway"
}

def haversine(lat1, lon1, lat2, lon2):
    """Distance in metres between two lat/lon points."""
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) *
         math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))

def in_singapore(lat, lon):
    return (SG_LAT_MIN <= lat <= SG_LAT_MAX and
            SG_LON_MIN <= lon <= SG_LON_MAX)

# ── Pass 1: collect all way nodes inside Singapore ──────────────
print("Pass 1: scanning ways...")

class WayScanner(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.needed_nodes = set()   # node ids referenced by valid ways
        self.ways = []              # (way_id, [node_ids], highway_type)

    def way(self, w):
        hw = w.tags.get("highway", "")
        if hw not in VALID_HIGHWAYS:
            return
        node_ids = [n.ref for n in w.nodes]
        self.ways.append((w.id, node_ids, hw))
        self.needed_nodes.update(node_ids)

ws = WayScanner()
ws.apply_file(PBF_FILE)
print(f"  Found {len(ws.ways):,} valid ways, "
      f"{len(ws.needed_nodes):,} referenced nodes")

# ── Pass 2: collect lat/lon for needed nodes ─────────────────────
print("Pass 2: collecting node coordinates...")

class NodeCollector(osmium.SimpleHandler):
    def __init__(self, needed):
        super().__init__()
        self.needed = needed
        self.coords = {}   # node_id -> (lat, lon)

    def node(self, n):
        if n.id in self.needed:
            lat, lon = n.location.lat, n.location.lon
            if in_singapore(lat, lon):
                self.coords[n.id] = (lat, lon)

nc = NodeCollector(ws.needed_nodes)
nc.apply_file(PBF_FILE)
print(f"  Resolved {len(nc.coords):,} nodes inside Singapore")

# ── Build edges ──────────────────────────────────────────────────
print("Building edges...")
edges = []
node_usage = defaultdict(int)

for way_id, node_ids, hw in ws.ways:
    # Filter to nodes we actually resolved
    valid = [nid for nid in node_ids if nid in nc.coords]
    if len(valid) < 2:
        continue
    for i in range(len(valid) - 1):
        a, b = valid[i], valid[i+1]
        lat1, lon1 = nc.coords[a]
        lat2, lon2 = nc.coords[b]
        dist = haversine(lat1, lon1, lat2, lon2)
        edges.append((a, b, round(dist, 2), hw))
        edges.append((b, a, round(dist, 2), hw))  # bidirectional
        node_usage[a] += 1
        node_usage[b] += 1

# Only keep nodes that actually appear in edges
used_nodes = set(node_usage.keys())
print(f"  {len(edges):,} directed edges, {len(used_nodes):,} used nodes")

# ── Write output ─────────────────────────────────────────────────
print("Writing nodes.csv...")
with open(NODES_OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["node_id", "lat", "lon"])
    for nid in used_nodes:
        lat, lon = nc.coords[nid]
        w.writerow([nid, round(lat, 7), round(lon, 7)])

print("Writing edges.csv...")
with open(EDGES_OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["from_id", "to_id", "distance_m", "highway"])
    for e in edges:
        w.writerow(e)

print(f"\nDone.")
print(f"  nodes.csv : {len(used_nodes):,} rows")
print(f"  edges.csv : {len(edges):,} rows")
