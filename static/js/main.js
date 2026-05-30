// FairBet Lab — Core JS
let accessToken  = localStorage.getItem('fb_access');
let refreshToken = localStorage.getItem('fb_refresh');
let betslip      = JSON.parse(localStorage.getItem('fb_betslip') || '[]');

// ── API ────────────────────────────────────────────────────────────────────────
async function apiFetch(url, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  let res = await fetch(url, { ...opts, headers });

  if (res.status === 401 && refreshToken) {
    const r = await fetch('/api/usuarios/login/refresh/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken })
    });
    if (r.ok) {
      const d = await r.json();
      accessToken = d.access;
      localStorage.setItem('fb_access', accessToken);
      headers['Authorization'] = `Bearer ${accessToken}`;
      res = await fetch(url, { ...opts, headers });
    } else { logout(); return null; }
  }
  return res;
}

function isLoggedIn() { return !!accessToken; }

function logout() {
  localStorage.removeItem('fb_access');
  localStorage.removeItem('fb_refresh');
  localStorage.removeItem('fb_user');
  localStorage.removeItem('fb_betslip');
  betslip = [];
  window.location.href = '/login/';
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const wrap = document.getElementById('toast-wrap');
  if (!wrap) return;
  const icons = { success: 'fa-circle-check', error: 'fa-circle-xmark', info: 'fa-circle-info' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${msg}</span>`;
  wrap.appendChild(t);
  setTimeout(() => { t.style.transition = '.3s'; t.style.opacity = '0'; t.style.transform = 'translateX(30px)'; setTimeout(() => t.remove(), 320); }, 3000);
}

// ── Betslip ────────────────────────────────────────────────────────────────────
function saveBetslip() { localStorage.setItem('fb_betslip', JSON.stringify(betslip)); }

function addToBetslip(cuotaId, seleccion, odds, evento, mercado) {
  const idx = betslip.findIndex(b => b.cuotaId === cuotaId);
  if (idx !== -1) {
    betslip.splice(idx, 1);
    document.querySelectorAll(`[data-cuota="${cuotaId}"]`).forEach(el => el.classList.remove('selected'));
  } else {
    betslip.push({ cuotaId, seleccion, odds: parseFloat(odds), evento, mercado });
    document.querySelectorAll(`[data-cuota="${cuotaId}"]`).forEach(el => el.classList.add('selected'));
    toast(`${seleccion} agregado al ticket`, 'info');
  }
  saveBetslip();
  renderBetslip();
}

function removeFromBetslip(cuotaId) {
  betslip = betslip.filter(b => b.cuotaId !== cuotaId);
  document.querySelectorAll(`[data-cuota="${cuotaId}"]`).forEach(el => el.classList.remove('selected'));
  saveBetslip();
  renderBetslip();
}

function renderBetslip() {
  const body   = document.getElementById('bs-body');
  const foot   = document.getElementById('bs-foot');
  const countEl = document.getElementById('bs-count');

  if (countEl) countEl.textContent = betslip.length || '';
  if (!body) return;

  if (!betslip.length) {
    body.innerHTML = `
      <div class="betslip-empty">
        <i class="fa-solid fa-ticket"></i>
        <p>Selecciona una cuota para<br/>agregar al ticket</p>
      </div>`;
    if (foot) foot.style.display = 'none';
    return;
  }

  body.innerHTML = betslip.map(b => `
    <div class="bs-item">
      <button class="bs-remove" onclick="removeFromBetslip(${b.cuotaId})">
        <i class="fa-solid fa-xmark"></i>
      </button>
      <div class="bs-evento">${b.evento}</div>
      <div class="bs-seleccion">${b.seleccion}</div>
      <div class="bs-odds">@ ${b.odds.toFixed(2)}</div>
    </div>`).join('');

  if (foot) foot.style.display = 'block';
  calcBetslip();
}

function calcBetslip() {
  const mi = document.getElementById('bs-monto');
  const gi = document.getElementById('bs-ganancia');
  const ti = document.getElementById('bs-odds-total');
  if (!mi) return;
  const monto = parseFloat(mi.value) || 0;
  const totalOdds = betslip.reduce((acc, b) => acc * b.odds, 1);
  if (ti) ti.textContent = totalOdds.toFixed(2);
  if (gi) gi.textContent = `S/ ${(monto * totalOdds).toFixed(2)}`;
}

async function confirmarApuesta() {
  if (!isLoggedIn()) { window.location.href = '/login/'; return; }
  if (!betslip.length) { toast('Agrega al menos una seleccion al ticket', 'error'); return; }
  const monto = parseFloat(document.getElementById('bs-monto')?.value || 0);
  if (monto <= 0) { toast('Ingresa un monto valido', 'error'); return; }

  const btn = document.getElementById('btn-apostar');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Procesando...'; }

  try {
    let res, data;
    if (betslip.length === 1) {
      res = await apiFetch('/api/apuestas/', {
        method: 'POST',
        body: JSON.stringify({ cuota_id: betslip[0].cuotaId, monto: monto.toFixed(4), clave_idempotencia: crypto.randomUUID() })
      });
      data = await res.json();
    } else {
      res = await apiFetch('/api/apuestas/combinada/', {
        method: 'POST',
        body: JSON.stringify({ cuota_ids: betslip.map(b => b.cuotaId), monto: monto.toFixed(4), clave_idempotencia: crypto.randomUUID() })
      });
      data = await res.json();
    }

    if (res?.ok) {
      const pago = data.apuesta?.pago_potencial || data.combinada?.pago_potencial || '0';
      toast(`Apuesta confirmada. Potencial: S/ ${parseFloat(pago).toFixed(2)}`, 'success');
      betslip = []; saveBetslip(); renderBetslip();
      actualizarSaldo();
    } else {
      toast(data.error || data.detail || 'Error al procesar la apuesta', 'error');
    }
  } catch { toast('Error de conexion', 'error'); }
  finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-check"></i> Confirmar Apuesta'; }
  }
}

// ── Navbar dinámico ────────────────────────────────────────────────────────────
async function actualizarSaldo() {
  if (!isLoggedIn()) return;
  const res = await apiFetch('/api/wallet/saldo/');
  if (!res?.ok) return;
  const d = await res.json();
  const el = document.getElementById('nav-balance-val');
  if (el) el.textContent = `S/ ${parseFloat(d.saldo_disponible).toFixed(2)}`;
}

function renderNavbar() {
  const navRight = document.getElementById('nav-right');
  if (!navRight) return;
  if (isLoggedIn()) {
    const user = JSON.parse(localStorage.getItem('fb_user') || '{}');
    navRight.innerHTML = `
      <div class="nav-balance">
        <i class="fa-solid fa-coins" style="color:var(--primary)"></i>
        <span id="nav-balance-val">S/ --</span>
      </div>
      <a href="/wallet/" class="btn btn-ghost btn-sm">
        <i class="fa-solid fa-plus"></i> Recargar
      </a>
      <a href="/mis-apuestas/" class="btn btn-ghost btn-sm">
        <i class="fa-solid fa-user"></i> ${user.username || 'Mi cuenta'}
      </a>
      <button onclick="logout()" class="btn btn-ghost btn-sm">
        <i class="fa-solid fa-right-from-bracket"></i>
      </button>`;
    actualizarSaldo();
  } else {
    navRight.innerHTML = `
      <a href="/login/"    class="btn btn-ghost btn-sm">Iniciar sesion</a>
      <a href="/registro/" class="btn btn-primary btn-sm">Registrarse</a>`;
  }
}

function marcarCuotasActivas() {
  betslip.forEach(b => {
    document.querySelectorAll(`[data-cuota="${b.cuotaId}"]`).forEach(el => el.classList.add('selected'));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  renderNavbar();
  renderBetslip();
  marcarCuotasActivas();
  const mi = document.getElementById('bs-monto');
  if (mi) mi.addEventListener('input', calcBetslip);
});