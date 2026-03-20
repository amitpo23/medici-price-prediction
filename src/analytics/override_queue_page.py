"""Override Queue dashboard — queue management with stats, filters, auto-refresh."""
from __future__ import annotations


def generate_override_queue_html() -> str:
    """Return self-contained HTML for the Override Queue dashboard."""
    return _OVERRIDE_QUEUE_HTML


_OVERRIDE_QUEUE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Override Queue — Medici</title>
<style>
:root{
  --bg:#1a1a2e;--surface:#16213e;--panel:#0f3460;
  --border:#1f4068;--text:#eee;--muted:#8899aa;
  --pending:#ffc107;--picked:#2196f3;--done:#4caf50;--failed:#f44336;
  --override:#ff9800;--accent:#42a5f5;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px}
.page{max-width:1400px;margin:0 auto;padding:16px}
h1{font-size:20px;margin-bottom:4px}
.sub{color:var(--muted);font-size:12px;margin-bottom:16px}
a{color:var(--accent);text-decoration:none}

/* Stats cards */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:16px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center}
.stat .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:4px}
.stat .val{font-size:22px;font-weight:700}
.stat .val.pending{color:var(--pending)}.stat .val.picked{color:var(--picked)}
.stat .val.done{color:var(--done)}.stat .val.failed{color:var(--failed)}
.stat .val.rate{color:var(--done)}

/* Filter bar */
.filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.filters button{background:var(--surface);color:var(--muted);border:1px solid var(--border);border-radius:4px;padding:5px 12px;font-size:12px;cursor:pointer}
.filters button:hover{color:var(--text);border-color:var(--accent)}
.filters button.active{background:var(--accent);color:#fff;border-color:var(--accent)}

/* Queue table */
.q-scroll{max-height:480px;overflow:auto;border:1px solid var(--border);border-radius:8px;margin-bottom:16px}
.q-table{width:100%;border-collapse:collapse;font-size:12px;background:var(--surface)}
.q-table th{background:var(--panel);padding:6px 8px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);position:sticky;top:0;border-bottom:2px solid var(--border)}
.q-table td{padding:5px 8px;border-bottom:1px solid rgba(255,255,255,.04);font-family:monospace}
.q-table tr:hover{background:rgba(255,255,255,.04)}

/* Status badges */
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:600;letter-spacing:.3px}
.badge.pending{background:rgba(255,193,7,.2);color:var(--pending)}
.badge.picked{background:rgba(33,150,243,.2);color:var(--picked)}
.badge.done{background:rgba(76,175,80,.2);color:var(--done)}
.badge.failed{background:rgba(244,67,54,.2);color:var(--failed)}

/* Hotel breakdown */
.breakdown{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px}
.breakdown h3{font-size:13px;color:var(--muted);margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}
.bk-row{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid rgba(255,255,255,.04)}
.bk-row:last-child{border:none}
.bk-name{flex:1}.bk-stat{font-family:monospace;margin-left:12px}

