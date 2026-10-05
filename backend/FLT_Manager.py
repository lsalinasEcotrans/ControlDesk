import os
import mysql.connector
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import httpx

router = APIRouter(prefix="/flt", tags=["FLT - Fleet Manager"])

GHOST_BASE = "https://ghost-main-static-b7ec98c880a54ad5a4782393902a32a2.ghostapi.app:29003/api/v1"
GHOST_BASE_V2 = "https://ghost-main-static-b7ec98c880a54ad5a4782393902a32a2.ghostapi.app:29003/api/ghost/v1"

# ─────────────────────────────────────────────
#  DB CONNECTION
# ─────────────────────────────────────────────
def get_db_connection():
    config = {
        "user":     os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASS"),
        "database": os.environ.get("DB_NAME"),
    }
    sock = os.environ.get("DB_SOCKET")
    if sock:
        config["unix_socket"] = sock
    else:
        config["host"] = os.environ.get("DB_HOST", "127.0.0.1")
        config["port"] = int(os.environ.get("DB_PORT", 3306))
    return mysql.connector.connect(**config)


# ─────────────────────────────────────────────
#  HTML CONSOLE
# ─────────────────────────────────────────────
HTML_CONSOLE = r"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>FLT Manager</title>
  <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg:      #0a0c10;
      --panel:   #0f1117;
      --panel2:  #13161f;
      --border:  #1e2433;
      --accent:  #00e5ff;
      --accent2: #7b61ff;
      --success: #00ff87;
      --danger:  #ff4d6d;
      --warn:    #ffd166;
      --text:    #c9d1e0;
      --muted:   #4a5568;
      --mono:    'Share Tech Mono', monospace;
      --sans:    'Syne', sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg); color: var(--text);
      font-family: var(--mono); min-height: 100vh;
      display: flex; flex-direction: column; align-items: center;
      padding: 40px 16px 80px;
      background-image:
        radial-gradient(ellipse 80% 40% at 50% -10%, rgba(0,229,255,.07) 0%, transparent 70%),
        repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(30,36,51,.4) 40px),
        repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(30,36,51,.4) 40px);
    }

    /* ── Header ── */
    .header { text-align:center; margin-bottom:40px; }
    .header .tag { font-size:11px; letter-spacing:4px; color:var(--accent); text-transform:uppercase; display:block; margin-bottom:8px; opacity:.7; }
    .header h1 { font-family:var(--sans); font-weight:800; font-size:clamp(28px,5vw,46px); color:#fff; letter-spacing:-1px; line-height:1; }
    .header h1 span { color:var(--accent); }
    .header .sub { font-size:13px; color:var(--muted); margin-top:10px; }

    /* ── Card ── */
    .card {
      width:100%; max-width:860px;
      background:var(--panel); border:1px solid var(--border);
      border-radius:12px; padding:32px; position:relative;
      box-shadow: 0 0 60px rgba(0,229,255,.04), 0 20px 60px rgba(0,0,0,.5);
    }
    .card::before {
      content:''; position:absolute; top:0; left:24px; right:24px; height:1px;
      background:linear-gradient(90deg,transparent,var(--accent),transparent); opacity:.5;
    }

    /* ── Login ── */
    .prompt-label {
      font-size:11px; letter-spacing:2px; text-transform:uppercase;
      color:var(--muted); margin-bottom:20px;
      display:flex; align-items:center; gap:8px;
    }
    .prompt-label::after { content:''; flex:1; height:1px; background:var(--border); }
    .input-group { margin-bottom:16px; }
    .input-group label {
      display:flex; align-items:center; gap:8px; font-size:11px;
      color:var(--muted); letter-spacing:1.5px; text-transform:uppercase; margin-bottom:8px;
    }
    .cursor { color:var(--accent); animation:blink 1s step-end infinite; }
    @keyframes blink { 50%{opacity:0} }
    input {
      width:100%; background:rgba(0,0,0,.4); border:1px solid var(--border);
      border-radius:6px; padding:12px 14px; color:#fff;
      font-family:var(--mono); font-size:14px; outline:none;
      transition:border-color .2s, box-shadow .2s;
    }
    input:focus { border-color:var(--accent); box-shadow:0 0 0 3px rgba(0,229,255,.08); }
    input::placeholder { color:var(--muted); }

    /* ── Buttons ── */
    .btn-login {
      width:100%; margin-top:8px; padding:13px;
      background:linear-gradient(135deg,var(--accent2),var(--accent));
      border:none; border-radius:6px; color:#000;
      font-family:var(--sans); font-weight:700; font-size:13px;
      letter-spacing:2px; text-transform:uppercase; cursor:pointer;
      transition:opacity .2s, transform .15s;
    }
    .btn-login:hover { opacity:.9; transform:translateY(-1px); }
    .btn-login:disabled { opacity:.4; cursor:not-allowed; transform:none; }

    .btn-logout {
      width:100%; margin-top:12px; padding:10px;
      background:transparent; border:1px solid rgba(255,77,109,.3);
      border-radius:6px; color:var(--danger); font-family:var(--mono);
      font-size:11px; letter-spacing:2px; text-transform:uppercase; cursor:pointer;
      transition:background .2s;
    }
    .btn-logout:hover { background:rgba(255,77,109,.08); }

    /* ── Status bar ── */
    .status-bar {
      display:flex; align-items:center; gap:8px;
      margin-top:16px; font-size:12px; color:var(--muted); min-height:18px;
    }
    .dot { width:7px; height:7px; border-radius:50%; background:var(--muted); flex-shrink:0; transition:background .3s; }
    .dot.ok   { background:var(--success); box-shadow:0 0 8px var(--success); }
    .dot.err  { background:var(--danger);  box-shadow:0 0 8px var(--danger);  }
    .dot.busy { background:var(--warn); animation:pulse 1s ease-in-out infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

    hr { border:none; border-top:1px solid var(--border); margin:28px 0; }

    /* ── Session token ── */
    .token-pill {
      background:rgba(0,229,255,.06); border:1px solid rgba(0,229,255,.2);
      border-radius:6px; padding:10px 50px 10px 14px;
      font-size:11px; word-break:break-all; color:var(--accent);
      margin-bottom:8px; position:relative;
    }
    .token-pill .copy-btn {
      position:absolute; top:8px; right:8px;
      background:rgba(0,229,255,.15); border:none; border-radius:4px;
      color:var(--accent); font-family:var(--mono); font-size:10px;
      padding:3px 8px; cursor:pointer; letter-spacing:1px;
    }
    .token-pill .copy-btn:hover { background:rgba(0,229,255,.28); }
    .session-note {
      font-size:11px; color:var(--muted); margin-bottom:24px;
      display:flex; align-items:center; gap:6px;
    }
    .session-note::before { content:'\26A0'; color:var(--warn); }

    /* ── Sync buttons grid ── */
    .section-title {
      font-family:var(--sans); font-weight:700; font-size:12px;
      letter-spacing:3px; text-transform:uppercase; color:var(--accent2); margin-bottom:16px;
    }
    .sync-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:28px; }

    .sync-card {
      background:var(--panel2); border:1px solid var(--border);
      border-radius:10px; padding:20px 16px; text-align:center;
      cursor:pointer; transition:border-color .2s, transform .15s, box-shadow .2s;
      position:relative; overflow:hidden;
    }
    .sync-card:hover { border-color:var(--accent2); transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,0,0,.4); }
    .sync-card:active { transform:translateY(0); }
    .sync-card.loading { pointer-events:none; }
    .sync-card .icon  { font-size:26px; margin-bottom:10px; display:block; }
    .sync-card .label {
      font-family:var(--sans); font-weight:700; font-size:13px;
      color:#fff; letter-spacing:1px; display:block; margin-bottom:4px;
    }
    .sync-card .sublabel { font-size:10px; color:var(--muted); letter-spacing:1px; }
    .sync-card .card-dot {
      position:absolute; top:10px; right:10px;
      width:6px; height:6px; border-radius:50%; background:var(--muted);
    }
    .sync-card .card-dot.ok   { background:var(--success); box-shadow:0 0 6px var(--success); }
    .sync-card .card-dot.err  { background:var(--danger);  box-shadow:0 0 6px var(--danger);  }
    .sync-card .card-dot.busy { background:var(--warn); animation:pulse 1s ease-in-out infinite; }

    /* ── Results panel ── */
    .result-panel {
      background:var(--panel2); border:1px solid var(--border);
      border-radius:10px; padding:20px; display:none;
    }
    .result-panel.visible { display:block; }
    .result-header {
      display:flex; align-items:center; justify-content:space-between;
      margin-bottom:16px;
    }
    .result-title { font-family:var(--sans); font-weight:700; font-size:13px; color:#fff; }
    .result-close {
      background:none; border:none; color:var(--muted);
      font-size:16px; cursor:pointer; line-height:1;
    }
    .result-close:hover { color:var(--danger); }

    .stats-row { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:16px; }
    .stat-card { background:rgba(0,0,0,.35); border:1px solid var(--border); border-radius:8px; padding:12px; text-align:center; }
    .stat-card .num { font-family:var(--sans); font-weight:800; font-size:24px; line-height:1; }
    .stat-card .lbl { font-size:10px; letter-spacing:2px; text-transform:uppercase; color:var(--muted); margin-top:4px; }
    .stat-card.total .num { color:#fff; }
    .stat-card.ins   .num { color:var(--success); }
    .stat-card.upd   .num { color:var(--warn); }

    .tbl-wrap { overflow-x:auto; border:1px solid var(--border); border-radius:8px; max-height:320px; overflow-y:auto; }
    table { width:100%; border-collapse:collapse; font-size:11px; }
    thead th {
      background:rgba(0,0,0,.6); color:var(--muted); font-size:10px;
      letter-spacing:2px; text-transform:uppercase;
      padding:9px 10px; text-align:left; position:sticky; top:0; z-index:1;
    }
    tbody tr { border-top:1px solid var(--border); transition:background .15s; }
    tbody tr:hover { background:rgba(255,255,255,.03); }
    tbody td { padding:8px 10px; vertical-align:middle; }

    .badge {
      display:inline-block; padding:2px 7px; border-radius:20px;
      font-size:10px; letter-spacing:1px; text-transform:uppercase; font-weight:bold;
    }
    .badge.insert { background:rgba(0,255,135,.12); color:var(--success); border:1px solid rgba(0,255,135,.25); }
    .badge.update { background:rgba(255,209,102,.12); color:var(--warn);   border:1px solid rgba(255,209,102,.25); }
    .badge.on  { background:rgba(0,229,255,.1);  color:var(--accent); border:1px solid rgba(0,229,255,.2); }
    .badge.off { background:rgba(255,255,255,.05); color:var(--muted); border:1px solid var(--border); }
    .color-swatch { display:inline-block; width:10px; height:10px; border-radius:2px; vertical-align:middle; margin-right:4px; border:1px solid rgba(255,255,255,.1); }

    .err-box { color:var(--danger); font-size:12px; margin-top:8px; }

    @media(max-width:580px) {
      .sync-grid { grid-template-columns:1fr; }
      .stats-row { grid-template-columns:repeat(3,1fr); }
    }
  </style>
</head>
<body>

<div class="header">
  <span class="tag">Internal &middot; Non-Production</span>
  <h1>FLT <span>Manager</span></h1>
  <p class="sub">Fleet Management Console &middot; Session-scoped auth</p>
</div>

<div class="card">

  <!-- ══ LOGIN ══ -->
  <div id="login-section">
    <div class="prompt-label">Autenticacion Ghost API</div>
    <div class="input-group">
      <label><span class="cursor">&#8250;</span> Usuario</label>
      <input id="username" type="text" placeholder="lsalinas" autocomplete="off"/>
    </div>
    <div class="input-group">
      <label><span class="cursor">&#8250;</span> Contrasena</label>
      <input id="password" type="password" placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"/>
    </div>
    <button class="btn-login" id="login-btn" onclick="doLogin()">Conectar &#8594;</button>
    <div class="status-bar">
      <div class="dot" id="login-dot"></div>
      <span id="login-msg">Esperando credenciales...</span>
    </div>
  </div>

  <!-- ══ DASHBOARD ══ -->
  <div id="dashboard" style="display:none">

    <div class="section-title">Sesion activa</div>
    <div class="token-pill">
      <button class="copy-btn" onclick="copyToken()">COPY</button>
      <span id="token-text"></span>
    </div>
    <p class="session-note">El token se borrara al cerrar esta pestana</p>

    <hr/>

    <div class="section-title">Sincronizacion de datos</div>

    <div class="sync-grid">
      <!-- Capabilities -->
      <div class="sync-card" id="card-cap" onclick="doSync('cap')">
        <div class="card-dot" id="dot-cap"></div>
        <span class="icon">&#9881;</span>
        <span class="label">Capabilities</span>
        <span class="sublabel">/api/v1/capabilities</span>
      </div>
      <!-- Drivers -->
      <div class="sync-card" id="card-drv" onclick="doSync('drv')">
        <div class="card-dot" id="dot-drv"></div>
        <span class="icon">&#128100;</span>
        <span class="label">Drivers</span>
        <span class="sublabel">/api/ghost/v1/drivers</span>
      </div>
      <!-- Vehicles -->
      <div class="sync-card" id="card-veh" onclick="doSync('veh')">
        <div class="card-dot" id="dot-veh"></div>
        <span class="icon">&#128663;</span>
        <span class="label">Vehicles</span>
        <span class="sublabel">/api/v1/vehicles</span>
      </div>
    </div>

    <!-- Result panel -->
    <div class="result-panel" id="result-panel">
      <div class="result-header">
        <span class="result-title" id="result-title">Resultado</span>
        <button class="result-close" onclick="closeResult()">&#10005;</button>
      </div>

      <div class="stats-row">
        <div class="stat-card total"><div class="num" id="r-total">0</div><div class="lbl">Total</div></div>
        <div class="stat-card ins">  <div class="num" id="r-insert">0</div><div class="lbl">Insertados</div></div>
        <div class="stat-card upd">  <div class="num" id="r-update">0</div><div class="lbl">Actualizados</div></div>
      </div>

      <div class="tbl-wrap">
        <table>
          <thead id="result-thead"><tr></tr></thead>
          <tbody id="result-tbody"></tbody>
        </table>
      </div>

      <div class="err-box" id="result-err" style="display:none"></div>

      <div class="status-bar">
        <div class="dot" id="result-dot"></div>
        <span id="result-msg">-</span>
      </div>
    </div>

    <button class="btn-logout" onclick="doLogout()">&#10005; Cerrar sesion</button>
  </div>

</div><!-- /card -->

<script>
// ── Dot helpers ──────────────────────────────
function setDot(id, state) {
  document.getElementById(id).className = 'dot ' + state;
}
function setCardDot(key, state) {
  const el = document.getElementById('dot-'+key);
  el.className = 'card-dot ' + state;
}
function setMsg(id, txt) { document.getElementById(id).textContent = txt; }

// ── Session restore ──────────────────────────
window.addEventListener('load', () => {
  const tok = sessionStorage.getItem('ghost_token');
  if (tok) showDashboard(tok);
});

// ── Login ────────────────────────────────────
async function doLogin() {
  const u = document.getElementById('username').value.trim();
  const p = document.getElementById('password').value;
  if (!u || !p) { setDot('login-dot','err'); setMsg('login-msg','Ingresa usuario y contrasena'); return; }

  document.getElementById('login-btn').disabled = true;
  setDot('login-dot','busy'); setMsg('login-msg','Autenticando...');

  try {
    const res  = await fetch('/flt/login', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username:u, password:p})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error de autenticacion');
    sessionStorage.setItem('ghost_token', data.secret);
    showDashboard(data.secret);
  } catch(e) {
    setDot('login-dot','err'); setMsg('login-msg', e.message);
    document.getElementById('login-btn').disabled = false;
  }
}
['username','password'].forEach(id =>
  document.getElementById(id).addEventListener('keydown', e => { if(e.key==='Enter') doLogin(); })
);

function showDashboard(token) {
  document.getElementById('login-section').style.display = 'none';
  document.getElementById('dashboard').style.display = 'block';
  document.getElementById('token-text').textContent = token;
}
function copyToken() {
  navigator.clipboard.writeText(sessionStorage.getItem('ghost_token')||'').catch(()=>{});
}
function doLogout() { sessionStorage.removeItem('ghost_token'); location.reload(); }

// ── Sync dispatcher ──────────────────────────
const SYNC_META = {
  cap: {
    label: 'Capabilities',
    cols:  ['ID','Codigo','Nombre','Req.','Prior.','Activo','Accion'],
    row:   r => [r.id, r.short_code, r.name, r.requirement,
                 r.priority!==null?r.priority:'-',
                 badge(r.enabled?'on':'off', r.enabled?'ON':'OFF'),
                 badge(r.action, r.action.toUpperCase())]
  },
  drv: {
    label: 'Drivers',
    cols:  ['ID','Callsign','Nombre','Mobile','Email','Activo','Accion'],
    row:   r => [r.id, r.callsign||'-', r.full_name, r.mobile||'-', r.email||'-',
                 badge(r.active?'on':'off', r.active?'ON':'OFF'),
                 badge(r.action, r.action.toUpperCase())]
  },
  veh: {
    label: 'Vehicles',
    cols:  ['ID','Callsign','Patente','Marca/Modelo','Tipo','Activo','Accion'],
    row:   r => [r.id, r.callsign||'-', r.plate_number,
                 (r.make||'')+' '+(r.model||''), r.vehicle_type||'-',
                 badge(r.is_active?'on':'off', r.is_active?'ON':'OFF'),
                 badge(r.action, r.action.toUpperCase())]
  }
};

function badge(cls, txt) {
  return '<span class="badge '+cls+'">'+txt+'</span>';
}

async function doSync(key) {
  const tok = sessionStorage.getItem('ghost_token');
  if (!tok) return;

  const card = document.getElementById('card-'+key);
  card.classList.add('loading');
  setCardDot(key,'busy');
  closeResult();

  try {
    const res  = await fetch('/flt/sync/'+key, {
      headers:{'Authentication-Token':tok}
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error en sincronizacion');

    setCardDot(key,'ok');
    showResult(key, data);
  } catch(e) {
    setCardDot(key,'err');
    showError(key, e.message);
  } finally {
    card.classList.remove('loading');
  }
}

function showResult(key, data) {
  const meta = SYNC_META[key];
  document.getElementById('result-title').textContent = meta.label + ' — Resultado';
  document.getElementById('r-total').textContent  = data.total;
  document.getElementById('r-insert').textContent = data.inserted;
  document.getElementById('r-update').textContent = data.updated;

  // Header
  const thead = document.getElementById('result-thead');
  thead.innerHTML = '<tr>'+meta.cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>';

  // Rows
  const tbody = document.getElementById('result-tbody');
  tbody.innerHTML = '';
  data.records.forEach(r => {
    const cells = meta.row(r);
    const tr = document.createElement('tr');
    tr.innerHTML = cells.map(c=>'<td>'+c+'</td>').join('');
    tbody.appendChild(tr);
  });

  document.getElementById('result-err').style.display = 'none';
  setDot('result-dot','ok');
  setMsg('result-msg', data.inserted+' insertados, '+data.updated+' actualizados');

  const panel = document.getElementById('result-panel');
  panel.classList.add('visible');
  panel.scrollIntoView({behavior:'smooth', block:'nearest'});
}

function showError(key, msg) {
  const meta = SYNC_META[key];
  document.getElementById('result-title').textContent = meta.label + ' — Error';
  document.getElementById('r-total').textContent  = 0;
  document.getElementById('r-insert').textContent = 0;
  document.getElementById('r-update').textContent = 0;
  document.getElementById('result-thead').innerHTML = '';
  document.getElementById('result-tbody').innerHTML = '';
  const err = document.getElementById('result-err');
  err.textContent = 'Error: ' + msg;
  err.style.display = 'block';
  setDot('result-dot','err'); setMsg('result-msg', msg);
  document.getElementById('result-panel').classList.add('visible');
}

function closeResult() {
  document.getElementById('result-panel').classList.remove('visible');
}
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────
#  ENDPOINT: Consola HTML
# ─────────────────────────────────────────────
@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def flt_console():
    return HTMLResponse(content=HTML_CONSOLE)


# ─────────────────────────────────────────────
#  ENDPOINT: Login proxy
# ─────────────────────────────────────────────
@router.post("/login")
async def flt_login(request: Request):
    body = await request.json()
    username = body.get("username")
    password = body.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Faltan username o password")

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        try:
            resp = await client.post(
                f"{GHOST_BASE}/authenticate",
                json={"username": username, "password": password},
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"No se pudo conectar a Ghost API: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text or "Error en autenticacion")

    return JSONResponse(content=resp.json())


# ─────────────────────────────────────────────
#  HELPER: obtener IDs existentes
# ─────────────────────────────────────────────
def get_existing_ids(cursor, table: str) -> set:
    cursor.execute(f"SELECT id FROM {table}")
    return {row["id"] for row in cursor.fetchall()}


# ─────────────────────────────────────────────
#  SYNC: CAPABILITIES
# ─────────────────────────────────────────────
@router.get("/sync/cap")
async def sync_capabilities(request: Request):
    token = _extract_token(request)

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await _ghost_get(client, f"{GHOST_BASE}/capabilities", token)

    capabilities = resp.json()
    inserted, updated, records = 0, 0, []

    conn, cursor = _open_db()
    try:
        existing = get_existing_ids(cursor, "FLT_CAPABILITIES")

        sql = """
            INSERT INTO FLT_CAPABILITIES
                (id, short_code, name, requirement, priority,
                 enabled, exclude_from_broadcast, exclusive_capability, operator_override)
            VALUES
                (%(id)s, %(short_code)s, %(name)s, %(requirement)s, %(priority)s,
                 %(enabled)s, %(exclude_from_broadcast)s, %(exclusive_capability)s, %(operator_override)s)
            ON DUPLICATE KEY UPDATE
                short_code             = VALUES(short_code),
                name                   = VALUES(name),
                requirement            = VALUES(requirement),
                priority               = VALUES(priority),
                enabled                = VALUES(enabled),
                exclude_from_broadcast = VALUES(exclude_from_broadcast),
                exclusive_capability   = VALUES(exclusive_capability),
                operator_override      = VALUES(operator_override)
        """

        for cap in capabilities:
            row = {
                "id":                    cap["id"],
                "short_code":            cap.get("shortCode"),
                "name":                  cap.get("name"),
                "requirement":           cap.get("requirement"),
                "priority":              cap.get("priority"),
                "enabled":               int(bool(cap.get("enabled", False))),
                "exclude_from_broadcast": int(bool(cap.get("excludeFromBroadcast", False))),
                "exclusive_capability":  int(bool(cap.get("exclusiveCapability", False))),
                "operator_override":     int(bool(cap.get("operatorOverride", False))),
            }
            action = "update" if cap["id"] in existing else "insert"
            cursor.execute(sql, row)
            inserted += action == "insert"
            updated  += action == "update"
            records.append({**row, "colour": cap.get("colour"), "action": action})

        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        _close_db(cursor, conn)

    return JSONResponse({"total": len(records), "inserted": inserted, "updated": updated, "records": records})


# ─────────────────────────────────────────────
#  SYNC: DRIVERS  (+ addresses)
# ─────────────────────────────────────────────
@router.get("/sync/drv")
async def sync_drivers(request: Request):
    token = _extract_token(request)

    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        resp = await _ghost_get(client, f"{GHOST_BASE_V2}/drivers", token)

    drivers = resp.json()
    # La API puede devolver lista directa o wrapper
    if isinstance(drivers, dict):
        drivers = drivers.get("data", drivers.get("drivers", []))

    inserted, updated, records = 0, 0, []

    conn, cursor = _open_db()
    try:
        existing = get_existing_ids(cursor, "FLT_DRIVERS")

        sql_driver = """
            INSERT INTO FLT_DRIVERS
                (id, company_id, callsign, forename, surname, full_name,
                 mobile, email, badge_number,
                 driver_licence_number, driver_licence_expiry,
                 start_date, finish_date,
                 suspended, active, row_version)
            VALUES
                (%(id)s, %(company_id)s, %(callsign)s, %(forename)s, %(surname)s, %(full_name)s,
                 %(mobile)s, %(email)s, %(badge_number)s,
                 %(driver_licence_number)s, %(driver_licence_expiry)s,
                 %(start_date)s, %(finish_date)s,
                 %(suspended)s, %(active)s, %(row_version)s)
            ON DUPLICATE KEY UPDATE
                company_id             = VALUES(company_id),
                callsign               = VALUES(callsign),
                forename               = VALUES(forename),
                surname                = VALUES(surname),
                full_name              = VALUES(full_name),
                mobile                 = VALUES(mobile),
                email                  = VALUES(email),
                badge_number           = VALUES(badge_number),
                driver_licence_number  = VALUES(driver_licence_number),
                driver_licence_expiry  = VALUES(driver_licence_expiry),
                start_date             = VALUES(start_date),
                finish_date            = VALUES(finish_date),
                suspended              = VALUES(suspended),
                active                 = VALUES(active),
                row_version            = VALUES(row_version)
        """

        sql_addr = """
            INSERT INTO FLT_DRIVER_ADDRESSES
                (driver_id, address_line1, address_line2, town, region, postcode, summary)
            VALUES
                (%(driver_id)s, %(address_line1)s, %(address_line2)s,
                 %(town)s, %(region)s, %(postcode)s, %(summary)s)
            ON DUPLICATE KEY UPDATE
                address_line1 = VALUES(address_line1),
                address_line2 = VALUES(address_line2),
                town          = VALUES(town),
                region        = VALUES(region),
                postcode      = VALUES(postcode),
                summary       = VALUES(summary)
        """

        for d in drivers:
            did = d["id"]
            row = {
                "id":                   did,
                "company_id":           d.get("companyId"),
                "callsign":             d.get("callsign"),
                "forename":             d.get("forename"),
                "surname":              d.get("surname"),
                "full_name":            d.get("fullName"),
                "mobile":               d.get("mobile"),
                "email":                d.get("email"),
                "badge_number":         d.get("badgeNumber"),
                "driver_licence_number": d.get("driverLicenceNumber"),
                "driver_licence_expiry": _parse_dt(d.get("driverLicenceExpiryDate")),
                "start_date":           _parse_dt(d.get("startDate")),
                "finish_date":          _parse_dt(d.get("finishDate")),
                "suspended":            int(bool(d.get("suspended", False))),
                "active":               int(bool(d.get("active", True))),
                "row_version":          d.get("rowVersion"),
            }
            action = "update" if did in existing else "insert"
            cursor.execute(sql_driver, row)

            # Address
            postal = d.get("postalAddress") or {}
            if postal:
                cursor.execute(sql_addr, {
                    "driver_id":    did,
                    "address_line1": postal.get("addressLine1"),
                    "address_line2": postal.get("addressLine2"),
                    "town":         postal.get("town"),
                    "region":       postal.get("region"),
                    "postcode":     postal.get("postcode"),
                    "summary":      postal.get("summaryText"),
                })

            inserted += action == "insert"
            updated  += action == "update"
            records.append({**row, "action": action})

        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        _close_db(cursor, conn)

    return JSONResponse({"total": len(records), "inserted": inserted, "updated": updated, "records": records})


# ─────────────────────────────────────────────
#  SYNC: VEHICLES  (+ vehicle_capabilities)
# ─────────────────────────────────────────────
@router.get("/sync/veh")
async def sync_vehicles(request: Request):
    token = _extract_token(request)

    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        resp = await _ghost_get(client, f"{GHOST_BASE}/vehicles", token)

    vehicles = resp.json()
    if isinstance(vehicles, dict):
        vehicles = vehicles.get("data", vehicles.get("vehicles", []))

    inserted, updated, records = 0, 0, []

    conn, cursor = _open_db()
    try:
        # Deshabilitar FK checks temporalmente: permite insertar vehiculos
        # cuyo owner_driver_id aun no exista en FLT_DRIVERS.
        # Se rehabilitan siempre en el bloque finally.
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        existing = get_existing_ids(cursor, "FLT_VEHICLES")

        sql_veh = """
            INSERT INTO FLT_VEHICLES
                (id, company_id, callsign, plate_number, make, model, colour,
                 year_of_manufacture, vehicle_type, size, mileage,
                 plate_expiry_date, insurance_expiry_date, mot_expiry_date, road_tax_expiry_date,
                 owner_driver_id, terminal_id, terminal_type, is_active, row_version)
            VALUES
                (%(id)s, %(company_id)s, %(callsign)s, %(plate_number)s,
                 %(make)s, %(model)s, %(colour)s,
                 %(year_of_manufacture)s, %(vehicle_type)s, %(size)s, %(mileage)s,
                 %(plate_expiry_date)s, %(insurance_expiry_date)s,
                 %(mot_expiry_date)s, %(road_tax_expiry_date)s,
                 %(owner_driver_id)s, %(terminal_id)s, %(terminal_type)s,
                 %(is_active)s, %(row_version)s)
            ON DUPLICATE KEY UPDATE
                company_id            = VALUES(company_id),
                callsign              = VALUES(callsign),
                plate_number          = VALUES(plate_number),
                make                  = VALUES(make),
                model                 = VALUES(model),
                colour                = VALUES(colour),
                year_of_manufacture   = VALUES(year_of_manufacture),
                vehicle_type          = VALUES(vehicle_type),
                size                  = VALUES(size),
                mileage               = VALUES(mileage),
                plate_expiry_date     = VALUES(plate_expiry_date),
                insurance_expiry_date = VALUES(insurance_expiry_date),
                mot_expiry_date       = VALUES(mot_expiry_date),
                road_tax_expiry_date  = VALUES(road_tax_expiry_date),
                owner_driver_id       = VALUES(owner_driver_id),
                terminal_id           = VALUES(terminal_id),
                terminal_type         = VALUES(terminal_type),
                is_active             = VALUES(is_active),
                row_version           = VALUES(row_version)
        """

        for v in vehicles:
            vid = v["id"]
            row = {
                "id":                   vid,
                "company_id":           v.get("companyId"),
                "callsign":             v.get("callsign"),
                "plate_number":         v.get("plateNumber") or v.get("registration"),
                "make":                 v.get("make"),
                "model":                v.get("model"),
                "colour":               v.get("colour"),
                "year_of_manufacture":  v.get("yearOfManufacture"),
                "vehicle_type":         v.get("vehicleType"),
                "size":                 v.get("size"),
                "mileage":              v.get("mileage"),
                "plate_expiry_date":    _parse_dt(v.get("plateExpiryDate")),
                "insurance_expiry_date": _parse_dt(v.get("insuranceExpiryDate")),
                "mot_expiry_date":      _parse_dt(v.get("motExpiryDate")),
                "road_tax_expiry_date": _parse_dt(v.get("roadTaxExpiryDate")),
                "owner_driver_id":      v.get("ownerDriverId"),
                "terminal_id":          v.get("terminalId"),
                "terminal_type":        v.get("terminalType"),
                "is_active":            int(bool(v.get("isActive", False))),
                "row_version":          v.get("rowVersion"),
            }
            action = "update" if vid in existing else "insert"
            cursor.execute(sql_veh, row)

            # Vehicle capabilities: borrar las viejas e insertar las nuevas
            caps = v.get("capabilities") or []
            if caps:
                cursor.execute("DELETE FROM FLT_VEHICLE_CAPABILITIES WHERE vehicle_id = %s", (vid,))
                for cap_id in caps:
                    # Solo insertar si la capability existe en la tabla maestra
                    cursor.execute(
                        "INSERT IGNORE INTO FLT_VEHICLE_CAPABILITIES (vehicle_id, capability_id) VALUES (%s, %s)",
                        (vid, cap_id)
                    )

            inserted += action == "insert"
            updated  += action == "update"
            records.append({**row, "action": action})

        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        try: cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        except Exception: pass
        _close_db(cursor, conn)

    return JSONResponse({"total": len(records), "inserted": inserted, "updated": updated, "records": records})


# ─────────────────────────────────────────────
#  HELPERS INTERNOS
# ─────────────────────────────────────────────
def _extract_token(request: Request) -> str:
    token = request.headers.get("Authentication-Token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    return token


async def _ghost_get(client: httpx.AsyncClient, url: str, token: str):
    try:
        resp = await client.get(url, headers={"Authentication-Token": token})
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar a Ghost API: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text or "Error Ghost API")
    return resp


def _open_db():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    return conn, cursor


def _close_db(cursor, conn):
    try: cursor.close()
    except Exception: pass
    try: conn.close()
    except Exception: pass


def _parse_dt(value):
    """Convierte ISO datetime string a formato MySQL, o None si es nulo."""
    if not value:
        return None
    try:
        # Quitar timezone offset para MySQL DATETIME
        clean = value[:19].replace("T", " ")
        return clean
    except Exception:
        return None