const indicator = document.getElementById('presence-indicator');
const titleEl = document.getElementById('presence-title');
const metaEl = document.getElementById('presence-meta');
const STATES = ['presence-indicator--occupied', 'presence-indicator--free', 'presence-indicator--transitioning', 'presence-indicator--entered', 'presence-indicator--idle', 'presence-indicator--error'];

function setIndicator(stateClass, title, meta) {
  if (!indicator || !titleEl || !metaEl) return;
  STATES.forEach((cls) => indicator.classList.remove(cls));
  indicator.classList.add(stateClass);
  titleEl.textContent = title;
  metaEl.textContent = meta;
}

function formatMeta(iso) {
  if (!iso) return 'Sin lecturas recientes';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'Sin lecturas recientes';
  return `Actualizado ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

async function refreshPresence() {
  if (!indicator) return;
  try {
    const res = await fetch('/api/presence', { cache: 'no-store' });
    if (!res.ok) throw new Error('Respuesta inválida');
    const data = await res.json();

    if (!data.connected && data.status !== 'online') {
      setIndicator('presence-indicator--error', 'Sin conexión', 'Revisar MQTT del sensor');
      return;
    }

    // Use state and message from backend if available, otherwise fall back to old logic
    if (data.state && data.message) {
      const stateClass = `presence-indicator--${data.state}`;
      setIndicator(stateClass, data.message, formatMeta(data.updated_at));
    } else {
      // Fallback for backward compatibility
      if (data.occupied) {
        setIndicator('presence-indicator--occupied', 'Vehículo detectado', formatMeta(data.updated_at));
      } else {
        setIndicator('presence-indicator--free', 'Espacio libre', formatMeta(data.updated_at));
      }
    }
  } catch (err) {
    console.warn('Presence fetch failed', err);
    setIndicator('presence-indicator--error', 'Estado desconocido', 'Imposible leer los sensores');
  }
}

function schedulePresenceUpdates() {
  refreshPresence();
  setInterval(refreshPresence, 3000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshPresence();
  });
}

if (indicator) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedulePresenceUpdates);
  } else {
    schedulePresenceUpdates();
  }
}
