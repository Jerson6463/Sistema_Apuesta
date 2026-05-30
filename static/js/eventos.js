// ── Banderas de equipos usando flagcdn.com ─────────────────────────────────────
const PAISES = {
  'Peru':       { code: 'pe', nombre: 'Peru' },
  'Brasil':     { code: 'br', nombre: 'Brasil' },
  'Argentina':  { code: 'ar', nombre: 'Argentina' },
  'Mexico':     { code: 'mx', nombre: 'Mexico' },
  'Uruguay':    { code: 'uy', nombre: 'Uruguay' },
  'Colombia':   { code: 'co', nombre: 'Colombia' },
  'Chile':      { code: 'cl', nombre: 'Chile' },
  'Ecuador':    { code: 'ec', nombre: 'Ecuador' },
  'Bolivia':    { code: 'bo', nombre: 'Bolivia' },
  'Paraguay':   { code: 'py', nombre: 'Paraguay' },
  'Venezuela':  { code: 've', nombre: 'Venezuela' },
  'Alemania':   { code: 'de', nombre: 'Alemania' },
  'Francia':    { code: 'fr', nombre: 'Francia' },
  'Espana':     { code: 'es', nombre: 'Espana' },
  'Inglaterra': { code: 'gb-eng', nombre: 'Inglaterra' },
  'Portugal':   { code: 'pt', nombre: 'Portugal' },
  'Italia':     { code: 'it', nombre: 'Italia' },
  'Holanda':    { code: 'nl', nombre: 'Holanda' },
  'Belgica':    { code: 'be', nombre: 'Belgica' },
  'Croacia':    { code: 'hr', nombre: 'Croacia' },
  'Marruecos':  { code: 'ma', nombre: 'Marruecos' },
  'Japon':      { code: 'jp', nombre: 'Japon' },
  'Corea':      { code: 'kr', nombre: 'Corea' },
  'Australia':  { code: 'au', nombre: 'Australia' },
  'USA':        { code: 'us', nombre: 'Estados Unidos' },
  'Canada':     { code: 'ca', nombre: 'Canada' },
  'Senegal':    { code: 'sn', nombre: 'Senegal' },
};

/**
 * Genera el HTML de la bandera de un equipo.
 * Usa flagcdn.com para las imágenes.
 */
function banderaHTML(nombreEquipo) {
  const pais = PAISES[nombreEquipo];
  if (pais) {
    return `<img
      class="equipo-flag"
      src="https://flagcdn.com/48x36/${pais.code}.png"
      alt="${pais.nombre}"
      onerror="this.outerHTML='<div class=\\'equipo-flag-placeholder\\'>${nombreEquipo.substring(0,3).toUpperCase()}</div>'"
    />`;
  }
  // Fallback: muestra las 3 primeras letras del nombre
  return `<div class="equipo-flag-placeholder">${nombreEquipo.substring(0,3).toUpperCase()}</div>`;
}

/**
 * Genera un botón de cuota seguro (sin problemas con comillas en los nombres).
 */
function buildCuotaBtn(cuotaId, seleccion, label, valor, eventoNombre, mercadoTipo) {
  const btn = document.createElement('div');
  btn.className = 'cuota-btn';
  btn.dataset.cuota = cuotaId;
  btn.innerHTML = `<div class="qlabel">${label}</div><div class="qval">${parseFloat(valor).toFixed(2)}</div>`;
  btn.addEventListener('click', () => addToBetslip(cuotaId, seleccion, parseFloat(valor), eventoNombre, mercadoTipo));
  return btn;
}

/**
 * Construye el header de un evento card.
 */
function buildEventoHeader(evento) {
  const fecha = new Date(evento.fecha_inicio).toLocaleString('es-PE', {
    weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  });
  const esVivo = evento.estado === 'en_vivo';
  const header = document.createElement('div');
  header.className = 'evento-meta';
  header.innerHTML = `
    <span class="liga">
      <i class="fa-solid fa-earth-americas"></i>
      Mundial 2026 &middot; Fase de Grupos
    </span>
    ${esVivo
      ? '<span class="live-badge"><span class="live-dot"></span> EN VIVO</span>'
      : `<span style="display:flex;align-items:center;gap:5px">
           <i class="fa-regular fa-clock"></i> ${fecha}
         </span>`
    }`;
  return header;
}

/**
 * Construye el bloque de equipos (banderas + nombres).
 */
