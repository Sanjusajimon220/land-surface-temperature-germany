"""Satellite-journalism story pages built from the real heat data.

`build_heat_story` turns the same heat_override + heat_timelapse you already
produce into a standalone, published-ready scrollytelling page: a sticky
thermal map of Germany that morphs as the reader scrolls (absolute temperature
-> heat-island anomaly -> 10-year time-lapse -> their own city), with
plain-language narration. The map is the brand: real Landsat land-surface
temperature, glowing against black.
"""
import json
from pathlib import Path

__all__ = ["build_heat_story"]


def _sample_grid(grid, lat, lon):
    """Read the real °C at a lat/lon from a grid_from_array payload."""
    if not grid:
        return None
    s, w, n, e = grid["bbox"]
    nx, ny, z = grid["nx"], grid["ny"], grid["z"]
    if not (s <= lat <= n and w <= lon <= e):
        return None
    col = int((lon - w) / (e - w) * (nx - 1))
    row = int((n - lat) / (n - s) * (ny - 1))      # north-up
    i = row * nx + col
    if 0 <= i < len(z):
        return z[i]
    return None


def build_heat_story(out_path, heat_override, heat_timelapse=None,
                     cities=None, title="Germany is heating up",
                     standfirst=None, byline="Ground_truth", year_now=2025,
                     forecast=None, partial_label=None, city_series=None,
                     current_year=None):
    """Write a scrollytelling urban-heat story to ``out_path``.

    heat_override: dict with png (absolute), png_anomaly, grid, bounds,
        baseline, vmin, vmax (the same dict you pass to build_app).
    heat_timelapse: dict with frames (base64 PNGs) + dates (e.g. '2016'..).
    forecast: optional dict to add the measured-trend + projection chapters:
        {"rate_png":..., "national_per_decade":..., "projections":[
            {"year":2030,"png":...,"mean_temp":...,"increase_vs_baseline":...,
             "uncertainty":...}, ...], "bounds":...}.
        The projection is always rendered visually distinct and labelled as
        extrapolation, never as measurement.
    partial_label: e.g. "2026 is a partial summer (in progress)" — shown on the
        time-lapse so an incomplete latest year is never mistaken for a full one.
    """
    if cities is None:
        from .germany import CITIES
        cities = CITIES
    grid = heat_override.get("grid")
    baseline = heat_override.get("baseline", 27.0)
    # bake each city's real temperature + anomaly from the grid
    city_rows = []
    for name, lon, lat in cities:
        t = _sample_grid(grid, lat, lon)
        if t is None:
            continue
        row = {"name": name, "lat": lat, "lon": lon,
               "t": t, "anom": round(t - baseline, 1)}
        if city_series and name in city_series:        # real 10-yr curve for this city
            yrs, temps = city_series[name]
            row["years"] = list(yrs)
            row["series"] = [round(float(v), 1) if v is not None else None for v in temps]
            row["anomseries"] = [round(float(v) - baseline, 1) if v is not None else None
                                 for v in temps]
        city_rows.append(row)
    city_rows.sort(key=lambda r: r["t"], reverse=True)

    # ---- German states: real boundaries + mean temperature per state ----
    state_rows = []
    try:
        from .germany_states import STATES
        for st in STATES:
            # sample the grid at the state's centroid + a few ring points for a mean
            vals = []
            cy, cx = st["c"]
            v = _sample_grid(grid, cy, cx)
            if v is not None:
                vals.append(v)
            for ring in st["rings"]:
                for lon, lat in ring[::6]:
                    vv = _sample_grid(grid, lat, lon)
                    if vv is not None:
                        vals.append(vv)
            if vals:
                mt = round(sum(vals) / len(vals), 1)
                state_rows.append({"name": st["name"], "rings": st["rings"],
                                   "c": st["c"], "t": mt,
                                   "anom": round(mt - baseline, 1)})
        state_rows.sort(key=lambda r: r["t"], reverse=True)
        for i, s in enumerate(state_rows):
            s["rank"] = i + 1
    except Exception:
        state_rows = []

    if standfirst is None:
        hottest = city_rows[0]["name"] if city_rows else "its cities"
        standfirst = (f"Every summer for a decade, satellites measured the ground "
                      f"temperature of {('Germany')}. The map below is real — not a "
                      f"forecast, not a model. It shows where the country bakes, why "
                      f"{hottest} runs hottest, and how much warmer it has become.")

    data = {
        "png": heat_override.get("png"),
        "png_anomaly": heat_override.get("png_anomaly"),
        "bounds": heat_override.get("bounds"),
        "baseline": baseline,
        "vmin": heat_override.get("vmin", 15),
        "vmax": heat_override.get("vmax", 45),
        "grid": grid,
        "cities": city_rows,
        "states": state_rows,
        "timelapse": heat_timelapse or None,
        "forecast": forecast or None,
        "partial_label": partial_label or None,
        "current_year": current_year or None,
        "title": title, "standfirst": standfirst, "byline": byline,
        "year_now": year_now,
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data))
    Path(out_path).write_text(html)
    return out_path


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Germany is heating up — Ground_truth</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#0c0e0f;--bg2:#131718;--line:#252b2c;--ink:#ededE6;--muted:#878e8a;
 --ochre:#e0a64e;--sage:#7fb4ab;--red:#d8694e;--d:'Space Grotesk',sans-serif;--b:'Inter',sans-serif;--m:'JetBrains Mono',monospace}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font-family:var(--b);line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{position:relative}
