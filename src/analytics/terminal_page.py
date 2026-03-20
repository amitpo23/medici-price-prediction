"""Trading Terminal — unified dark-themed dashboard for hotel options traders."""
from __future__ import annotations


def generate_terminal_html() -> str:
    """Return self-contained HTML for the Trading Terminal dashboard."""
    return _TERMINAL_HTML


_TERMINAL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Terminal — Medici</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#1a1a2e;--surface:#16213e;--panel:#0f3460;
  --border:#1f4068;--text:#eee;--muted:#8899aa;
  --call:#00c853;--put:#ff1744;--none:#757575;
  --tp-min:#00e676;--tp-max:#ff5252;
  --band:rgba(33,150,243,0.15);
  --ev-event:#ef5350;--ev-season:#ffa726;--ev-demand:#42a5f5;
  --ev-momentum:#ab47bc;--ev-weather:#26c6da;--ev-competitor:#66bb6a;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px}
.page{max-width:1600px;margin:0 auto;padding:12px}
h1{font-size:18px;font-weight:700}
a{color:#42a5f5;text-decoration:none}

/* Header */
.hdr{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid var(--border);margin-bottom:12px}
.hdr select{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:5px 8px;font-size:13px;min-width:180px}
.hdr label{display:flex;align-items:center;gap:4px;font-size:12px;color:var(--muted)}
.hdr .ts{margin-left:auto;font-size:11px;color:var(--muted);font-family:monospace}

/* Layout — stacked vertically so charts are full-width */
.main{display:flex;flex-direction:column;gap:12px}
.panels-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}

/* Chart containers */
.chart-box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;position:relative;overflow:visible}
.chart-box canvas{width:100%!important}
.chart-title{font-size:12px;font-weight:600;margin-bottom:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}

/* Side panels */
.panel{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px}
.panel-title{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;border-bottom:1px solid var(--border);padding-bottom:6px}

