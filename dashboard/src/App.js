import { useState, useEffect } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

const CENTRE = { latitude: 1.3521, longitude: 103.8198, zoom: 13.5 };

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const COLORS = {
  base:    [231, 76,  60],   // red
  milp:    [46,  204, 113],  // green
  hub:     [246, 201, 14],   // yellow
  robot:   [52,  152, 219],  // blue
};

// ── KPI Card ───────────────────────────────────────────────────
function KpiCard({ title, base, opt, unit = "", invert = false }) {
  const delta    = opt - base;
  const pct      = base > 0 ? ((delta / base) * 100).toFixed(1) : 0;
  const positive = invert ? delta < 0 : delta > 0;
  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>{title}</div>
      <div style={{ display: "flex", justifyContent: "space-around", marginTop: 8 }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#e74c3c", fontSize: 22, fontWeight: "bold" }}>
            {typeof base === "number" ? base.toLocaleString() : base}{unit}
          </div>
          <div style={styles.cardLabel}>Hardcoded</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#2ecc71", fontSize: 22, fontWeight: "bold" }}>
            {typeof opt === "number" ? opt.toLocaleString() : opt}{unit}
          </div>
          <div style={styles.cardLabel}>MILP</div>
        </div>
      </div>
      <div style={{ textAlign: "center", marginTop: 8,
                    color: positive ? "#2ecc71" : "#e74c3c",
                    fontWeight: "bold", fontSize: 14 }}>
        {delta > 0 ? "+" : ""}{typeof delta === "number" ? delta.toLocaleString() : delta}
        {unit} ({pct}%)
      </div>
    </div>
  );
}