/* Pager */
.pager{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.pager button{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:5px 12px;font-size:12px;cursor:pointer}
.pager button:disabled{opacity:.4;cursor:default}

.loading{text-align:center;padding:40px;color:var(--muted)}
.spin{display:inline-block;width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="page">
<h1>Override Queue</h1>
<p class="sub">Price override requests &mdash; pending, in-progress, completed.
  <a href="/api/v1/salesoffice/dashboard/terminal">&larr; Terminal</a> |
  <a href="/api/v1/salesoffice/home">Home</a></p>

<!-- Stats -->
<div class="stats">
  <div class="stat"><div class="lbl">Pending</div><div class="val pending" id="st-pending">--</div></div>
  <div class="stat"><div class="lbl">Picked</div><div class="val picked" id="st-picked">--</div></div>
  <div class="stat"><div class="lbl">Done</div><div class="val done" id="st-done">--</div></div>
  <div class="stat"><div class="lbl">Failed</div><div class="val failed" id="st-failed">--</div></div>
  <div class="stat"><div class="lbl">Total</div><div class="val" id="st-total">--</div></div>
  <div class="stat"><div class="lbl">Success Rate</div><div class="val rate" id="st-rate">--</div></div>
  <div class="stat"><div class="lbl">Avg Discount</div><div class="val" id="st-avg">--</div></div>
  <div class="stat"><div class="lbl">Volume</div><div class="val" id="st-vol">--</div></div>
</div>

<!-- Filters -->
<div class="filters">
  <button class="active" data-f="">All</button>
  <button data-f="pending">Pending</button>
  <button data-f="picked">Picked</button>
  <button data-f="done">Done</button>
  <button data-f="failed">Failed</button>
</div>

<!-- Queue table -->
<div class="q-scroll">
  <table class="q-table">
    <thead><tr>
      <th>#</th><th>Detail</th><th>Hotel</th><th>Category</th>
      <th>Price</th><th>Discount</th><th>Target</th><th>Signal</th>
      <th>Status</th><th>Created</th><th>Completed</th><th>Error</th>
    </tr></thead>
    <tbody id="q-body"><tr><td colspan="12" class="loading"><div class="spin"></div></td></tr></tbody>
  </table>
</div>

<!-- Pager -->
<div class="pager">
  <span id="pager-info" style="font-size:12px;color:var(--muted)">--</span>
  <div>
    <button id="btn-prev" disabled>&larr; Prev</button>
    <button id="btn-next" disabled>Next &rarr;</button>
  </div>
</div>

<!-- Hotel breakdown -->
<div class="breakdown" id="breakdown">
  <h3>Hotel Breakdown (30 days)</h3>
  <div id="bk-body" class="loading"><div class="spin"></div></div>
</div>
</div>

<script>
const API='/api/v1/salesoffice';
const S={filter:'',offset:0,limit:50,total:0};

function esc(v){const d=document.createElement('div');d.textContent=v;return d.innerHTML}
function fmt$(v){return '$'+Number(v).toFixed(2)}
function shortDt(d){if(!d)return'';return d.replace('T',' ').substring(0,16)}

/* ── Load queue ─────────────────────────────────── */
async function loadQueue(){
  const params=new URLSearchParams({limit:String(S.limit),offset:String(S.offset)});
  if(S.filter)params.set('status',S.filter);
  try{
    const r=await fetch(API+'/override/queue?'+params);
    if(!r.ok)return;
    const data=await r.json();
    S.total=data.total||0;
    renderTable(data.requests||[]);
    renderStats(data.stats||{});
    document.getElementById('pager-info').textContent=
      'Showing '+(S.offset+1)+'-'+Math.min(S.offset+S.limit,S.total)+' of '+S.total;
    document.getElementById('btn-prev').disabled=S.offset===0;
    document.getElementById('btn-next').disabled=S.offset+S.limit>=S.total;
  }catch(e){}
}

function renderTable(rows){
  const body=document.getElementById('q-body');
  if(!rows.length){body.innerHTML='<tr><td colspan="12" style="text-align:center;color:var(--muted);padding:30px">No overrides found</td></tr>';return}
  body.innerHTML=rows.map(r=>'<tr>'+
    '<td>'+r.id+'</td>'+
    '<td>'+r.detail_id+'</td>'+
    '<td>'+esc(r.hotel_name||'')+'</td>'+
    '<td>'+esc(r.category||'')+'</td>'+
    '<td>'+fmt$(r.current_price)+'</td>'+
    '<td style="color:var(--override)">-'+fmt$(r.discount_usd)+'</td>'+
    '<td style="font-weight:600">'+fmt$(r.target_price)+'</td>'+
    '<td><span class="badge '+(r.signal==='PUT'||r.signal==='STRONG_PUT'?'failed':'')+'">'+esc(r.signal||'')+'</span></td>'+
    '<td><span class="badge '+esc(r.status)+'">'+statusIcon(r.status)+' '+esc(r.status)+'</span></td>'+
    '<td>'+shortDt(r.created_at)+'</td>'+
    '<td>'+shortDt(r.completed_at)+'</td>'+
    '<td style="color:var(--failed);font-size:11px;max-width:120px;overflow:hidden;text-overflow:ellipsis" title="'+esc(r.error_message||'')+'">'+esc(r.error_message||'')+'</td>'+
  '</tr>').join('');
}

function statusIcon(s){return s==='pending'?'\u{1F551}':s==='picked'?'\u{1F504}':s==='done'?'\u2705':s==='failed'?'\u274C':''}

function renderStats(stats){
  document.getElementById('st-pending').textContent=stats.pending??'--';
  document.getElementById('st-picked').textContent=stats.picked??'--';
  document.getElementById('st-done').textContent=stats.done??'--';
  document.getElementById('st-failed').textContent=stats.failed??'--';
  document.getElementById('st-total').textContent=stats.total??'--';
  const total=(stats.done||0)+(stats.failed||0);
  document.getElementById('st-rate').textContent=total>0?((stats.done||0)/total*100).toFixed(0)+'%':'--';
  document.getElementById('st-avg').textContent=stats.avg_discount?fmt$(stats.avg_discount):'--';
  document.getElementById('st-vol').textContent=stats.total_volume?fmt$(stats.total_volume):'--';
}

/* ── Load history / breakdown ────────────────────── */
async function loadHistory(){
  try{
    const r=await fetch(API+'/override/history?days=30');
    if(!r.ok)return;
    const data=await r.json();
    const hotels=data.by_hotel||[];
    const bk=document.getElementById('bk-body');
    if(!hotels.length){bk.innerHTML='<span style="color:var(--muted)">No history yet</span>';return}
    bk.innerHTML=hotels.map(h=>'<div class="bk-row">'+
      '<span class="bk-name">'+esc(h.hotel_name||'Hotel '+h.hotel_id)+' ('+h.hotel_id+')</span>'+
      '<span class="bk-stat">'+h.total+' total</span>'+
      '<span class="bk-stat" style="color:var(--done)">'+h.done+' done</span>'+
      '<span class="bk-stat" style="color:var(--failed)">'+(h.failed||0)+' failed</span>'+
      '<span class="bk-stat">'+(h.total>0?((h.done/h.total)*100).toFixed(0)+'%':'--')+'</span>'+
    '</div>').join('');
    // Update stats from history if queue stats didn't have volume
    if(data.total_overrides!=null){
      document.getElementById('st-avg').textContent=data.avg_discount?fmt$(data.avg_discount):'--';
      document.getElementById('st-vol').textContent=data.total_volume?fmt$(data.total_volume):'--';
    }
  }catch(e){}
}

/* ── Filter buttons ──────────────────────────────── */
document.querySelectorAll('.filters button').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.filters button').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    S.filter=btn.dataset.f;S.offset=0;loadQueue();
  });
});

document.getElementById('btn-prev').addEventListener('click',()=>{S.offset=Math.max(0,S.offset-S.limit);loadQueue()});
document.getElementById('btn-next').addEventListener('click',()=>{S.offset+=S.limit;loadQueue()});

/* ── Auto-refresh ────────────────────────────────── */
setInterval(loadQueue,30000);

/* ── Init ────────────────────────────────────────── */
loadQueue();
loadHistory();
</script>
</body>
</html>"""