/* fixed map background — content scrolls over it, no negative-margin overlap */
#stage{position:fixed;inset:0;height:100vh;width:100%;z-index:0;background:var(--bg)}
#map{height:100%;width:100%;background:var(--bg)}
.leaflet-container{background:#0c0e0f}
.scrim{position:fixed;inset:0;pointer-events:none;z-index:1;
 background:linear-gradient(90deg,rgba(12,14,15,.95) 0%,rgba(12,14,15,.65) 34%,rgba(12,14,15,0) 56%)}
.content{position:relative;z-index:2;pointer-events:none}
.content .card,.content input,.content button,.content a{pointer-events:auto}
/* per-view caption: tells the reader the time frame of what's on the map */
#caption{position:fixed;top:20px;left:24px;z-index:5;max-width:340px;
 font-family:var(--m);font-size:12px;color:var(--ink);background:#0c0e0fcc;border:1px solid var(--line);
 border-radius:9px;padding:9px 13px;backdrop-filter:blur(6px);line-height:1.45}
#caption .cl{color:var(--ochre);letter-spacing:.06em;text-transform:uppercase;font-size:10px;display:block;margin-bottom:3px}
#caption.hide{opacity:0;transform:translateY(-6px)}
#caption{transition:opacity .4s,transform .4s}
/* big year readout during the time-lapse */
#yearbig{position:fixed;top:50%;right:7vw;transform:translateY(-50%);z-index:5;
 font-family:var(--d);font-weight:700;font-size:clamp(54px,9vw,120px);color:#ededE6;
 text-shadow:0 4px 30px #000;opacity:0;transition:opacity .3s;pointer-events:none;text-align:right}
#yearbig.show{opacity:.92}
#yearbig small{display:block;font-family:var(--m);font-size:13px;font-weight:400;letter-spacing:.1em;color:var(--ochre)}
.panel{min-height:100vh;display:flex;align-items:center;padding:0 6vw;pointer-events:none}
.card{max-width:430px;pointer-events:auto}
.eyebrow{font-family:var(--m);font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--ochre);margin-bottom:14px}
.panel h2{font-family:var(--d);font-weight:600;font-size:clamp(26px,3.4vw,40px);line-height:1.12;letter-spacing:-.02em;margin-bottom:14px}
.panel p{font-size:17px;color:#c9cec9;margin-bottom:12px}
.panel p b{color:var(--ink);font-weight:600}
.big{font-family:var(--d);font-weight:700;font-size:clamp(46px,8vw,92px);line-height:.95;letter-spacing:-.03em;color:var(--ink)}
.big .u{color:var(--red)}
/* hero */
#hero{position:relative;z-index:2;height:100vh;display:flex;flex-direction:column;justify-content:flex-end;
 padding:0 6vw 8vh;background:linear-gradient(0deg,rgba(12,14,15,.6),rgba(12,14,15,.15))}
