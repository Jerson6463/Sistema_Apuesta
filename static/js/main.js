// FairBet Lab — main.js
// Autenticación: sesión Django (cookie). Sin JWT ni localStorage de tokens.

let betslip = JSON.parse(localStorage.getItem('fb_betslip') || '[]');

// ── CSRF ───────────────────────────────────────────────────────────────────────
function getCsrf() {
  return document.cookie.split(';')
    .find(c => c.trim().startsWith('csrftoken='))
    ?.split('=')[1] || '';
}

// ── API fetch con sesión Django ────────────────────────────────────────────────
async function apiFetch(url, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (opts.method && opts.method !== 'GET') {
    headers['X-CSRFToken'] = getCsrf();
  }
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 403 || res.status === 401) {
    window.location.href = '/login/';
    return null;
  }
  return res;
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const wrap = document.getElementById('toast-wrap');
  if (!wrap) return;
  const icons = { success: 'fa-circle-check', error: 'fa-circle-xmark', info: 'fa-circle-info' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<i class="${icons[type] || icons.info}"></i><span>${msg}</span>`;
  wrap.appendChild(t);
  setTimeout(() => {
    t.style.transition = '.3s';
    t.style.opacity = '0';
    t.style.transform = 'translateX(30px)';
    setTimeout(() => t.remove(), 320);
  }, 5000);
}

function mostrarErrorBetslip(msg) {
  const el = document.getElementById('bs-error');
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}

function limpiarErrorBetslip() {
  const el = document.getElementById('bs-error');
  if (el) { el.textContent = ''; el.style.display = 'none'; }
}

// ── Betslip ────────────────────────────────────────────────────────────────────
function saveBetslip() { localStorage.setItem('fb_betslip', JSON.stringify(betslip)); }

function limpiarBetslip() {
  betslip = [];
  document.querySelectorAll('.cuota-btn.selected').forEach(el => el.classList.remove('selected'));
  saveBetslip();
  renderBetslip();
}

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
  const body    = document.getElementById('bs-body');
  const foot    = document.getElementById('bs-foot');
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
  const monto     = parseFloat(mi.value) || 0;
  const totalOdds = betslip.reduce((acc, b) => acc * b.odds, 1);
  if (ti) ti.textContent = totalOdds.toFixed(2);
  if (gi) gi.textContent = `S/ ${(monto * totalOdds).toFixed(2)}`;
}

// ── Confirmar apuesta ──────────────────────────────────────────────────────────
async function confirmarApuesta() {
  limpiarErrorBetslip();
  if (!betslip.length) { toast('Agrega al menos una selección al ticket', 'error'); return; }
  const monto = parseFloat(document.getElementById('bs-monto')?.value || 0);
  if (monto <= 0) { toast('Ingresa un monto válido', 'error'); return; }

  const btn = document.getElementById('btn-apostar');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Procesando...'; }

  try {
    let res;
    if (betslip.length === 1) {
      res = await apiFetch('/api/apuestas/', {
        method: 'POST',
        body: JSON.stringify({
          cuota_id:           betslip[0].cuotaId,
          monto:              monto.toFixed(4),
          clave_idempotencia: crypto.randomUUID(),
        })
      });
    } else {
      res = await apiFetch('/api/apuestas/combinada/', {
        method: 'POST',
        body: JSON.stringify({
          cuota_ids:          betslip.map(b => b.cuotaId),
          monto:              monto.toFixed(4),
          clave_idempotencia: crypto.randomUUID(),
        })
      });
    }

    if (!res) return;

    const ct   = res.headers.get('content-type') || '';
    const data = ct.includes('application/json') ? await res.json() : null;

    if (res.ok) {
      const pago = data?.apuesta?.pago_potencial || data?.combinada?.pago_potencial || '0';
      toast(`¡Apuesta confirmada! Potencial: S/ ${parseFloat(pago).toFixed(2)}`, 'success');
      betslip = [];
      saveBetslip();
      renderBetslip();
      // Actualizar saldo en navbar sin recargar página
      actualizarSaldoNavbar();
    } else {
      const statusMsgs = { 402: 'Saldo insuficiente. Recarga fichas primero.', 429: 'Demasiadas solicitudes. Espera un momento antes de apostar de nuevo.' };
      const errMsg = data?.error || data?.detail || statusMsgs[res.status] || `Error ${res.status} al procesar la apuesta`;
      toast(errMsg, 'error');
      mostrarErrorBetslip(errMsg);
    }
  } catch (e) {
    toast('Error inesperado: ' + (e?.message || 'desconocido'), 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-check"></i> Confirmar Apuesta';
    }
  }
}

// ── Actualizar saldo en navbar (sin recargar página) ───────────────────────────
async function actualizarSaldoNavbar() {
  const el = document.getElementById('nav-balance-val');
  if (!el) return;
  const res = await apiFetch('/api/wallet/saldo/');
  if (!res?.ok) return;
  const d = await res.json();
  el.textContent = `S/ ${parseFloat(d.saldo_disponible).toFixed(2)}`;
}

// ── Al cargar la página ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderBetslip();
  // Marcar cuotas que ya están en el betslip guardado
  betslip.forEach(b => {
    document.querySelectorAll(`[data-cuota="${b.cuotaId}"]`)
      .forEach(el => el.classList.add('selected'));
  });
  const mi = document.getElementById('bs-monto');
  if (mi) mi.addEventListener('input', calcBetslip);
});