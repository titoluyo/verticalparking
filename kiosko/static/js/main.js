const indicator = document.getElementById('presence-indicator');
const titleEl = document.getElementById('presence-title');
const metaEl = document.getElementById('presence-meta');
const actionButtons = document.getElementById('action-buttons');
const btnGuardar = document.getElementById('btn-guardar');
const btnRecoger = document.getElementById('btn-recoger');
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
    updatePresenceFromData(data);
  } catch (err) {
    console.warn('Presence fetch failed', err);
    setIndicator('presence-indicator--error', 'Estado desconocido', 'Imposible leer los sensores');
    updatePaneVisibility('error');
  }
}

let eventSource = null;
let pollInterval = null;
let visibilityHandlerAdded = false;

function updatePresenceFromData(data) {
  if (!data.connected && data.status !== 'online') {
    setIndicator('presence-indicator--error', 'Sin conexión', 'Revisar MQTT del sensor');
    updatePaneVisibility('error');
    return;
  }

  // Use state and message from backend if available, otherwise fall back to old logic
  let currentState = null;
  if (data.state && data.message) {
    const stateClass = `presence-indicator--${data.state}`;
    setIndicator(stateClass, data.message, formatMeta(data.updated_at));
    currentState = data.state;
  } else {
    // Fallback for backward compatibility
    if (data.occupied) {
      setIndicator('presence-indicator--occupied', 'Vehículo detectado', formatMeta(data.updated_at));
      currentState = 'occupied';
    } else {
      setIndicator('presence-indicator--free', 'Espacio libre', formatMeta(data.updated_at));
      currentState = 'free';
    }
  }
  
  // Update pane visibility based on state
  updatePaneVisibility(currentState);
}

function updatePaneVisibility(state) {
  // When state is "free" (Espacio libre) → show only "Recoger vehículo"
  // When state is "entered" (Vehiculo ingresado) → show only "Guardar vehículo"
  // Other states → hide both buttons
  if (state === 'free') {
    if (actionButtons) actionButtons.style.display = 'grid';
    if (btnRecoger) btnRecoger.style.display = 'block';
    if (btnGuardar) btnGuardar.style.display = 'none';
  } else if (state === 'entered') {
    if (actionButtons) actionButtons.style.display = 'grid';
    if (btnGuardar) btnGuardar.style.display = 'block';
    if (btnRecoger) btnRecoger.style.display = 'none';
  } else {
    // Hide both buttons for other states (transitioning, error, idle, etc.)
    if (actionButtons) actionButtons.style.display = 'none';
    if (btnGuardar) btnGuardar.style.display = 'none';
    if (btnRecoger) btnRecoger.style.display = 'none';
  }
}

function handleVisibilityChange() {
  if (document.hidden) {
    // Page hidden - close SSE connection to save resources
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  } else {
    // Page visible - reconnect SSE if it was closed
    if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
      if (typeof EventSource !== 'undefined') {
        connectPresenceStream();
      } else {
        refreshPresence();
      }
    }
  }
}

function connectPresenceStream() {
  // Check if EventSource is supported
  if (typeof EventSource === 'undefined') {
    console.warn('EventSource not supported, falling back to polling');
    schedulePresencePolling();
    return;
  }

  // Close existing connection if any
  if (eventSource) {
    eventSource.close();
  }

  try {
    eventSource = new EventSource('/api/presence/stream');

    eventSource.onopen = function() {
      console.log('SSE connection opened');
    };

    eventSource.onmessage = function(event) {
      try {
        const data = JSON.parse(event.data);
        updatePresenceFromData(data);
      } catch (err) {
        console.warn('Failed to parse SSE message:', err);
      }
    };

    eventSource.onerror = function(err) {
      console.warn('SSE connection error:', err);
      // EventSource will automatically try to reconnect
      // But if it fails completely, fall back to polling
      if (eventSource && eventSource.readyState === EventSource.CLOSED) {
        console.warn('SSE connection closed, falling back to polling');
        eventSource.close();
        eventSource = null;
        schedulePresencePolling();
      }
    };
  } catch (err) {
    console.warn('Failed to create EventSource:', err);
    schedulePresencePolling();
  }
}

function schedulePresencePolling() {
  // Fallback to polling if SSE is not available
  refreshPresence();
  if (pollInterval) {
    clearInterval(pollInterval);
  }
  pollInterval = setInterval(refreshPresence, 3000);
}

function schedulePresenceUpdates() {
  // Add visibility change handler once
  if (!visibilityHandlerAdded) {
    document.addEventListener('visibilitychange', handleVisibilityChange);
    visibilityHandlerAdded = true;
  }
  
  // Set initial button visibility (hidden by default until we know the state)
  // This will be updated when the first data arrives
  if (actionButtons) actionButtons.style.display = 'none';
  if (btnGuardar) btnGuardar.style.display = 'none';
  if (btnRecoger) btnRecoger.style.display = 'none';
  
  // Try SSE first, fall back to polling if not supported
  connectPresenceStream();
}

if (indicator) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedulePresenceUpdates);
  } else {
    schedulePresenceUpdates();
  }
}