#hero .kicker{font-family:var(--m);font-size:13px;letter-spacing:.2em;text-transform:uppercase;color:var(--ochre);margin-bottom:20px}
#hero h1{font-family:var(--d);font-weight:700;font-size:clamp(40px,7vw,86px);line-height:1.02;letter-spacing:-.03em;max-width:13ch;margin-bottom:22px}
#hero .stand{font-size:clamp(17px,2vw,21px);color:#c9cec9;max-width:54ch}
#hero .by{font-family:var(--m);font-size:12px;color:var(--muted);margin-top:26px}
.scrolltip{position:absolute;left:50%;bottom:26px;transform:translateX(-50%);font-family:var(--m);font-size:11px;color:var(--muted);letter-spacing:.15em;animation:bob 1.8s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translate(-50%,0)}50%{transform:translate(-50%,7px)}}
/* legend chip */
.lg{position:fixed;right:18px;top:18px;z-index:700;background:#0c0e0fdd;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-family:var(--m);font-size:11px;color:var(--muted);backdrop-filter:blur(6px);max-width:230px}
/* click-to-read temperature box */
#clickread{position:fixed;left:24px;bottom:24px;z-index:700;background:#0c0e0fee;border:1px solid var(--ochre);
 border-radius:10px;padding:11px 14px;backdrop-filter:blur(6px);display:flex;flex-direction:column;gap:2px;box-shadow:0 8px 30px #0009}
#clickread.hide{display:none}
#clickread .cr-t{font-family:var(--d);font-weight:700;font-size:22px;color:var(--ink);line-height:1}
#clickread .cr-a{font-family:var(--m);font-size:12px;color:var(--ochre)}
#clickread .cr-x{font-family:var(--m);font-size:10px;color:var(--muted)}
.lg .ttl{color:var(--ink);font-size:11px;margin-bottom:7px;letter-spacing:.04em}
.lg .bar{height:9px;border-radius:5px;margin-bottom:5px}
.lg .tk{display:flex;justify-content:space-between}
/* city ranking */
.rank{list-style:none;margin-top:8px}
.rank li{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--line);font-family:var(--m);font-size:14px}
.rank .n{color:var(--muted);width:20px}
.rank .nm{flex:1;color:var(--ink)}
.rank .tp{color:var(--red);font-weight:500}
.rank .sw{width:34px;height:8px;border-radius:4px}
/* search */
.find{margin-top:14px;display:flex;gap:8px}
.find input{flex:1;background:var(--bg2);border:1px solid var(--line);border-radius:8px;color:var(--ink);font-family:var(--b);font-size:15px;padding:10px 12px}
.find input:focus{outline:none;border-color:var(--ochre)}
.readout{margin-top:12px;font-family:var(--m);font-size:14px;color:var(--ink);min-height:22px}
.readout .hot{color:var(--red)}
/* method / footer flat sections */
.flat{position:relative;z-index:600;background:var(--bg);border-top:1px solid var(--line);padding:9vh 6vw}
.flat .inner{max-width:780px;margin:0 auto}
.flat h3{font-family:var(--d);font-weight:600;font-size:26px;margin-bottom:18px;letter-spacing:-.01em}
.flat p{color:#c9cec9;margin-bottom:14px;max-width:68ch}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-top:8px}
.meta div{background:var(--bg);padding:16px}
.meta .k{font-family:var(--m);font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
.meta .v{font-family:var(--d);font-size:18px;color:var(--ink)}
footer{position:relative;z-index:600;background:var(--bg2);border-top:1px solid var(--line);padding:8vh 6vw;text-align:center}
footer .mark{font-family:var(--d);font-weight:700;font-size:24px;letter-spacing:-.01em}
footer .mark .dot{color:var(--ochre)}
footer p{color:var(--muted);max-width:52ch;margin:14px auto 0;font-size:15px}
.next{display:inline-flex;gap:8px;margin-top:22px;font-family:var(--m);font-size:13px;color:var(--sage);border:1px solid var(--line);border-radius:999px;padding:9px 16px}
@media(max-width:720px){
 .scrim{background:linear-gradient(0deg,rgba(12,14,15,.95) 0%,rgba(12,14,15,.6) 50%,rgba(12,14,15,.2) 100%)}
 .panel{align-items:flex-end;padding-bottom:9vh}.card{max-width:none}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.scrolltip{animation:none}}
/* projection treatment — make extrapolation visually unmistakable */
.warn{font-size:15px;color:var(--ochre);border-left:2px solid var(--ochre);padding-left:12px}
#stage.isproj #map{filter:saturate(.85)}
#stage.isproj::after{content:"";position:absolute;inset:0;z-index:410;pointer-events:none;
 background:repeating-linear-gradient(45deg,rgba(224,166,78,.10) 0 10px,rgba(224,166,78,0) 10px 20px)}
#projbadge{position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:800;
 font-family:var(--m);font-size:12px;letter-spacing:.12em;color:#170f02;background:var(--ochre);
 border-radius:999px;padding:8px 16px;font-weight:600;box-shadow:0 6px 24px #0008}
#projbadge span{display:block;font-weight:400;font-size:10px;letter-spacing:.04em;text-align:center;opacity:.8}
/* city detail popup + anomaly sparkline */
.cpop .leaflet-popup-content-wrapper{background:#0c0e0f;color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:0 10px 40px #000a}
.cpop .leaflet-popup-tip{background:#0c0e0f;border:1px solid var(--line)}
.cpop .leaflet-popup-content{margin:13px 15px}
.citypop h3{font-family:var(--d);font-weight:600;font-size:17px;margin-bottom:8px}
.citypop .bigt{font-family:var(--d);font-weight:700;font-size:30px;line-height:1;color:var(--red)}
.citypop .bigt span{font-family:var(--m);font-size:11px;color:var(--muted);font-weight:400}
.citypop .anomt{font-family:var(--m);font-size:12px;color:var(--sage);margin:5px 0 9px}
.citypop .anomt.up{color:var(--red)}
.citypop .pphot{margin:4px 0}
.spark{display:block}
.sparx{display:flex;justify-content:space-between;font-family:var(--m);font-size:9px;color:var(--muted);margin-top:1px}
.citypop .ppnote{font-family:var(--m);font-size:11px;color:var(--ochre);margin:6px 0}
.citypop .ppcoord{font-family:var(--m);font-size:10px;color:var(--muted);margin-top:6px;border-top:1px solid var(--line);padding-top:6px}
/* permanent city name labels on the map */
.ctip{background:#0c0e0fcc;border:1px solid var(--line);color:var(--ink);font-family:var(--m);
 font-size:11px;padding:2px 6px;border-radius:5px;box-shadow:none;white-space:nowrap}
.ctip::before{display:none}
/* state numbers on map + right-side state name key */
.snum span{display:flex;align-items:center;justify-content:center;width:22px;height:22px;
 background:#0c0e0f;border:1px solid var(--ochre);color:var(--ochre);border-radius:50%;
 font-family:var(--m);font-size:11px;font-weight:600}
#statekey{position:fixed;top:50%;right:18px;transform:translateY(-50%);z-index:5;width:215px;
 background:#0c0e0fdd;border:1px solid var(--line);border-radius:10px;padding:11px 12px;backdrop-filter:blur(6px)}
.sk-ttl{font-family:var(--m);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--ochre);margin-bottom:7px}
.sk-row{display:flex;align-items:center;gap:8px;padding:2px 0;font-family:var(--m);font-size:11px}
.sk-n{color:var(--ochre);width:16px;text-align:right}
.sk-nm{flex:1;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sk-t{color:var(--red)}
.rank.states li{padding:5px 0}
.rankfoot{font-family:var(--m);font-size:11px;color:var(--muted);margin-top:10px}
/* this-summer city deltas */
.cydelta{margin:14px 0 4px;border-top:1px solid var(--line)}
.cyrow{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--line)}
.cyn{font-family:var(--m);font-size:14px;color:var(--ink)}
.cyv{font-family:var(--d);font-weight:600;font-size:15px}
.cyv.hot{color:var(--red)} .cyv.cool{color:var(--sage)}
.cyhdr{display:flex;justify-content:space-between;font-family:var(--m);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;padding:6px 0}
.cyabs{font-family:var(--m);font-size:12px;color:var(--muted);flex:1;text-align:right;padding-right:14px}
.cyn{flex:0 0 auto}
.src{font-family:var(--m);font-size:10px;color:var(--muted);margin-top:14px;letter-spacing:.02em;border-top:1px solid var(--line);padding-top:8px}
/* time-lapse player bar */
#tlbar{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:6;display:flex;align-items:center;gap:12px;
 background:#0c0e0fdd;border:1px solid var(--line);border-radius:12px;padding:9px 16px;backdrop-filter:blur(8px);box-shadow:0 8px 30px #0008}
#tlbar button{width:34px;height:34px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--ink);
 font-size:14px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s}
#tlbar button:hover{background:var(--ochre);color:#170f02;border-color:var(--ochre)}
#tlbar #tl-scrub{width:min(40vw,320px);accent-color:var(--ochre);cursor:pointer}
#tlbar .tl-yr{font-family:var(--d);font-weight:600;font-size:17px;color:var(--ochre);min-width:48px;text-align:center}
</style></head>
<body>
<div id="stage"><div id="map"></div></div>
<div class="scrim"></div>
<div id="caption" class="hide"></div>
<div id="yearbig"></div>
<div id="clickread" class="hide"></div>

<div class="content">
 <section id="hero">
   <div class="kicker" id="kick"></div>
   <h1 id="htitle"></h1>
   <div class="stand" id="hstand"></div>
   <div class="by" id="hby"></div>
   <div class="scrolltip">scroll ↓</div>
 </section>

 <div class="panels" id="panels"></div>

 <section class="flat"><div class="inner">
   <h3>How this was measured</h3>
   <p id="method1"></p>
   <p>Land-surface temperature is the temperature of the ground itself — roofs, roads, fields — not the air a weather station reads. It runs hotter than air temperature, which is exactly why it reveals where a city traps heat. Forests and water stay cool; dense built-up districts glow.</p>
   <div class="meta" id="metagrid"></div>
   <p style="margin-top:18px">Blank areas carry no reliable reading (persistent cloud or water) and are left empty rather than guessed. This is a screening view, honest about its gaps.</p>
 </div></section>

 <footer>
   <div class="mark">Ground<span class="dot">_</span>truth</div>
   <p>A decade of Germany&rsquo;s summer ground temperature, measured from free satellite data and made legible to anyone.</p>
   <div class="next">Built from free Landsat data · NASA/USGS via Google Earth Engine</div>
 </footer>
</div>

<div class="lg" id="legend"></div>

<script>
const D = __DATA__;
const HEAT_RAMP='linear-gradient(90deg,#3a73d8,#4e9fbd,#d9cc59,#e68d38,#dc522e,#9e1a1f)';
const ANOM_RAMP='linear-gradient(90deg,#3a73d8,#4e9fbd,#eee,#e68d38,#dc522e,#9e1a1f)';

// ---- hero copy ----
document.getElementById('kick').textContent='Satellite journalism · Urban heat';
document.getElementById('htitle').textContent=D.title;
document.getElementById('hstand').textContent=D.standfirst;
document.getElementById('hby').textContent='By '+D.byline+' · real Landsat land-surface temperature';

// ---- map ----
const map=L.map('map',{zoomControl:false,attributionControl:false,scrollWheelZoom:false,dragging:false,doubleClickZoom:false,boxZoom:false,keyboard:false,tap:false});
const b=D.bounds, southwest=L.latLng(b[0][0],b[0][1]), northeast=L.latLng(b[1][0],b[1][1]);
const DE=L.latLngBounds(southwest,northeast);
map.fitBounds(DE);
let overlay=L.imageOverlay(D.png,DE,{opacity:0,interactive:false}).addTo(map);
function show(url){overlay.setUrl(url);overlay.setOpacity(.92);}
function fly(t){ if(t.b){map.flyToBounds(t.b,{duration:1.1});} else {map.flyToBounds(DE,{duration:1.1});} }

// ---- click anywhere to read the real value (context-aware per view) ----
function sampleGrid(g,lat,lon){if(!g)return null;
 const s=g.bbox[0],w=g.bbox[1],n=g.bbox[2],e=g.bbox[3];
 if(!(s<=lat&&lat<=n&&w<=lon&&lon<=e))return null;
 const col=Math.round((lon-w)/(e-w)*(g.nx-1)),row=Math.round((n-lat)/(n-s)*(g.ny-1));
 const v=g.z[row*g.nx+col];return (v===null||v===undefined)?null:v;}
let readMarker=null;
map.on('click',(ev)=>{
 const el=document.getElementById('clickread');
 const view=(steps[active]||{}).view||'abs';
 const lat=ev.latlng.lat, lon=ev.latlng.lng;
 let html=null;
 if(view==='cy'&&CY&&CY.grid_now){           // 2026 view: this summer vs normal
   const now=sampleGrid(CY.grid_now,lat,lon), nrm=sampleGrid(D.grid,lat,lon);
   if(now!==null){const dd=nrm!==null?Math.round((now-nrm)*10)/10:null;
     html=`<span class="cr-t">${now}°C</span>`+
       (nrm!==null?`<span class="cr-a">${dd>0?'+':''}${dd}° vs ${nrm}° normal</span>`:'<span class="cr-a">summer 2026</span>');}
 } else if(view==='anom'){                    // heat-island view: anomaly first
   const t=sampleGrid(D.grid,lat,lon);
   if(t!==null){const an=Math.round((t-D.baseline)*10)/10;
     html=`<span class="cr-t">${an>0?'+':''}${an}°C</span><span class="cr-a">vs ${D.baseline}° national avg · ${t}° actual</span>`;}
 } else {                                     // absolute / time-lapse / others
   const t=sampleGrid(D.grid,lat,lon);
   if(t!==null){const an=Math.round((t-D.baseline)*10)/10;
     html=`<span class="cr-t">${t}°C</span><span class="cr-a">${an>0?'+':''}${an}° vs ${D.baseline}° avg</span>`;}
 }
 if(html===null){el.classList.add('hide');return;}
 el.classList.remove('hide');
 el.innerHTML=html+`<span class="cr-x">${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E · click to read</span>`;
});
// enable clicking even though pan/zoom stay locked
map.dragging.disable();

// ---- clickable city markers with detail + anomaly sparkline ----
function spark(series, years, baseline){
 const v=series.filter(x=>x!=null); if(v.length<2) return '';
 const w=190,h=54,pad=6, lo=Math.min(...v,baseline), hi=Math.max(...v,baseline);
 const X=i=>pad+i*(w-2*pad)/(series.length-1);
 const Y=t=>h-pad-(t-lo)/(hi-lo+1e-6)*(h-2*pad);
 let d='',pts=[];
 series.forEach((t,i)=>{if(t==null)return; const x=X(i),y=Y(t); d+=(d?'L':'M')+x+' '+y+' '; pts.push([x,y,t,years[i]]);});
 const yb=Y(baseline);
 // trend line (first->last)
 const f=pts[0], l=pts[pts.length-1];
 return `<svg width="${w}" height="${h}" class="spark">
   <line x1="${pad}" y1="${yb}" x2="${w-pad}" y2="${yb}" stroke="#878e8a" stroke-dasharray="2 3" stroke-width="1"/>
   <path d="${d}" fill="none" stroke="#e0a64e" stroke-width="2"/>
   <line x1="${f[0]}" y1="${f[1]}" x2="${l[0]}" y2="${l[1]}" stroke="#d8694e" stroke-width="1" opacity="0.5"/>
   <circle cx="${l[0]}" cy="${l[1]}" r="3" fill="#d8694e"/>
 </svg>
 <div class="sparx"><span>${years[0]}</span><span style="color:#878e8a">— mean ${baseline}°C —</span><span>${years[years.length-1]}</span></div>`;
}
function cityPopup(c){
 const sign=c.anom>0?'+':'';
 let trend='';
 if(c.series){
   const v=c.series.filter(x=>x!=null);
   const rise=v.length>1?(v[v.length-1]-v[0]):0;
   trend=`<div class="pphot">${spark(c.series,c.years,D.baseline)}</div>
     <div class="ppnote">${rise>=0?'▲':'▼'} ${rise>=0?'+':''}${rise.toFixed(1)}°C across ${c.years[0]}–${c.years[c.years.length-1]}</div>`;
 }
 return `<div class="citypop"><h3>${c.name}</h3>
   <div class="bigt">${c.t}°C <span>ground</span></div>
   <div class="anomt ${c.anom>0?'up':''}">${sign}${c.anom}°C vs national average</div>
   ${trend}
   <div class="ppcoord">${c.lat.toFixed(2)}°N, ${c.lon.toFixed(2)}°E</div></div>`;
}
const cityMarks={};
function addCityMarkers(){
 D.cities.forEach(c=>{
  const hot=c.anom>3, col=hot?'#d8694e':(c.anom>0?'#e0a64e':'#7fb4ab');
  const mk=L.circleMarker([c.lat,c.lon],{radius:hot?7:5,color:'#0c0e0f',weight:1.5,
    fillColor:col,fillOpacity:.95}).addTo(map).bindPopup(cityPopup(c),{maxWidth:240,className:'cpop'});
  mk.bindTooltip(`${c.name} · ${c.t}°`,{permanent:true,direction:'right',className:'ctip',offset:[6,0]});
  cityMarks[c.name.toLowerCase()]=mk;
 });
}
let markersOn=false;
function toggleMarkers(on){ if(on===markersOn)return; markersOn=on;
 if(on){addCityMarkers();} else {Object.values(cityMarks).forEach(m=>map.removeLayer(m));
   for(const k in cityMarks)delete cityMarks[k];}
}

// ---- legend ----
function legend(mode){
 const L=document.getElementById('legend');
 if(mode==='anom'){L.innerHTML=`<div class="ttl">heat-island anomaly</div><div class="bar" style="background:${ANOM_RAMP}"></div><div class="tk"><span>cooler</span><span>10-yr mean</span><span>hotter</span></div>`;}
 else if(mode==='rate'){L.innerHTML=`<div class="ttl">warming rate · °C per decade</div><div class="bar" style="background:${ANOM_RAMP}"></div><div class="tk"><span>cooled</span><span>0</span><span>warmed</span></div>`;}
 else if(mode==='cyanom'){L.innerHTML=`<div class="ttl">summer ${CY?CY.year:''} vs 10-yr normal</div><div class="bar" style="background:${ANOM_RAMP}"></div><div class="tk"><span>cooler</span><span>normal</span><span>hotter</span></div>`;}
 else{L.innerHTML=`<div class="ttl">ground temperature</div><div class="bar" style="background:${HEAT_RAMP}"></div><div class="tk"><span>${D.vmin}°</span><span>${D.baseline}° mean</span><span>${D.vmax}°C</span></div>`;}
}
legend('abs');

// projected badge: makes a projection unmistakably NOT a measurement
function badge(on,year){
 let el=document.getElementById('projbadge');
 if(on){ if(!el){el=document.createElement('div');el.id='projbadge';document.body.appendChild(el);}
   el.innerHTML='◷ PROJECTION · '+(year||'')+'<span>extrapolated trend, not measured</span>';
   el.style.display='block'; document.getElementById('stage').classList.add('isproj');
 } else { if(el)el.style.display='none'; document.getElementById('stage').classList.remove('isproj'); }
}
// partial-year detector (from partial_label, e.g. "2026 ...")
const PARTIAL=(D.partial_label||'').match(/\b(20\d\d)\b/);
function isPartial(y){return PARTIAL&&String(y)===PARTIAL[1];}

// ---- panels (scrollytelling steps) ----
const hottest=D.cities[0], coolest=D.cities[D.cities.length-1];
const tl=D.timelapse;
const steps=[
 {eye:'What you are looking at',h:'This is Germany, measured from space',
  html:`<p>Each summer from ${tl?tl.dates[0]:'2016'} to ${tl?tl.dates[tl.dates.length-1]:'2025'}, the Landsat satellites recorded the temperature of the <b>ground itself</b> — roofs, roads, fields — across the whole country. We took the ten-year median: the typical summer surface.</p><p>Brighter red is hotter ground; blue is cool. The national average sits at <b>${D.baseline}°C</b> — and from here, the story is where it breaks from that average.</p>`,
  view:'abs',target:{}},
 {eye:'The hottest places',h:'Germany’s ten hottest cities',
  html:`<p>Rank every major city by its ten-year summer ground temperature and the built-up south leads. <b>${hottest.name}</b> tops the list at <b>${hottest.t}°C</b> — that’s <b>${hottest.anom>0?'+':''}${hottest.anom}°C</b> above the <b>${D.baseline}°C</b> national average.</p>`+rankHTML()+`<p class="src">Source: Landsat 8/9 (NASA/USGS) · 10-yr summer median, 2016–2025 · analysis Ground_truth</p>`,
  view:'abs',target:{b:DE},markers:true},
 {eye:'State by state',h:'How the sixteen states compare',
  html:`<p>Zoom out to the sixteen Bundesländer and the divide is regional, not random — the hottest ground clusters in the east and the cities. <b>${(D.states&&D.states[0])?D.states[0].name+' leads at '+D.states[0].t+'°C':''}</b>.</p>`+stateRankHTML()+`<p class="src">Source: Landsat 8/9 (NASA/USGS) · state mean of the 10-yr summer median · analysis Ground_truth</p>`,
  view:'abs',target:{b:DE},states:true},
 {eye:'Cities vs countryside',h:'Where the country traps heat',
  html:`<p>Now subtract the national average. <b>Red is hotter than the country as a whole; blue is cooler.</b> The pattern is unmistakable: rural land cools to blue, while built-up cores glow red — concrete and asphalt soak up the sun and hold it.</p><p>This drives the urban heat-island effect that makes city nights dangerous for the old, the young and the sick. Knowing exactly <i>where</i> the ground runs hottest is the first step to cooling it.</p>`,
  view:'anom',target:{}},
 {eye:'A decade of summers',h:'And it has been climbing',
  html:`<p>Play the years and the surface reddens. ${tl?`From <b>${tl.dates[0]}</b> to <b>${tl.dates[tl.dates.length-1]}</b>`:'Over the decade'}, hot summers have become the norm — the backdrop to the heat waves now crossing Europe.</p>${D.partial_label?`<p class="warn">${D.partial_label}.</p>`:''}`,
  view:'tl',target:{b:DE}},
];

// ---- THIS SUMMER vs the 10-year normal (the news hook) ----
const CY=D.current_year;
if(CY){
 const topc=(CY.cities||[]).slice(0,6);
 const sign=CY.national_delta>0?'+':'';
 const absline=(CY.national_now!==undefined&&CY.national_normal!==undefined)
   ?`<b>${CY.national_now}°C</b> this summer vs <b>${CY.national_normal}°C</b> normal`
   :`${sign}${CY.national_delta}°C above normal`;
 steps.push({eye:'Right now · summer '+CY.year,h:`This summer: ${CY.national_now!==undefined?CY.national_now+'°C':(sign+CY.national_delta+'°C above normal')}`,
  html:`<p>This isn’t the ten-year average any more — it’s <b>summer ${CY.year}, measured so far</b>, against each place’s own ten-year normal. <b>Red = hotter than normal; blue = cooler.</b></p>`+
   `<p>Nationally the ground is averaging ${absline} — <b>${sign}${CY.national_delta}°C</b> hotter than the ${CY.baseline_label||'2016–2025'} normal.</p>`+
   (topc.length?`<div class="cydelta"><div class="cyhdr"><span>City</span><span>this summer · normal</span></div>`+topc.map(c=>`<div class="cyrow"><span class="cyn">${c.name}</span><span class="cyabs">${c.now!==undefined?c.now+'° · '+c.normal+'°':''}</span><span class="cyv ${c.delta>0?'hot':'cool'}">${c.delta>0?'+':''}${c.delta}°</span></div>`).join('')+`</div>`:'')+
   `<p class="warn">${CY.note||('Summer '+CY.year+' is still unfolding — measured through the latest cloud-free passes.')}</p>`+
   `<p class="src">Source: Landsat 8/9 (NASA/USGS) · summer ${CY.year} vs ${CY.baseline_label||'2016–2025'} median · analysis Ground_truth</p>`,
  view:'cy',target:{b:DE}});
}

// ---- forecast chapters (added only when real trend data is supplied) ----
const FC=D.forecast;
if(FC){
 if(FC.national_per_decade!==undefined && FC.rate_png){
  steps.push({eye:'Measured · not a guess',h:'How fast each place is warming',
   html:`<p>This map isn’t a forecast — it’s the <b>measured trend</b>. We fit a straight line through ten years of real summer surfaces at every point on the map. Red means that ground warmed; blue means it cooled.</p><p>Across Germany the ground warmed about <b>${FC.national_per_decade>0?'+':''}${FC.national_per_decade}°C per decade</b>. That is what the satellites recorded, not what a model imagined.</p>`,
   view:'rate',target:{b:DE}});
 }
 (FC.projections||[]).forEach(pj=>{
  steps.push({eye:'Projection · not measurement',h:`If this trend holds, ${pj.year}`,
   html:`<p>Extend that measured line forward and, <b>if the last decade’s rate simply continued</b>, the typical summer ground in ${pj.year} looks like this — averaging <b>${pj.mean_temp}°C</b>${pj.increase_vs_baseline!==undefined?`, about <b>${pj.increase_vs_baseline>0?'+':''}${pj.increase_vs_baseline}°C</b> above today’s mean`:''}.</p><p class="warn">This is an extrapolation, not a measurement — a straight line drawn into the future, give or take <b>±${pj.uncertainty}°C</b>. It assumes nothing changes: no faster warming, no cooling action. The real point is the direction, and the direction is up.</p>`,
   view:'proj',proj:pj,target:{b:DE}});
 });
}
// closing interactive beat — make it personal
steps.push({eye:'Make it personal',h:'Find your city',
  html:`<p>Type a German city to read its real ten-year summer ground temperature, how far above the national average it sits, and its trend. Or click any dot on the map.</p>
   <div class="find"><input id="cityq" placeholder="e.g. ${hottest.name}, Karlsruhe, Berlin…" autocomplete="off"></div>
   <div class="readout" id="cityout"></div>`,
  view:'abs',target:{},markers:true});

function rankHTML(){
 const top=D.cities.slice(0,10);
 const max=Math.max(...top.map(c=>c.t)), min=Math.min(...D.cities.map(c=>c.t));
 let h='<ol class="rank">';
 top.forEach((c,i)=>{const f=(c.t-min)/(max-min+1e-6);
  const col=`hsl(${(1-f)*40+5},80%,${55-f*18}%)`;
  h+=`<li><span class="n">${i+1}</span><span class="nm">${c.name}</span><span class="sw" style="background:${col}"></span><span class="tp">${c.t}°C</span></li>`;});
 return h+'</ol>';
}
function stateRankHTML(){
 const ss=D.states||[]; if(!ss.length) return '<p>State data unavailable.</p>';
 const max=Math.max(...ss.map(s=>s.t)), min=Math.min(...ss.map(s=>s.t));
 let h='<ol class="rank states">';
 ss.forEach(s=>{const f=(s.t-min)/(max-min+1e-6);
  const col=`hsl(${(1-f)*40+5},80%,${55-f*18}%)`;
  h+=`<li><span class="n">${s.rank}</span><span class="nm">${s.name}</span><span class="sw" style="background:${col}"></span><span class="tp">${s.t}°C</span></li>`;});
 return h+'</ol><div class="rankfoot">Mean summer ground temperature, ranked hottest to coolest.</div>';
}

// ---- state boundaries: numbered outlines on the map + names on the right ----
let stateLayer=null, stateLabels=[];
function toggleStates(on){
 if(on){
  if(stateLayer) return;
  stateLayer=L.layerGroup().addTo(map);
  (D.states||[]).forEach(s=>{
   s.rings.forEach(ring=>{
    const latlngs=ring.map(([lon,lat])=>[lat,lon]);
    L.polygon(latlngs,{color:'#ededE6',weight:1,fill:false,opacity:.55,dashArray:'3 4'}).addTo(stateLayer);
   });
   // numbered marker at centroid
   const num=L.marker(s.c,{icon:L.divIcon({className:'snum',html:`<span>${s.rank}</span>`,iconSize:[22,22]})}).addTo(stateLayer);
   stateLabels.push(num);
  });
  buildStateLegend();
 } else {
  if(stateLayer){map.removeLayer(stateLayer);stateLayer=null;stateLabels=[];}
  const sl=document.getElementById('statekey'); if(sl)sl.remove();
 }
}
function buildStateLegend(){
 let el=document.getElementById('statekey');
 if(!el){el=document.createElement('div');el.id='statekey';document.body.appendChild(el);}
 const ss=D.states||[];
 el.innerHTML='<div class="sk-ttl">States · hottest → coolest</div>'+
  ss.map(s=>`<div class="sk-row"><span class="sk-n">${s.rank}</span><span class="sk-nm">${s.name}</span><span class="sk-t">${s.t}°</span></div>`).join('');
}

const panels=document.getElementById('panels');
steps.forEach((s,i)=>{
 const sec=document.createElement('section');sec.className='panel';sec.dataset.i=i;
 sec.innerHTML=`<div class="card"><div class="eyebrow">${s.eye}</div><h2>${s.h}</h2>${s.html}</div>`;
 panels.appendChild(sec);
});

// ---- method copy ----
document.getElementById('method1').textContent=
 `The map is built from Landsat 8 and 9 Collection-2 thermal imagery (band ST_B10), summer acquisitions only, ${tl?tl.dates[0]:'2016'}–${tl?tl.dates[tl.dates.length-1]:'2025'}. For every pixel we take the median summer surface temperature, clip to Germany, and render it. ${D.cities.length} cities are sampled directly from that grid.`;
document.getElementById('metagrid').innerHTML=
 `<div><div class="k">Source</div><div class="v">Landsat 8/9</div></div>`+
 `<div><div class="k">Measure</div><div class="v">Surface °C</div></div>`+
 `<div><div class="k">Period</div><div class="v">${tl?tl.dates[0]+'–'+tl.dates[tl.dates.length-1]:'10 years'}</div></div>`+
 `<div><div class="k">National mean</div><div class="v">${D.baseline}°C</div></div>`;

// ---- caption (time frame) + big year ----
const yrRange = tl ? (tl.dates[0]+'–'+tl.dates[tl.dates.length-1]) : '2016–2025';
function caption(label, sub){
 const el=document.getElementById('caption');
 if(!label){el.classList.add('hide');return;}
 el.innerHTML=`<span class="cl">${label}</span>${sub||''}`;el.classList.remove('hide');
}
function bigYear(txt){const el=document.getElementById('yearbig');
 if(!txt){el.classList.remove('show');return;} el.innerHTML=txt; el.classList.add('show');}
const CAP={
 abs:['10-year average · 2016–2025', 'Each spot is the typical summer ground temperature. Brighter red = hotter ground.'],
 anom:['heat-island · vs national mean', 'Red = hotter than the country’s average; blue = cooler. Cities glow red.'],
 rate:['warming trend · 2016–2025', 'Measured °C gained per decade at each point. Red warmed; blue cooled.'],
 proj:['projection', 'The measured trend extended forward — an estimate, not a measurement.'],
 tl:['summer by summer · '+( '2016–2025'), 'Use the controls below to play, pause or scrub through the years.']
};

// ---- scroll driving ----
let active=-1, tlTimer=null;
function setStep(i){
 if(i===active)return; active=i; const s=steps[i]; if(!s)return;
 stopTL();
 bigYear(null); tlControls(false);
 const cap=CAP[s.view]||CAP.abs;
 if(s.view==='abs'){show(D.png);legend('abs');badge(false);caption(cap[0],cap[1]);}
 else if(s.view==='anom'){show(D.png_anomaly||D.png);legend(D.png_anomaly?'anom':'abs');badge(false);caption(cap[0],cap[1]);}
 else if(s.view==='rate'&&FC){show(FC.rate_png);legend('rate');badge(false);caption(cap[0],cap[1]);}
 else if(s.view==='proj'&&s.proj){show(s.proj.png);legend('abs');badge(true,s.proj.year);
   caption('projection · '+s.proj.year, 'if the measured trend continued');}
 else if(s.view==='cy'&&CY){show(CY.png);legend('cyanom');badge(false);
   caption('summer '+CY.year+' vs normal', 'red = hotter than this place’s 10-yr normal · partial summer');}
 else if(s.view==='tl'&&tl){
   legend('abs');badge(false);caption(cap[0],cap[1]);
   tlSetup(); tlControls(true); tlPlay();      // show controls + start playing
 } else {show(D.png);legend('abs');badge(false);caption(cap[0],cap[1]);}
 toggleMarkers(!!s.markers);
 toggleStates(!!s.states);
 fly(s.target);
}
// ---- time-lapse player (play / pause / restart / scrub) ----
let tlK=0, tlPlaying=false;
function tlLab(d){return d+(isPartial(d)?' · partial':'');}
function tlFrame(k){tlK=((k%tl.frames.length)+tl.frames.length)%tl.frames.length;
 show(tl.frames[tlK]); bigYear(tlLab(tl.dates[tlK])+'<small>summer ground temp</small>');
 const sc=document.getElementById('tl-scrub'); if(sc)sc.value=tlK;
 const yr=document.getElementById('tl-yr'); if(yr)yr.textContent=tl.dates[tlK];}
function tlSetup(){tlK=0;tlFrame(0);}
function tlPlay(){if(tlPlaying)return;tlPlaying=true;tlBtn();
 tlTimer=setInterval(()=>tlFrame(tlK+1),950);}
function tlPause(){tlPlaying=false;if(tlTimer){clearInterval(tlTimer);tlTimer=null;}tlBtn();}
function tlStop(){tlPause();tlFrame(0);}            // restart to first year
function stopTL(){if(tlTimer){clearInterval(tlTimer);tlTimer=null;}tlPlaying=false;}
function tlBtn(){const b=document.getElementById('tl-play');if(b)b.innerHTML=tlPlaying?'❚❚':'▶';}
function tlControls(on){
 let bar=document.getElementById('tlbar');
 if(on){
  if(!bar){bar=document.createElement('div');bar.id='tlbar';document.body.appendChild(bar);
   bar.innerHTML=`<button id="tl-play" title="Play / pause">▶</button>
    <button id="tl-stop" title="Restart">⟲</button>
    <input id="tl-scrub" type="range" min="0" max="${tl.frames.length-1}" value="0">
    <span id="tl-yr" class="tl-yr">${tl.dates[0]}</span>`;
   document.getElementById('tl-play').onclick=()=>tlPlaying?tlPause():tlPlay();
   document.getElementById('tl-stop').onclick=()=>tlStop();
   document.getElementById('tl-scrub').oninput=(e)=>{tlPause();tlFrame(+e.target.value);};
  }
  bar.style.display='flex';
 } else if(bar){bar.style.display='none';}
}
const io=new IntersectionObserver((es)=>{es.forEach(e=>{if(e.isIntersecting)setStep(+e.target.dataset.i);});},
 {threshold:.55});
document.querySelectorAll('.panel').forEach(p=>io.observe(p));

// reveal map after hero
const heroIO=new IntersectionObserver((es)=>{es.forEach(e=>{if(!e.isIntersecting&&active<0)setStep(0);});},{threshold:.2});
heroIO.observe(document.getElementById('hero'));

// ---- find your city ----
function readCity(q){
 q=q.trim().toLowerCase();if(!q)return '';
 const c=D.cities.find(c=>c.name.toLowerCase().startsWith(q))||D.cities.find(c=>c.name.toLowerCase().includes(q));
 if(!c)return `<span style="color:var(--muted)">No reading for “${q}”. Try a major city.</span>`;
 const sign=c.anom>0?'+':'';
 const hot=c.anom>3?'hot':'';
 return `<b>${c.name}</b> — <span class="${hot?'hot':''}">${c.t}°C</span> ground temperature · <b>${sign}${c.anom}°C</b> vs national average`;
}
document.addEventListener('input',(e)=>{if(e.target&&e.target.id==='cityq'){
 const q=e.target.value.trim().toLowerCase();
 document.getElementById('cityout').innerHTML=readCity(q);
 if(q.length>=2){const c=D.cities.find(c=>c.name.toLowerCase().startsWith(q));
   if(c){toggleMarkers(true);const mk=cityMarks[c.name.toLowerCase()];
     if(mk){map.flyTo([c.lat,c.lon],7,{duration:.8});setTimeout(()=>mk.openPopup(),820);}}}
}});
</script>
</body></html>"""
