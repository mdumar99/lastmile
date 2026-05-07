import pandas as pd

nodes = pd.read_csv("data/osm/graph_nodes.csv")

print("Lat/Lon coverage:")
print(f"  Lat: {nodes['lat'].min():.4f} → {nodes['lat'].max():.4f}")
print(f"  Lon: {nodes['lon'].min():.4f} → {nodes['lon'].max():.4f}")

centre_lat = nodes['lat'].mean()
centre_lon = nodes['lon'].mean()
print(f"\n  Centre: {centre_lat:.4f}, {centre_lon:.4f}")
print(f"\n  Google Maps link:")
print(f"  https://www.google.com/maps/@{centre_lat:.4f},{centre_lon:.4f},14z")
