// Auto-refresh records table every 10 seconds (index view)
async function refreshRegistros() {
  const tabla = document.getElementById('tabla-registros');
  if (!tabla) return; // not on index page
  try {
    const res = await fetch('/api/registros');
    if (!res.ok) return;
    const data = await res.json();
    const tbody = tabla.querySelector('tbody');
    tbody.innerHTML = '';
    for (const r of data) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${r.id}</td><td>${r.nombre}</td><td>${r.placa}</td><td>${r.creado_en}</td>`;
      tbody.appendChild(tr);
    }
  } catch (_) {
    // Ignore errors in kiosk mode
  }
}

setInterval(refreshRegistros, 10000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refreshRegistros();
});

