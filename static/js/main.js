// FairBet Lab — Scripts principales

document.addEventListener('DOMContentLoaded', () => {

  // ── Animación de entrada para las cards ──
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.ep-card, .feature-card, .stat-card, .user-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(16px)';
    el.style.transition = 'opacity .4s ease, transform .4s ease';
    observer.observe(el);
  });

  // ── Contador animado de stats ──
  document.querySelectorAll('.stat-card .num').forEach(el => {
    const target = parseInt(el.textContent);
    if (isNaN(target)) return;
    let current = 0;
    const step = Math.ceil(target / 30);
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current;
      if (current >= target) clearInterval(timer);
    }, 40);
  });

  // ── Copiar endpoint al hacer clic ──
  document.querySelectorAll('.ep-path').forEach(el => {
    el.style.cursor = 'pointer';
    el.title = 'Click para copiar';
    el.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const text = el.textContent;
      navigator.clipboard.writeText(text).then(() => {
        const original = el.textContent;
        el.textContent = '✓ Copiado';
        el.style.color = '#4ade80';
        setTimeout(() => {
          el.textContent = original;
          el.style.color = '';
        }, 1200);
      });
    });
  });

  // ── Hora actual en Lima ──
  const timeEl = document.getElementById('hora-lima');
  if (timeEl) {
    const update = () => {
      const now = new Date();
      timeEl.textContent = now.toLocaleTimeString('es-PE', {
        timeZone: 'America/Lima',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    };
    update();
    setInterval(update, 1000);
  }

});