function buildEquipos(equipo_local, equipo_visitante) {
  const wrap = document.createElement('div');
  wrap.className = 'equipos';
  wrap.innerHTML = `
    <div class="equipo">
      ${banderaHTML(equipo_local)}
      <div class="equipo-name">${equipo_local}</div>
      <div class="equipo-label">Local</div>
    </div>
    <div class="vs-badge">VS</div>
    <div class="equipo">
      ${banderaHTML(equipo_visitante)}
      <div class="equipo-name">${equipo_visitante}</div>
      <div class="equipo-label">Visitante</div>
    </div>`;
  return wrap;
}

/**
 * Construye una fila de cuotas dado un mercado ya cargado.
 */
function buildFilaCuotas(mercado, eventoNombre, local, visitante) {
  const wrap = document.createElement('div');

  // `sels` acepta múltiples nombres de selección para compatibilidad con eventos
  // creados antes y después de la estandarización de la BD.
  const CONFIGS = {
    '1X2': [
      { sels: ['1', 'local'],              label: '1 &nbsp; ' + local.substring(0,3).toUpperCase(),      nombre: local },
      { sels: ['empate', 'X', 'x', 'draw'],label: 'X &nbsp; Empate',                                     nombre: 'Empate' },
      { sels: ['2', 'visitante'],          label: '2 &nbsp; ' + visitante.substring(0,3).toUpperCase(),   nombre: visitante },
    ],
    'over_under': [
      { sels: ['over',  'over_2.5'],  label: 'Mas de 2.5',    nombre: 'Mas de 2.5' },
      { sels: ['under', 'under_2.5'], label: 'Menos de 2.5',  nombre: 'Menos de 2.5' },
    ],
    'btts': [
      { sels: ['si'], label: 'Si anotan',  nombre: 'Si anotan' },
      { sels: ['no'], label: 'No ambos',   nombre: 'No ambos' },
    ],
    'handicap': [
      { sels: ['local',     'local_-1'],     label: 'Local &minus;1',  nombre: 'Local -1' },
      { sels: ['visitante', 'visitante_+1'], label: 'Visit. +1',       nombre: 'Visitante +1' },
    ],
  };

  const LABELS_MERCADO = {
    '1X2':        '<i class="fa-solid fa-chart-simple"></i> 1X2 &mdash; Resultado del partido',
    'over_under': '<i class="fa-solid fa-arrow-up-9-1"></i> Over/Under 2.5 goles',
    'btts':       '<i class="fa-solid fa-arrows-left-right"></i> Ambos equipos anotan',
    'handicap':   '<i class="fa-solid fa-scale-balanced"></i> Handicap',
  };

  const label = document.createElement('div');
  label.className = 'mercado-label';
  label.innerHTML = LABELS_MERCADO[mercado.tipo] || mercado.tipo;
  wrap.appendChild(label);

  const fila = document.createElement('div');
  fila.className = 'cuotas-row';

  const cfg = CONFIGS[mercado.tipo] || [];
  cfg.forEach(c => {
    // Busca la cuota probando todos los nombres de selección posibles
    const cuota = mercado.cuotas.find(q => c.sels.includes(q.seleccion));
    if (cuota) {
      fila.appendChild(buildCuotaBtn(cuota.id, c.nombre, c.label, cuota.valor, eventoNombre, mercado.tipo));
    }
  });

  wrap.appendChild(fila);
  return wrap;
}

/**
 * Construye una tarjeta de evento completa con mercados ya cargados.
 */
function buildEventoCard(evento, mercadosDetalle) {
  const card = document.createElement('div');
  card.className = 'evento-card';
  card.id = `card-ev-${evento.id}`;

  // Header
  card.appendChild(buildEventoHeader(evento));

  // Body
  const body = document.createElement('div');
  body.className = 'evento-body';

  // Equipos
  body.appendChild(buildEquipos(evento.equipo_local, evento.equipo_visitante));

  // Mercados
  if (mercadosDetalle && mercadosDetalle.length) {
    mercadosDetalle.forEach(m => {
      body.appendChild(buildFilaCuotas(m, evento.nombre, evento.equipo_local, evento.equipo_visitante));
    });
  } else {
    const p = document.createElement('p');
    p.style.cssText = 'color:var(--text-3);font-size:13px;text-align:center;padding:12px';
    p.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Cargando cuotas...';
    body.appendChild(p);
  }

  // Footer
  const footer = document.createElement('div');
  footer.className = 'evento-footer';
  footer.innerHTML = `
    <a href="/eventos/${evento.id}/" class="mas-mercados">
      Ver todos los mercados <i class="fa-solid fa-chevron-right"></i>
    </a>`;
  body.appendChild(footer);

  card.appendChild(body);
  return card;
}