/* Signal badge */
.sig{display:inline-block;padding:3px 10px;border-radius:4px;font-weight:700;font-size:13px;letter-spacing:.5px}
.sig.call{background:var(--call);color:#000}.sig.put{background:var(--put);color:#fff}.sig.neutral{background:var(--none);color:#fff}

/* Signal summary rows */
.sig-row{display:flex;justify-content:space-between;padding:3px 0;font-size:12px}
.sig-row .lbl{color:var(--muted)}.sig-row .val{font-family:monospace;font-weight:600}
.sig-row .val.up{color:var(--call)}.sig-row .val.down{color:var(--put)}

/* Source rows */
.src-row{display:flex;align-items:center;gap:6px;padding:4px 0;font-size:12px;border-bottom:1px solid rgba(255,255,255,.05)}
.src-name{flex:1;color:var(--muted);min-width:100px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.src-dir{width:56px;text-align:center;font-weight:600;border-radius:3px;padding:1px 4px;font-size:11px}
.src-dir.call{background:rgba(0,200,83,.2);color:var(--call)}
.src-dir.put{background:rgba(255,23,68,.2);color:var(--put)}
.src-dir.neutral{background:rgba(117,117,117,.2);color:var(--none)}
.src-agree{width:16px;text-align:center}.src-conf{width:40px;text-align:right;font-family:monospace;color:var(--muted)}
.src-price{width:60px;text-align:right;font-family:monospace}

/* Warning */
.warn-banner{background:rgba(255,23,68,.15);border:1px solid var(--put);border-radius:6px;padding:8px 12px;font-size:12px;font-weight:600;color:var(--put);text-align:center;display:none}
.warn-banner.show{display:block}

/* Accuracy */
.acc-row{display:flex;justify-content:space-between;padding:2px 0;font-size:12px}
.acc-row .lbl{color:var(--muted)}.acc-row .val{font-family:monospace}

/* Override controls */
.ovr-bar{background:var(--surface);border:1px solid var(--override);border-radius:8px;padding:10px 14px;margin-bottom:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ovr-bar .ovr-title{font-size:12px;font-weight:600;color:var(--override)}
.ovr-bar input[type=number]{background:var(--bg);color:var(--text);border:1px solid var(--override);border-radius:4px;padding:4px 8px;font-size:13px;width:80px;font-family:monospace}
.ovr-bar select{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:12px}
.ovr-bar .ovr-info{font-size:11px;color:var(--muted)}
.btn-ovr{background:var(--override);color:#000;border:none;border-radius:4px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer}
.btn-ovr:hover{filter:brightness(1.15)}
.btn-ovr:disabled{opacity:.4;cursor:default}
.btn-ovr-sm{background:var(--override);color:#000;border:none;border-radius:3px;padding:2px 8px;font-size:10px;font-weight:600;cursor:pointer}
.btn-ovr-sm:hover{filter:brightness(1.15)}
.btn-ovr-sm:disabled{opacity:.4;cursor:default}
.btn-ovr-sm.queued{background:var(--pending);cursor:default}
.ovr-inline{display:inline-flex;align-items:center;gap:4px}
.ovr-inline input{background:var(--bg);color:var(--text);border:1px solid var(--override);border-radius:3px;padding:2px 4px;font-size:11px;width:55px;font-family:monospace}
.toast{position:fixed;top:16px;right:16px;padding:10px 16px;border-radius:6px;font-size:13px;font-weight:500;z-index:9999;animation:fadeIn .3s}
.toast.ok{background:rgba(76,175,80,.9);color:#fff}.toast.err{background:rgba(244,67,54,.9);color:#fff}
@keyframes fadeIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:none}}
.ovr-panel{border-top:1px solid var(--border);margin-top:8px;padding-top:8px}
.queue-status{font-size:11px;color:var(--muted);display:flex;gap:12px;align-items:center}

/* Options table */
.opts-section{margin-top:16px}
.opts-controls{display:flex;gap:8px;margin-bottom:8px;align-items:center}
.opts-controls select,.opts-controls input{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:12px}
.opts-table{width:100%;border-collapse:collapse;font-size:12px;background:var(--surface);border-radius:8px;overflow:hidden}
.opts-table th{background:var(--panel);padding:6px 8px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);position:sticky;top:0;cursor:pointer;user-select:none;border-bottom:2px solid var(--border)}
.opts-table th:hover{color:var(--text)}
.opts-table td{padding:5px 8px;border-bottom:1px solid rgba(255,255,255,.04);font-family:monospace}
.opts-table tr:hover{background:rgba(255,255,255,.04);cursor:pointer}
.opts-table tr.active{background:rgba(33,150,243,.15)}
.opts-scroll{max-height:320px;overflow:auto;border:1px solid var(--border);border-radius:8px}

/* Loading */
.loading{text-align:center;padding:40px;color:var(--muted)}
.spin{display:inline-block;width:24px;height:24px;border:2px solid var(--border);border-top-color:#42a5f5;border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.empty{text-align:center;padding:30px;color:var(--muted);font-style:italic}

@media(max-width:900px){
  .panels-row{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class="page">
<!-- Header -->
<div class="hdr">
  <h1>Trading Terminal</h1>
  <select id="sel-hotel"><option value="">Select Hotel...</option></select>
  <select id="sel-option" disabled><option value="">Select Option...</option></select>
  <label><input type="checkbox" id="chk-refresh"> Auto-refresh</label>
  <span class="ts" id="ts-updated">--</span>
  <a href="/api/v1/salesoffice/home" style="font-size:12px">&larr; Home</a>
</div>

<!-- Main layout — charts full-width, panels row below -->
<div class="main">
  <!-- Charts full-width -->
  <div class="chart-box" style="min-height:360px">
    <div class="chart-title">Price Path</div>
    <div id="price-loading" class="empty">Select a hotel and option to view price path</div>
    <canvas id="price-chart" style="display:none"></canvas>
  </div>
  <div class="chart-box" style="min-height:200px">
    <div class="chart-title">Enrichment Decomposition</div>
    <div id="enrich-loading" class="empty">Select an option to view enrichments</div>
    <canvas id="enrich-chart" style="display:none"></canvas>
  </div>

  <!-- Panels side by side -->
  <div class="panels-row">
    <div class="panel" id="panel-signal">
      <div class="panel-title">Signal Summary</div>
      <div id="signal-body" class="empty">Select an option</div>
    </div>
    <div class="panel" id="panel-sources">
      <div class="panel-title">Source Consensus</div>
      <div class="warn-banner" id="disagree-warn">SOURCES DISAGREE — verify before trading</div>
      <div id="sources-body" class="empty">Select an option</div>
    </div>
    <div class="panel" id="panel-accuracy">
      <div class="panel-title">Accuracy &amp; Context</div>
      <div id="accuracy-body" class="empty">Select an option</div>
    </div>
  </div>
</div>

<!-- Options table -->
<div class="opts-section">
  <!-- Bulk Override Bar -->
  <div class="ovr-bar" id="ovr-bar" style="display:none">
    <span class="ovr-title">&#11015; Bulk Override PUTs</span>
    <label style="font-size:12px;color:var(--muted)">Discount: <input type="number" id="ovr-discount" value="1.00" min="0.01" max="10" step="0.50"></label>
    <button class="btn-ovr" id="btn-bulk-ovr" disabled>&#9654; Queue All PUTs</button>
    <span class="ovr-info" id="ovr-put-count">PUT signals: --</span>
    <span class="queue-status" id="queue-status"></span>
    <a href="/api/v1/salesoffice/dashboard/override-queue" style="font-size:11px;margin-left:auto">View Queue &rarr;</a>
  </div>

  <div class="opts-controls">
    <span style="font-size:12px;color:var(--muted);font-weight:600">OPTIONS</span>
    <select id="opts-sort">
      <option value="trade">Sort: Best Trade%</option>
      <option value="signal">Sort: Signal</option>
      <option value="disagree">Sort: Disagreements</option>
      <option value="price">Sort: Price</option>
    </select>
  </div>
  <div class="opts-scroll">
    <table class="opts-table">
      <thead><tr>
        <th>ID</th><th>Category</th><th>Board</th><th>Check-in</th><th>T</th>
        <th>Price</th><th>Signal</th><th>Min&rarr;Max</th><th>Trade%</th><th>Consensus</th><th></th><th>Override</th>
      </tr></thead>
      <tbody id="opts-body"><tr><td colspan="12" class="empty">Select a hotel</td></tr></tbody>
    </table>
  </div>
</div>
</div>

<script>
/* ── State ──────────────────────────────────────────────────────── */
const S = {
  hotelId: null, detailId: null,
  options: [], hotels: new Map(),
  priceChart: null, enrichChart: null,
  refreshTimer: null,
};
const API = '/api/v1/salesoffice';
const el = k => document.getElementById(k);

/* ── Helpers ────────────────────────────────────────────────────── */
function fmt$(v){return '$'+Number(v).toLocaleString('en-US',{maximumFractionDigits:0})}
function fmtPct(v){return (v>=0?'+':'')+Number(v).toFixed(1)+'%'}
function esc(v){const d=document.createElement('div');d.textContent=v;return d.innerHTML}
function sigCls(s){return s==='CALL'?'call':s==='PUT'?'put':'neutral'}
function shortDate(d){if(!d)return'';return d.length>=10?d.substring(5,10):d}

async function api(path){
  try{
    const r=await fetch(API+path,{cache:'no-store'});
    if(!r.ok)return null;
    return await r.json();
  }catch(e){return null}
}

/* ── Init ───────────────────────────────────────────────────────── */
async function init(){
  el('price-loading').innerHTML='Loading options...';
  const data=await api('/options?limit=500&profile=lite');
  if(!data||!data.rows){
    el('price-loading').innerHTML='Cache warming up... retrying in 10s. <a href="#" onclick="init();return false">Retry now</a>';
    setTimeout(init,10000);
    return;
  }
  S.options=data.rows;
  S.hotels.clear();
  data.rows.forEach(r=>{
    if(!S.hotels.has(r.hotel_id))S.hotels.set(r.hotel_id,r.hotel_name);
  });
  const sel=el('sel-hotel');
  sel.innerHTML='<option value="">Select Hotel...</option>';
  [...S.hotels.entries()].sort((a,b)=>a[1].localeCompare(b[1])).forEach(([id,name])=>{
    const o=document.createElement('option');o.value=id;o.textContent=name;sel.appendChild(o);
  });
  el('price-loading').innerHTML='Select a hotel and option to view price path';
  el('ts-updated').textContent='Ready — '+S.options.length+' options loaded';
}

/* ── Hotel selected ─────────────────────────────────────────────── */
function onHotelChange(){
  S.hotelId=el('sel-hotel').value||null;
  S.detailId=null;
  const optSel=el('sel-option');
  optSel.innerHTML='<option value="">Select Option...</option>';
  optSel.disabled=!S.hotelId;
  clearTerminal();
  if(!S.hotelId){el('opts-body').innerHTML='<tr><td colspan="12" class="empty">Select a hotel</td></tr>';return}
  const filtered=S.options.filter(r=>String(r.hotel_id)===String(S.hotelId));
  filtered.forEach(r=>{
    const o=document.createElement('option');
    o.value=r.detail_id;
    o.textContent=`${r.category} / ${r.board} — ${shortDate(r.date_from)} (T=${r.days_to_checkin})`;
    optSel.appendChild(o);
  });
  renderTable(filtered);
}

/* ── Option selected ────────────────────────────────────────────── */
function onOptionChange(){
  S.detailId=el('sel-option').value||null;
  if(S.detailId)loadTerminal(S.detailId);
  highlightRow();
}

function selectFromTable(detailId){
  S.detailId=String(detailId);
  el('sel-option').value=S.detailId;
  loadTerminal(S.detailId);
  highlightRow();
}

function highlightRow(){
  document.querySelectorAll('.opts-table tbody tr').forEach(tr=>{
    tr.classList.toggle('active',tr.dataset.id===String(S.detailId));
  });
}

/* ── Clear ──────────────────────────────────────────────────────── */
function clearTerminal(){
  if(S.priceChart){S.priceChart.destroy();S.priceChart=null}
  if(S.enrichChart){S.enrichChart.destroy();S.enrichChart=null}
  el('price-chart').style.display='none';
  el('price-loading').style.display='block';el('price-loading').className='empty';el('price-loading').innerHTML='Select an option to view price path';
  el('enrich-chart').style.display='none';
  el('enrich-loading').style.display='block';el('enrich-loading').className='empty';el('enrich-loading').innerHTML='Select an option to view enrichments';
  el('signal-body').innerHTML='<div class="empty">Select an option</div>';
  el('sources-body').innerHTML='<div class="empty">Select an option</div>';
  el('accuracy-body').innerHTML='<div class="empty">Select an option</div>';
  el('disagree-warn').classList.remove('show');
}

/* ── Load Terminal ──────────────────────────────────────────────── */
async function loadTerminal(detailId){
  clearTerminal();
  el('ts-updated').textContent='Loading...';
  el('price-loading').className='loading';el('price-loading').innerHTML='<div class="spin"></div>';el('price-loading').style.display='block';el('price-chart').style.display='none';
  el('enrich-loading').className='loading';el('enrich-loading').innerHTML='<div class="spin"></div>';el('enrich-loading').style.display='block';el('enrich-chart').style.display='none';

  const [fcRaw, pathData, sourceData, detailData, histData]=await Promise.all([
    api(`/forward-curve/${detailId}?raw=true`),
    api(`/path-forecast/${detailId}`),
    api(`/sources/compare/${detailId}`),
    api(`/options/detail/${detailId}`),
    api(`/charts/contract-data?detail_id=${detailId}`),
  ]);

  el('ts-updated').textContent=new Date().toLocaleTimeString();

  renderPriceChart(fcRaw, pathData, histData);
  renderEnrichChart(fcRaw);
  renderSignalPanel(fcRaw, pathData, detailData);
  renderSourcesPanel(sourceData);
  renderAccuracyPanel(detailData, fcRaw);
}

/* ── Price Chart ────────────────────────────────────────────────── */
function renderPriceChart(fcRaw, pathData, histData){
  el('price-loading').style.display='none';
  const canvas=el('price-chart');canvas.style.display='block';

  const fc=fcRaw?.forward_curve||[];
  const rawFc=fcRaw?.raw_forward_curve||[];
  if(!fc.length){canvas.style.display='none';return}

  const labels=fc.map(p=>shortDate(p.date));
  const datasets=[];

  // Confidence band (lower)
  datasets.push({
    label:'Lower Bound',data:fc.map(p=>p.lower_bound??p.predicted_price),
    borderColor:'transparent',backgroundColor:'transparent',
    pointRadius:0,fill:false,order:10
  });
  // Confidence band (upper fill to lower)
  datasets.push({
    label:'Confidence Band',data:fc.map(p=>p.upper_bound??p.predicted_price),
    borderColor:'transparent',backgroundColor:'rgba(33,150,243,0.12)',
    pointRadius:0,fill:'-1',order:9
  });

  // Ensemble forecast
  datasets.push({
    label:'Ensemble Forecast',data:fc.map(p=>p.predicted_price),
    borderColor:'#64b5f6',backgroundColor:'transparent',
    borderWidth:2.5,pointRadius:0,tension:0.3,order:2
  });

  // Raw decay curve
  if(rawFc.length){
    datasets.push({
      label:'Raw Decay Curve',data:rawFc.map(p=>p.predicted_price),
      borderColor:'#90a4ae',backgroundColor:'transparent',
      borderWidth:1.5,borderDash:[6,3],pointRadius:0,tension:0.3,order:3
    });
  }

  // Historical scan prices
  if(histData){
    const series=histData.scan||histData.scan_price_series||histData.prices||[];
    if(series.length){
      // Map historical dates to fc labels
      const histPoints=new Array(labels.length).fill(null);
      series.forEach(s=>{
        const d=shortDate(s.date||s.d);
        const idx=labels.indexOf(d);
        if(idx>=0)histPoints[idx]=s.price||s.p;
      });
      datasets.push({
        label:'Actual History',data:histPoints,
        borderColor:'#e0e0e0',backgroundColor:'transparent',
        borderWidth:1.5,pointRadius:2,pointBackgroundColor:'#e0e0e0',
        spanGaps:true,tension:0,order:1
      });
    }
  }

  // Turning points as scatter
  if(pathData?.turning_points?.length){
    const tpMin=[],tpMax=[];
    pathData.turning_points.forEach(tp=>{
      const d=shortDate(tp.date);const idx=labels.indexOf(d);
      if(idx<0)return;
      const pt={x:idx,y:tp.price};
      if(tp.type==='MIN')tpMin.push(pt);else tpMax.push(pt);
    });
    if(tpMin.length)datasets.push({
      label:'MIN (Buy)',data:tpMin,type:'scatter',
      pointRadius:7,pointStyle:'triangle',
      pointBackgroundColor:'var(--tp-min)',pointBorderColor:'var(--tp-min)',
      order:0
    });
    if(tpMax.length)datasets.push({
      label:'MAX (Sell)',data:tpMax,type:'scatter',
      pointRadius:7,pointStyle:'triangle',pointRotation:180,
      pointBackgroundColor:'var(--tp-max)',pointBorderColor:'var(--tp-max)',
      order:0
    });
  }

  // Historical + ML as horizontal lines
  const addHLine=(label,price,color)=>{
    if(!price||price<=0)return;
    datasets.push({
      label,data:new Array(labels.length).fill(price),
      borderColor:color,backgroundColor:'transparent',
      borderWidth:1,borderDash:[3,3],pointRadius:0,order:5
    });
  };

  // Try to get source predictions from detail data or fcRaw
  const spreds=fcRaw?._source_prediction_summary_catalog||{};
  const histPred=spreds.historical_pattern;
  const mlPred=spreds.ml_forecast;
  if(histPred?.predicted_price)addHLine('Historical Pattern',histPred.predicted_price,'#ffcc80');
  if(mlPred?.predicted_price)addHLine('ML Forecast',mlPred.predicted_price,'#a5d6a7');

  // Best buy/sell lines
  if(pathData?.best_buy_price>0)addHLine('Best Buy',pathData.best_buy_price,'rgba(0,230,118,0.6)');
  if(pathData?.best_sell_price>0)addHLine('Best Sell',pathData.best_sell_price,'rgba(255,82,82,0.6)');

  if(S.priceChart)S.priceChart.destroy();
  S.priceChart=new Chart(canvas,{
    type:'line',
    data:{labels,datasets},
    options:{
      responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{display:true,position:'bottom',labels:{color:'#aaa',font:{size:10},boxWidth:12,padding:8,usePointStyle:true}},
        tooltip:{
          backgroundColor:'rgba(22,33,62,0.95)',titleColor:'#eee',bodyColor:'#ccc',
          callbacks:{label:ctx=>{
            if(ctx.parsed.y==null)return null;
            return ctx.dataset.label+': $'+ctx.parsed.y.toFixed(0);
          }}
        }
      },
      scales:{
        x:{ticks:{color:'#90a4ae',font:{size:10},maxTicksLimit:12},grid:{color:'rgba(255,255,255,0.08)'}},
        y:{ticks:{color:'#b0bec5',font:{size:10},callback:v=>'$'+v},grid:{color:'rgba(255,255,255,0.1)'},position:'right'}
      }
    }
  });
}

/* ── Enrichment Chart ───────────────────────────────────────────── */
function renderEnrichChart(fcRaw){
  el('enrich-loading').style.display='none';
  const canvas=el('enrich-chart');canvas.style.display='block';

  const fc=fcRaw?.forward_curve||[];
  if(!fc.length){canvas.style.display='none';return}

  const labels=fc.map(p=>shortDate(p.date));
  const fields=[
    {key:'event_adj_pct',label:'Events',color:'#ef5350'},
    {key:'season_adj_pct',label:'Seasonality',color:'#ffa726'},
    {key:'demand_adj_pct',label:'Demand',color:'#42a5f5'},
    {key:'momentum_adj_pct',label:'Momentum',color:'#ab47bc'},
    {key:'weather_adj_pct',label:'Weather',color:'#26c6da'},
    {key:'competitor_adj_pct',label:'Competitors',color:'#66bb6a'},
  ];

  const datasets=fields.map(f=>({
    label:f.label,
    data:fc.map(p=>parseFloat(p[f.key]||0)),
    backgroundColor:f.color+'cc',borderColor:f.color,borderWidth:0.5,
  }));

  if(S.enrichChart)S.enrichChart.destroy();
  S.enrichChart=new Chart(canvas,{
    type:'bar',
    data:{labels,datasets},
    options:{
      responsive:true,maintainAspectRatio:false,
      plugins:{
        legend:{display:true,position:'bottom',labels:{color:'#aaa',font:{size:10},boxWidth:10,padding:6}},
        tooltip:{backgroundColor:'rgba(22,33,62,0.95)',titleColor:'#eee',bodyColor:'#ccc',
          callbacks:{label:ctx=>ctx.dataset.label+': '+ctx.parsed.y.toFixed(3)+'%'}}
      },
      scales:{
        x:{stacked:true,ticks:{color:'#666',font:{size:9},maxTicksLimit:12},grid:{display:false}},
        y:{stacked:true,ticks:{color:'#888',font:{size:10},callback:v=>v.toFixed(2)+'%'},grid:{color:'rgba(255,255,255,0.06)'}}
      }
    }
  });
}

/* ── Signal Panel ───────────────────────────────────────────────── */
function renderSignalPanel(fcRaw, pathData, detailData){
  const d=detailData||fcRaw||{};
  const sig=d.sig||d.option_signal||'--';
  const cp=d.cp||d.current_price||0;
  const pp=d.pp||d.predicted_checkin_price||0;
  const chg=cp>0?((pp/cp-1)*100):0;
  const mom=d.mom||d.momentum||{};
  const reg=d.reg||d.regime||{};

  const pMin=pathData?.predicted_min_price;
  const pMinT=pathData?.predicted_min_t;
  const pMinD=pathData?.predicted_min_date;
  const pMax=pathData?.predicted_max_price;
  const pMaxT=pathData?.predicted_max_t;
  const pMaxD=pathData?.predicted_max_date;
  const reversals=pathData?((pathData.num_up_segments||0)+(pathData.num_down_segments||0)-1):0;
  const bestTrade=pathData?.max_trade_profit_pct||0;
  const q=d.q||d.confidence_quality||'';

  el('signal-body').innerHTML=
    '<div style="text-align:center;margin-bottom:8px"><span class="sig '+sigCls(sig)+'">'+esc(sig)+'</span>'+
    (q?' <span style="color:var(--muted);font-size:11px">('+esc(q)+')</span>':'')+
    '</div>'+
    '<div class="sig-row"><span class="lbl">Current</span><span class="val">'+fmt$(cp)+'</span></div>'+
    '<div class="sig-row"><span class="lbl">Predicted</span><span class="val '+(chg>=0?'up':'down')+'">'+fmt$(pp)+' ('+fmtPct(chg)+')</span></div>'+
    (pMin!=null?'<div class="sig-row"><span class="lbl">Min</span><span class="val down">'+fmt$(pMin)+' @ T='+pMinT+(pMinD?' ('+shortDate(pMinD)+')':'')+'</span></div>':'')+
    (pMax!=null?'<div class="sig-row"><span class="lbl">Max</span><span class="val up">'+fmt$(pMax)+' @ T='+pMaxT+(pMaxD?' ('+shortDate(pMaxD)+')':'')+'</span></div>':'')+
    '<div class="sig-row"><span class="lbl">Reversals</span><span class="val">'+(reversals>0?reversals:0)+'</span></div>'+
    '<div class="sig-row"><span class="lbl">Best Trade</span><span class="val '+(bestTrade>0?'up':'')+'">'+fmtPct(bestTrade)+'</span></div>'+
    '<div class="sig-row"><span class="lbl">Regime</span><span class="val">'+(reg.regime||reg.label||'--')+'</span></div>'+
    '<div class="sig-row"><span class="lbl">Momentum</span><span class="val">'+(mom.signal||'--')+'</span></div>'+
    ((sig==='PUT'||sig==='STRONG_PUT')
      ? '<div class="ovr-panel"><div class="ovr-inline">'+
        '<button class="btn-ovr" onclick="queueOverride('+d.detail_id+','+cp+')" id="panel-ovr-btn">&#11015; Override -$<span id="panel-ovr-disc">'+(parseFloat(el('ovr-discount').value)||1).toFixed(2)+'</span></button>'+
        '<span style="color:var(--muted);font-size:11px">&rarr; '+fmt$(cp-(parseFloat(el('ovr-discount').value)||1))+'</span>'+
        '</div></div>'
      : (sig==='CALL'||sig==='STRONG_CALL')
        ? '<div class="ovr-panel"><div class="ovr-inline">'+
          '<button class="btn-ovr" style="background:var(--call)" onclick="queueOpportunity('+d.detail_id+','+cp+')">&#11014; Buy Opp</button>'+
          '<span style="color:var(--muted);font-size:11px">buy '+fmt$(cp)+' &rarr; push '+fmt$(cp+50)+' (+$50)</span>'+
          '</div></div>'
        : '');
}

/* ── Sources Panel ──────────────────────────────────────────────── */
function renderSourcesPanel(sourceData){
  if(!sourceData){el('sources-body').innerHTML='<div class="empty">No data</div>';return}

  const preds=sourceData.source_predictions||[];
  const consensus=sourceData.consensus_direction||'--';
  const strength=sourceData.consensus_strength||0;
  const ensDir=sourceData.ensemble_direction||'--';
  const ensVsCons=sourceData.ensemble_vs_consensus||'--';
  const disagree=sourceData.disagreement_flag;

  el('disagree-warn').classList.toggle('show',!!disagree);

  let html='';
  preds.forEach(p=>{
    const dir=p.direction||'NEUTRAL';
    const agrees=dir===consensus;
    html+='<div class="src-row">'+
      '<span class="src-name" title="'+esc(p.source_label||p.source_name)+'">'+esc(p.source_label||p.source_name)+'</span>'+
      '<span class="src-dir '+sigCls(dir)+'">'+dir+'</span>'+
      '<span class="src-agree">'+(agrees?'<span style="color:var(--call)">&#10003;</span>':'<span style="color:var(--put)">&#10007;</span>')+'</span>'+
      '<span class="src-conf">'+(p.confidence>0?(p.confidence*100).toFixed(0)+'%':'--')+'</span>'+
      '<span class="src-price">'+fmt$(p.predicted_price)+'</span>'+
    '</div>';
  });
  html+='<div style="border-top:1px solid var(--border);margin-top:6px;padding-top:6px;font-size:12px;display:flex;justify-content:space-between">'+
    '<span>Consensus: <b class="'+sigCls(consensus)+'">'+consensus+' ('+(strength*100).toFixed(0)+'%)</b></span>'+
    '<span>Ensemble: <b class="'+sigCls(ensDir)+'">'+ensDir+'</b> &mdash; '+ensVsCons+'</span>'+
  '</div>';
  el('sources-body').innerHTML=html;
}

/* ── Accuracy Panel ─────────────────────────────────────────────── */
function renderAccuracyPanel(detailData, fcRaw){
  const d=detailData||{};
  const q=d.q||fcRaw?.confidence_quality||'--';
  const scans=d.scans||0;
  const lastScan=d.scan_history?.latest_scan_date||fcRaw?.forward_curve?.[0]?.date||'--';
  const drops=d.drops||0;
  const rises=d.rises||0;

  el('accuracy-body').innerHTML=
    '<div class="acc-row"><span class="lbl">Data Quality</span><span class="val">'+esc(String(q).toUpperCase())+'</span></div>'+
    '<div class="acc-row"><span class="lbl">Scan Snapshots</span><span class="val">'+scans+'</span></div>'+
    '<div class="acc-row"><span class="lbl">Price Drops / Rises</span><span class="val" style="color:var(--put)">'+drops+'</span> / <span class="val" style="color:var(--call)">'+rises+'</span></div>'+
    '<div class="acc-row"><span class="lbl">Last Scan</span><span class="val">'+esc(shortDate(lastScan))+'</span></div>'+
    '<div class="acc-row"><span class="lbl">Enrichment Impact</span><span class="val">'+(fcRaw?.enrichment_total_impact!=null?fmt$(fcRaw.enrichment_total_impact):'--')+'</span></div>'+
    '<div class="acc-row"><span class="lbl">Raw vs Enriched</span><span class="val">'+(fcRaw?.raw_final_price?fmt$(fcRaw.raw_final_price)+' &rarr; '+fmt$(fcRaw.predicted_checkin_price):'--')+'</span></div>';
}

/* ── Options Table ──────────────────────────────────────────────── */
function renderTable(rows){
  const sortKey=el('opts-sort').value;
  const sorted=[...rows];
  if(sortKey==='trade')sorted.sort((a,b)=>(b.path_best_trade_pct||0)-(a.path_best_trade_pct||0));
  else if(sortKey==='signal')sorted.sort((a,b)=>{const o={CALL:0,PUT:1,NEUTRAL:2};return(o[a.option_signal]||3)-(o[b.option_signal]||3)});
  else if(sortKey==='disagree')sorted.sort((a,b)=>(b.source_disagreement?1:0)-(a.source_disagreement?1:0));
  else if(sortKey==='price')sorted.sort((a,b)=>(b.current_price||0)-(a.current_price||0));

  if(!sorted.length){el('opts-body').innerHTML='<tr><td colspan="12" class="empty">No options</td></tr>';return}

  // Count PUTs for bulk bar
  const puts=sorted.filter(r=>r.option_signal==='PUT'||r.option_signal==='STRONG_PUT');
  const disc=parseFloat(el('ovr-discount').value)||1;
  el('ovr-put-count').textContent='PUT signals: '+puts.length+' | Est. savings: $'+(puts.length*disc).toFixed(2);
  el('btn-bulk-ovr').disabled=puts.length===0;
  el('ovr-bar').style.display='flex';

  el('opts-body').innerHTML=sorted.map(r=>{
    const sig=r.option_signal||'--';
    const isPut=sig==='PUT'||sig==='STRONG_PUT';
    const pMin=r.path_min_price!=null?fmt$(r.path_min_price):'--';
    const pMax=r.path_max_price!=null?fmt$(r.path_max_price):'--';
    const trade=r.path_best_trade_pct||0;
    const cons=r.source_consensus||'--';
    const dis=r.source_disagreement;
    const isCall=sig==='CALL'||sig==='STRONG_CALL';
    const ovrId='ovr-'+r.detail_id;
    let ovrCell;
    if(isPut)ovrCell='<td id="'+ovrId+'"><button class="btn-ovr-sm" onclick="event.stopPropagation();queueOverride('+r.detail_id+','+r.current_price+')">&#11015; Override</button></td>';
    else if(isCall)ovrCell='<td id="'+ovrId+'"><button class="btn-ovr-sm" style="background:var(--call)" onclick="event.stopPropagation();queueOpportunity('+r.detail_id+','+r.current_price+')">&#11014; Buy</button></td>';
    else ovrCell='<td><span style="color:var(--muted);font-size:10px">--</span></td>';
    return '<tr data-id="'+r.detail_id+'" onclick="selectFromTable('+r.detail_id+')"'+
      (String(r.detail_id)===String(S.detailId)?' class="active"':'')+'>'+
      '<td>'+r.detail_id+'</td>'+
      '<td>'+esc(r.category||'')+'</td>'+
      '<td>'+esc(r.board||'')+'</td>'+
      '<td>'+shortDate(r.date_from)+'</td>'+
      '<td>'+r.days_to_checkin+'</td>'+
      '<td>'+fmt$(r.current_price)+'</td>'+
      '<td><span class="sig '+sigCls(sig)+'" style="font-size:10px;padding:1px 6px">'+sig+'</span></td>'+
      '<td style="font-size:11px">'+pMin+'&rarr;'+pMax+'</td>'+
      '<td style="color:'+(trade>5?'var(--call)':'var(--muted)')+'">'+fmtPct(trade)+'</td>'+
      '<td><span class="sig '+sigCls(cons)+'" style="font-size:10px;padding:1px 6px">'+cons+'</span></td>'+
      '<td>'+(dis?'<span style="color:var(--put);font-weight:700" title="Sources disagree">!!!</span>':'')+'</td>'+
      ovrCell+
    '</tr>';
  }).join('');

  loadQueueStatus();
}

/* ── Override Functions ─────────────────────────────────────────── */
function showToast(msg,ok){
  const t=document.createElement('div');t.className='toast '+(ok?'ok':'err');t.textContent=msg;
  document.body.appendChild(t);setTimeout(()=>t.remove(),5000);
}

async function queueOverride(detailId,currentPrice){
  const disc=parseFloat(el('ovr-discount').value)||1;
  const target=currentPrice-disc;
  if(disc<=0||disc>10){showToast('Discount must be $0.01-$10.00',false);return}
  if(target<50){showToast('Target price $'+target.toFixed(2)+' is below $50 minimum',false);return}
  const cell=document.getElementById('ovr-'+detailId);
  if(cell)cell.innerHTML='<span style="color:var(--pending);font-size:10px">sending...</span>';
  try{
    const r=await fetch(API+'/override/request',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({detail_id:detailId,discount_usd:disc})
    });
    const data=await r.json();
    if(r.ok){
      showToast('Queued #'+data.request_id+': '+fmt$(currentPrice)+' \u2192 '+fmt$(data.target_price),true);
      if(cell)cell.innerHTML='<span class="btn-ovr-sm queued" style="font-size:10px">\u{1F551} #'+data.request_id+'</span>';
    }else{
      showToast(data.detail||'Override failed',false);
      if(cell)cell.innerHTML='<button class="btn-ovr-sm" onclick="event.stopPropagation();queueOverride('+detailId+','+currentPrice+')">&#11015; Retry</button>';
    }
  }catch(e){
    showToast('Network error',false);
    if(cell)cell.innerHTML='<button class="btn-ovr-sm" onclick="event.stopPropagation();queueOverride('+detailId+','+currentPrice+')">&#11015; Retry</button>';
  }
}

async function queueOpportunity(detailId,currentPrice){
  const cell=document.getElementById('ovr-'+detailId);
  if(cell)cell.innerHTML='<span style="color:var(--call);font-size:10px">sending...</span>';
  try{
    const r=await fetch(API+'/opportunity/request',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({detail_id:detailId,max_rooms:1})
    });
    const data=await r.json();
    if(r.ok){
      showToast('Opp #'+data.request_id+': buy '+fmt$(data.buy_price)+' \u2192 push '+fmt$(data.push_price)+' profit +'+fmt$(data.profit_usd),true);
      if(cell)cell.innerHTML='<span class="btn-ovr-sm queued" style="background:var(--done);font-size:10px">\u2705 #'+data.request_id+'</span>';
    }else{
      showToast(data.detail||'Opportunity failed',false);
      if(cell)cell.innerHTML='<button class="btn-ovr-sm" style="background:var(--call)" onclick="event.stopPropagation();queueOpportunity('+detailId+','+currentPrice+')">&#11014; Retry</button>';
    }
  }catch(e){
    showToast('Network error',false);
    if(cell)cell.innerHTML='<button class="btn-ovr-sm" style="background:var(--call)" onclick="event.stopPropagation();queueOpportunity('+detailId+','+currentPrice+')">&#11014; Retry</button>';
  }
}

async function bulkOverride(){
  const disc=parseFloat(el('ovr-discount').value)||1;
  if(disc<=0||disc>10){showToast('Discount must be $0.01-$10.00',false);return}
  const puts=S.options.filter(r=>String(r.hotel_id)===String(S.hotelId)&&(r.option_signal==='PUT'||r.option_signal==='STRONG_PUT'));
  if(!puts.length){showToast('No PUT signals to override',false);return}
  if(!confirm('Queue '+puts.length+' overrides at -$'+disc.toFixed(2)+'?\nTotal impact: -$'+(puts.length*disc).toFixed(2)))return;
  el('btn-bulk-ovr').disabled=true;el('btn-bulk-ovr').textContent='Sending...';
  try{
    const r=await fetch(API+'/override/bulk',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({discount_usd:disc,hotel_id:parseInt(S.hotelId)})
    });
    const data=await r.json();
    if(r.ok){
      showToast('Queued batch '+data.batch_id+': '+data.count+' overrides at -$'+disc.toFixed(2),true);
      // Refresh table to show queued status
      const filtered=S.options.filter(r=>String(r.hotel_id)===String(S.hotelId));
      renderTable(filtered);
    }else{
      showToast(data.detail||'Bulk override failed',false);
    }
  }catch(e){showToast('Network error',false)}
  el('btn-bulk-ovr').disabled=false;el('btn-bulk-ovr').textContent='\u25B6 Queue All PUTs';
}

async function loadQueueStatus(){
  try{
    const r=await fetch(API+'/override/queue?limit=1');
    if(!r.ok)return;
    const data=await r.json();
    const s=data.stats||{};
    el('queue-status').innerHTML=
      '<span style="color:var(--pending)">'+(s.pending||0)+' pending</span> | '+
      '<span style="color:var(--done)">'+(s.done||0)+' done</span> | '+
      '<span style="color:var(--failed)">'+(s.failed||0)+' failed</span>';
  }catch(e){}
}

/* ── Auto-refresh ───────────────────────────────────────────────── */
function toggleRefresh(){
  if(el('chk-refresh').checked){
    S.refreshTimer=setInterval(()=>{if(S.detailId)loadTerminal(S.detailId)},180000);
  }else{
    clearInterval(S.refreshTimer);S.refreshTimer=null;
  }
}

/* ── Events ─────────────────────────────────────────────────────── */
el('sel-hotel').addEventListener('change',onHotelChange);
el('sel-option').addEventListener('change',onOptionChange);
el('chk-refresh').addEventListener('change',toggleRefresh);
el('opts-sort').addEventListener('change',()=>{
  if(S.hotelId){
    const filtered=S.options.filter(r=>String(r.hotel_id)===String(S.hotelId));
    renderTable(filtered);
  }
});
el('btn-bulk-ovr').addEventListener('click',bulkOverride);
el('ovr-discount').addEventListener('change',()=>{
  if(S.hotelId){
    const filtered=S.options.filter(r=>String(r.hotel_id)===String(S.hotelId));
    renderTable(filtered);
  }
});

init();
</script>
</body>
</html>"""