// ── Mini bar chart ─────────────────────────────────────────────
function BarChart({ data, color, title }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div style={styles.chartBox}>
      <div style={styles.chartTitle}>{title}</div>
      <div style={{ display: "flex", alignItems: "flex-end",
                    height: 80, gap: 3, padding: "0 8px" }}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, display: "flex",
                                flexDirection: "column", alignItems: "center" }}>
            <div style={{
              width: "100%",
              height: `${(d.count / max) * 72}px`,
              background: color, borderRadius: 2, opacity: 0.85,
            }} />
            {i % 2 === 0 &&
              <div style={{ color: "#888", fontSize: 8, marginTop: 2 }}>
                H{d.hour}
              </div>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────
export default function App() {
  const [data,    setData]    = useState(null);
  const [mode,    setMode]    = useState("baseline");  // baseline | optimised
  const [layer,   setLayer]   = useState("heatmap");   // heatmap | robots
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/data/simulation.json")
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => console.error("Failed to load simulation data:", e));
  }, []);

  if (loading) return (
    <div style={styles.loading}>
      <div style={styles.loadingText}>Loading simulation data...</div>
    </div>
  );

  const sim     = data[mode];
  const other   = data[mode === "baseline" ? "optimised" : "baseline"];
  const bs      = data.baseline.stats;
  const os      = data.optimised.stats;
  const isBase  = mode === "baseline";
  const color   = isBase ? COLORS.base : COLORS.milp;

  // ── Deck.gl layers ─────────────────────────────────────────
  const heatmapLayer = new HeatmapLayer({
    id:           "heatmap",
    data:         sim.heatmap,
    getPosition:  d => [d.lon, d.lat],
    getWeight:    d => d.weight,
    radiusPixels: 40,
    intensity:    1.2,
    threshold:    0.05,
    colorRange: isBase
      ? [[254,229,217],[252,187,161],[252,146,114],[251,106,74],[222,45,38],[165,15,21]]
      : [[237,248,233],[199,233,192],[161,217,155],[116,196,118],[49,163,84],[0,109,44]],
  });

  const hubLayer = new ScatterplotLayer({
    id:           "hubs",
    data:         sim.hubs,
    getPosition:  d => [d.lon, d.lat],
    getRadius:    50,
    getFillColor: COLORS.hub,
    getLineColor: [255, 255, 255],
    lineWidthMinPixels: 2,
    stroked:      true,
    pickable:     true,
  });

  const robotLayer = new ScatterplotLayer({
    id:           "robots",
    data:         sim.tracks,
    getPosition:  d => [d.lon, d.lat],
    getRadius:    20,
    getFillColor: d => d.status === "CHARGING"
      ? [246, 201, 14]
      : d.status === "DELIVERING"
      ? COLORS.milp
      : COLORS.robot,
    pickable:     true,
    opacity:      0.9,
  });

  const layers = layer === "heatmap"
    ? [heatmapLayer, hubLayer]
    : [robotLayer,   hubLayer];

  return (
    <div style={styles.root}>
      {/* ── Header ── */}
      <div style={styles.header}>
        <div>
          <div style={styles.headerTitle}>Last-Mile Delivery Simulation</div>
          <div style={styles.headerSub}>
            {data.meta.area} · {data.meta.robots} robots · 8h simulated
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          {["baseline", "optimised"].map(m => (
            <button key={m} onClick={() => setMode(m)}
              style={{ ...styles.btn,
                       background: mode === m
                         ? (m === "baseline" ? "#e74c3c" : "#2ecc71")
                         : "#2a2a3e" }}>
              {m === "baseline" ? "Hardcoded Hubs" : "MILP Optimised"}
            </button>
          ))}
          {["heatmap", "robots"].map(l => (
            <button key={l} onClick={() => setLayer(l)}
              style={{ ...styles.btn,
                       background: layer === l ? "#3a7bd5" : "#2a2a3e" }}>
              {l === "heatmap" ? "Heatmap" : "Robots"}
            </button>
          ))}
        </div>
      </div>

      {/* ── Map ── */}
      <div style={styles.mapWrap}>
        <DeckGL
          initialViewState={CENTRE}
          controller={true}
          layers={layers}
        >
          <Map mapStyle={MAP_STYLE} />
        </DeckGL>

        {/* ── Legend ── */}
        <div style={styles.legend}>
          <div style={styles.legendTitle}>Legend</div>
          <div style={styles.legendRow}>
            <div style={{...styles.dot, background:"#f6c90e"}}/>
            Hub locations
          </div>
          {layer === "robots" && <>
            <div style={styles.legendRow}>
              <div style={{...styles.dot, background:"#2ecc71"}}/> Delivering
            </div>
            <div style={styles.legendRow}>
              <div style={{...styles.dot, background:"#3498db"}}/> Idle
            </div>
            <div style={styles.legendRow}>
              <div style={{...styles.dot, background:"#f6c90e"}}/> Charging
            </div>
          </>}
          {layer === "heatmap" && <div style={styles.legendRow}>
            <div style={{...styles.dot,
                         background: isBase ? "#e74c3c" : "#2ecc71"}}/>
            Delivery density
          </div>}
        </div>
      </div>

      {/* ── Bottom panel ── */}
      <div style={styles.bottom}>
        {/* KPI cards */}
        <KpiCard title="Deliveries"
          base={bs.deliveries} opt={os.deliveries} />
        <KpiCard title="Energy (kWh)"
          base={Math.round(bs.energy_kwh)} opt={Math.round(os.energy_kwh)}
          invert={true} />
        <KpiCard title="Recharges"
          base={bs.recharges} opt={os.recharges} invert={true} />
        <KpiCard title="MILP Cost Saving"
          base={"8,235,794"} opt={"6,095,001"} unit="" />

        {/* Throughput charts */}
        <BarChart
          data={data.baseline.throughput}
          color="#e74c3c"
          title="Throughput — Hardcoded Hubs" />
        <BarChart
          data={data.optimised.throughput}
          color="#2ecc71"
          title="Throughput — MILP Hubs" />
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = {
  root:    { display:"flex", flexDirection:"column", height:"100vh",
             background:"#0f1117", color:"white", fontFamily:"monospace",
             overflow:"hidden" },
  loading: { display:"flex", justifyContent:"center", alignItems:"center",
             height:"100vh", background:"#0f1117" },
  loadingText: { color:"white", fontSize:20 },
  header:  { display:"flex", justifyContent:"space-between", alignItems:"center",
             padding:"10px 20px", background:"#1a1a2e",
             borderBottom:"1px solid #333355", flexShrink:0 },
  headerTitle: { fontSize:16, fontWeight:"bold", color:"white" },
  headerSub:   { fontSize:11, color:"#888", marginTop:2 },
  btn:     { padding:"6px 14px", border:"none", borderRadius:6,
             color:"white", cursor:"pointer", fontSize:12,
             fontFamily:"monospace", transition:"background 0.2s" },
  mapWrap: { flex:1, position:"relative", minHeight:0 },
  legend:  { position:"absolute", top:12, right:12, background:"rgba(26,26,46,0.92)",
             padding:"12px 16px", borderRadius:8,
             border:"1px solid #333355", zIndex:10 },
  legendTitle: { fontWeight:"bold", marginBottom:8, fontSize:12 },
  legendRow:   { display:"flex", alignItems:"center", gap:8,
                 fontSize:11, color:"#ccc", marginBottom:4 },
  dot:     { width:10, height:10, borderRadius:"50%", flexShrink:0 },
  bottom:  { display:"flex", gap:12, padding:"12px 16px",
             background:"#1a1a2e", borderTop:"1px solid #333355",
             overflowX:"auto", flexShrink:0 },
  card:    { background:"#0f1117", borderRadius:8, padding:"10px 16px",
             border:"1px solid #333355", minWidth:160, flexShrink:0 },
  cardTitle: { fontSize:11, color:"#888", textAlign:"center" },
  cardLabel: { fontSize:10, color:"#666", marginTop:2 },
  chartBox:  { background:"#0f1117", borderRadius:8, padding:"10px 8px",
               border:"1px solid #333355", minWidth:200, flexShrink:0 },
  chartTitle: { fontSize:11, color:"#888", textAlign:"center", marginBottom:4 },
};
