// FairBet Lab — Frontend principal
const API = '';
let accessToken = localStorage.getItem('fb_access');
let refreshToken = localStorage.getItem('fb_refresh');
let userData = JSON.parse(localStorage.getItem('fb_user') || 'null');
let betslip = JSON.parse(localStorage.getItem('fb_betslip') || '[]');

// ── Auth helpers ──────────────────────────────────────────────────────────────
async function apiFetch(url, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  let res = await fetch(API + url, { ...options, headers });

  if (res.status === 401 && refreshToken) {
    const r = await fetch(API + '/api/usuarios/login/refresh/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken })
    });
    if (r.ok) {
      const d = await r.json();
      accessToken = d.access;
      localStorage.setItem('fb_access', accessToken);
      headers['Authorization'] = `Bearer ${accessToken}`;
      res = await fetch(API + url, { ...options, headers });
    } else { logout(); return null; }
  }
  return res;
}

function logout() {
  localStorage.removeItem('fb_access');
  localStorage.removeItem('fb_refresh');
  localStorage.removeItem('fb_user');
  localStorage.removeItem('fb_betslip');
  window.location.href = '/login/';
}

function isLoggedIn() { return !!accessToken; }

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const t = document.createElement('div');
  const icons = { success: '✅', error: '❌', info: '🎯' };
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${icons[type]||'ℹ️'}</span><span>${msg}</span>`;
  container.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(100%)'; t.style.transition = '.3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

// ── Betslip ───────────────────────────────────────────────────────────────────
function saveBetslip() { localStorage.setItem('fb_betslip', JSON.stringify(betslip)); }

function addToBetslip(cuotaId, seleccion, odds, evento, mercado) {
  const exists = betslip.find(b => b.cuotaId === cuotaId);
  if (exists) {
    betslip = betslip.filter(b => b.cuotaId !== cuotaId);
    document.querySelectorAll(`[data-cuota="${cuotaId}"]`).forEach(el => el.classList.remove('selected'));
    saveBetslip(); renderBetslip(); return;
  }
  betslip.push({ cuotaId, seleccion, odds, evento, mercado });
  document.querySelectorAll(`[data-cuota="${cuotaId}"]`).forEach(el => el.classList.add('selected'));
  saveBetslip(); renderBetslip();
  toast(`${seleccion} @ ${odds} agregado al ticket`, 'success');
}

function removeFromBetslip(cuotaId) {
  betslip = betslip.filter(b => b.cuotaId !== cuotaId);
  document.querySelectorAll(`[data-cuota="${cuotaId}"]`).forEach(el => el.classList.remove('selected'));
  saveBetslip(); renderBetslip();
}

function renderBetslip() {
  const body = document.getElementById('betslip-body');
  const footer = document.getElementById('betslip-footer');
  const count = document.getElementById('betslip-count');
  if (!body) return;
  if (count) count.textContent = betslip.length || '';

  if (betslip.length === 0) {
    body.innerHTML = `<div class="betslip-empty"><div class="icon">🎯</div><p>Selecciona una cuota para apostar</p></div>`;
    if (footer) footer.style.display = 'none';
    return;
  }

  body.innerHTML = betslip.map(b => `
    <div class="betslip-item">
      <button class="remove" onclick="removeFromBetslip(${b.cuotaId})">✕</button>
      <div class="bi-evento">${b.evento}</div>
      <div class="bi-seleccion">${b.seleccion}</div>
      <div class="bi-odds">@ ${b.odds}</div>
    </div>
  `).join('');

  if (footer) footer.style.display = 'block';
  calcularBetslip();
}

function calcularBetslip() {
  const montoInput = document.getElementById('monto-apuesta');
  const gananciaEl = document.getElementById('ganancia-potencial');
  const totalOddsEl = document.getElementById('total-odds');
  if (!montoInput || !gananciaEl) return;

  const monto = parseFloat(montoInput.value) || 0;
  const totalOdds = betslip.reduce((acc, b) => acc * parseFloat(b.odds), 1);
  const ganancia = (monto * totalOdds).toFixed(2);

  if (totalOddsEl) totalOddsEl.textContent = totalOdds.toFixed(2);
  gananciaEl.textContent = `S/ ${ganancia}`;
}

async function confirmarApuesta() {
  if (!isLoggedIn()) { window.location.href = '/login/'; return; }
  if (betslip.length === 0) { toast('Agrega al menos una selección', 'error'); return; }

  const monto = parseFloat(document.getElementById('monto-apuesta')?.value || 0);
  if (monto <= 0) { toast('Ingresa un monto válido', 'error'); return; }

  const btn = document.getElementById('btn-apostar');
  if (btn) { btn.disabled = true; btn.textContent = 'Procesando...'; }

  try {
    if (betslip.length === 1) {
      const b = betslip[0];
      const res = await apiFetch('/api/apuestas/', {
        method: 'POST',
        body: JSON.stringify({ cuota_id: b.cuotaId, monto: monto.toFixed(4), clave_idempotencia: crypto.randomUUID() })
      });
      const data = await res.json();
      if (res.ok) {
        toast(`¡Apuesta confirmada! Pago potencial: S/ ${data.apuesta.pago_potencial}`, 'success');
        betslip = []; saveBetslip(); renderBetslip();
        actualizarSaldo();
      } else {
        toast(data.error || 'Error al procesar la apuesta', 'error');
      }
    } else {
      const res = await apiFetch('/api/apuestas/combinada/', {
        method: 'POST',
        body: JSON.stringify({ cuota_ids: betslip.map(b => b.cuotaId), monto: monto.toFixed(4), clave_idempotencia: crypto.randomUUID() })
      });
      const data = await res.json();
      if (res.ok) {
        toast(`¡Combinada confirmada! Pago potencial: S/ ${data.combinada.pago_potencial}`, 'success');
        betslip = []; saveBetslip(); renderBetslip();
        actualizarSaldo();
      } else {
        toast(data.error || 'Error al procesar la apuesta', 'error');
      }
    }
  } catch (e) {
    toast('Error de conexión', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '✅ Confirmar Apuesta'; }
  }
}

async function actualizarSaldo() {
  if (!isLoggedIn()) return;
  const res = await apiFetch('/api/wallet/saldo/');
  if (!res || !res.ok) return;
  const data = await res.json();
  const el = document.getElementById('nav-saldo');
  if (el) el.textContent = `S/ ${parseFloat(data.saldo_disponible).toFixed(2)}`;
}

// ── Navbar dinámico ───────────────────────────────────────────────────────────
function renderNavbar() {
  const navRight = document.getElementById('nav-right');
  if (!navRight) return;
  if (isLoggedIn()) {
    navRight.innerHTML = `
      <span class="nav-saldo" id="nav-saldo">S/ --</span>
      <a href="/wallet/" class="btn btn-outline btn-sm">💰 Wallet</a>
      <a href="/mis-apuestas/" class="btn btn-outline btn-sm">🎯 Mis Apuestas</a>
      <button onclick="logout()" class="btn btn-outline btn-sm">Salir</button>
    `;
    actualizarSaldo();
  } else {
    navRight.innerHTML = `
      <a href="/login/" class="btn btn-outline btn-sm">Iniciar Sesión</a>
      <a href="/registro/" class="btn btn-primary btn-sm">Registrarse</a>
    `;
  }
}

// ── Marcar cuotas ya en betslip ───────────────────────────────────────────────
function marcarCuotasActivas() {
  betslip.forEach(b => {
    document.querySelectorAll(`[data-cuota="${b.cuotaId}"]`).forEach(el => el.classList.add('selected'));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  renderNavbar();
  renderBetslip();
  marcarCuotasActivas();
  const mi = document.getElementById('monto-apuesta');
  if (mi) mi.addEventListener('input', calcularBetslip);
});