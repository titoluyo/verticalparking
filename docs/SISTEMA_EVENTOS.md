# Sistema de Eventos - Arquitectura Basada en Eventos

## 1. Introducción

El sistema de estacionamiento vertical está diseñado como una **arquitectura basada en eventos**, donde los módulos se comunican de forma asíncrona mediante eventos MQTT. Este documento describe todos los eventos del sistema y cómo fluyen entre los módulos.

---

## 2. Tipos de Eventos

### 2.1. Eventos de Sensores (Publicados por cabina-firmware)

#### 2.1.1. Evento: `presence/entry` (IR1 - Sensor de Entrada)
- **Publicado por:** cabina-firmware
- **Topic:** `parking/{site}/{cabin_id}/presence/entry`
- **Payload:**
  ```json
  {
    "site": "garage-01",
    "device": "cabina-01",
    "sensor": "ir1",
    "present": true,
    "ts": 1234567890.123
  }
  ```
- **Descripción:** Se publica cuando el sensor IR1 detecta que un vehículo comienza a entrar en la cabina.
- **Retenido:** Sí (QoS 1, retain=true)
- **Consumido por:** kiosko (PresenceService)

#### 2.1.2. Evento: `presence/full` (IR2 - Sensor Completo)
- **Publicado por:** cabina-firmware
- **Topic:** `parking/{site}/{cabin_id}/presence/full`
- **Payload:**
  ```json
  {
    "site": "garage-01",
    "device": "cabina-01",
    "sensor": "ir2",
    "present": true,
    "ts": 1234567890.123
  }
  ```
- **Descripción:** Se publica cuando el sensor IR2 detecta que un vehículo está completamente dentro de la cabina.
- **Retenido:** Sí (QoS 1, retain=true)
- **Consumido por:** kiosko (PresenceService)

#### 2.1.3. Evento: `distance/event`
- **Publicado por:** cabina-firmware
- **Topic:** `parking/{site}/{cabin_id}/distance/event`
- **Payload:**
  ```json
  {
    "from_mm": 500,
    "to_mm": 450,
    "ts": 1234567890.123
  }
  ```
- **Descripción:** Eventos de cambio de distancia (no retenido, solo eventos significativos).
- **Retenido:** No (QoS 0)
- **Consumido por:** kiosko (PresenceService)

### 2.2. Eventos de Estado del Sistema (Publicados por cabina-firmware)

#### 2.2.1. Evento: `floor/reached`
- **Publicado por:** cabina-firmware
- **Topic:** `parking/{site}/{cabin_id}/floor/reached`
- **Payload:**
  ```json
  {
    "distance_mm": 450,
    "floor_level_mm": 450,
    "ts": 1234567890.123
  }
  ```
- **Descripción:** Se publica cuando la cabina detecta que ha llegado al nivel del piso (transición, no estado continuo).
- **Retenido:** No (QoS 1, retain=false)
- **Consumido por:** kiosko (callbacks registrados en PresenceService)
- **Acción resultante:** kiosko detiene el motor automáticamente

#### 2.2.2. Evento: `calibration/complete`
- **Publicado por:** cabina-firmware
- **Topic:** `parking/{site}/{cabin_id}/calibration/complete`
- **Payload:**
  ```json
  {
    "floor_level_mm": 450,
    "calibration_rounds": 2,
    "min_distance_mm": 440,
    "max_distance_mm": 1200,
    "ts": 1234567890.123
  }
  ```
- **Descripción:** Se publica cuando la calibración se completa exitosamente.
- **Retenido:** No (QoS 1, retain=false)
- **Consumido por:** kiosko (callbacks registrados en PresenceService)

### 2.3. Comandos (Publicados por kiosko)

#### 2.3.1. Comando: Motor `ON` / `OFF`
- **Publicado por:** kiosko (MotorControlService)
- **Topic:** `parking/{site}/motor`
- **Payload:** `"ON"` o `"OFF"` (string simple)
- **QoS:** 1
- **Retenido:** No
- **Consumido por:** motor-control
- **Acción resultante:** motor-control activa/desactiva el relé

#### 2.3.2. Comando: Calibración `start` / `stop`
- **Publicado por:** kiosko (MotorControlService)
- **Topic:** `parking/{site}/{cabin_id}/cmd`
- **Payload:**
  ```json
  {"start_calibration": true}
  ```
  o
  ```json
  {"stop_calibration": true}
  ```
- **QoS:** 1
- **Retenido:** No
- **Consumido por:** cabina-firmware
- **Acción resultante:** cabina-firmware inicia/detiene el proceso de calibración

---

## 3. Flujos de Eventos Principales

### 3.1. Flujo: Almacenamiento de Vehículo

```
1. [Usuario] → kiosko: POST /guardar (confirmar almacenamiento)
   └─> kiosko: Crea ticket, asigna cabina actual

2. kiosko → motor-control: MQTT "ON" → parking/garage-01/motor
   └─> motor-control: Activa relé → Motor inicia

3. kiosko: Registra callback para evento "floor/reached" de la siguiente cabina libre

4. [Motor mueve cabinas] → cabina-firmware: Detecta cambios de distancia

5. cabina-firmware → kiosko: MQTT "floor/reached" → parking/garage-01/cabina-02/floor/reached
   └─> kiosko: Ejecuta callback
       ├─> kiosko → motor-control: MQTT "OFF" → parking/garage-01/motor
       │   └─> motor-control: Desactiva relé → Motor se detiene
       └─> kiosko: Establece nueva cabina como activa

6. [Vehículo entra] → cabina-firmware: Sensor IR1 detecta entrada
   └─> cabina-firmware → kiosko: MQTT "presence/entry" (present=true)

7. [Vehículo completamente dentro] → cabina-firmware: Sensor IR2 detecta
   └─> cabina-firmware → kiosko: MQTT "presence/full" (present=true)
       └─> kiosko: Actualiza UI (estado: "entered")
```

### 3.2. Flujo: Recuperación de Vehículo

```
1. [Usuario] → kiosko: POST /recoger (escanea QR del ticket)
   └─> kiosko: Identifica cabina donde está el vehículo

2. kiosko → motor-control: MQTT "ON" → parking/garage-01/motor
   └─> motor-control: Activa relé → Motor inicia

3. kiosko: Registra callback para evento "floor/reached" de la cabina objetivo

4. [Motor mueve cabinas] → cabina-firmware: Detecta cambios de distancia

5. cabina-firmware → kiosko: MQTT "floor/reached" → parking/garage-01/cabina-01/floor/reached
   └─> kiosko: Ejecuta callback
       ├─> kiosko → motor-control: MQTT "OFF" → parking/garage-01/motor
       │   └─> motor-control: Desactiva relé → Motor se detiene
       └─> kiosko: Marca cabina como disponible

6. [Vehículo sale] → cabina-firmware: Sensor IR2 detecta salida
   └─> cabina-firmware → kiosko: MQTT "presence/full" (present=false)

7. [Vehículo completamente fuera] → cabina-firmware: Sensor IR1 detecta
   └─> cabina-firmware → kiosko: MQTT "presence/entry" (present=false)
       └─> kiosko: Actualiza UI (estado: "free")
```

### 3.3. Flujo: Calibración del Sistema

```
1. [Usuario] → kiosko: POST /api/calibration/start (cabin_id)
   └─> kiosko → cabina-firmware: MQTT {"start_calibration": true} → parking/garage-01/cabina-01/cmd
       └─> cabina-firmware: Inicia proceso de calibración

2. kiosko → motor-control: MQTT "ON" → parking/garage-01/motor
   └─> motor-control: Activa relé → Motor inicia

3. [Motor gira 2 rotaciones completas] → cabina-firmware: Mide distancia continuamente
   └─> cabina-firmware: Registra distancia mínima (nivel del piso)

4. cabina-firmware: Detecta que completó 2 rotaciones
   └─> cabina-firmware → kiosko: MQTT "calibration/complete" → parking/garage-01/cabina-01/calibration/complete
       └─> kiosko: Ejecuta callback
           ├─> kiosko → motor-control: MQTT "OFF" → parking/garage-01/motor
           │   └─> motor-control: Desactiva relé → Motor se detiene
           └─> kiosko: Guarda nivel del piso en base de datos
```

### 3.4. Flujo: Detección Continua de Vehículos

```
[Loop continuo en cabina-firmware]

1. cabina-firmware: Lee sensores IR cada 100ms
   ├─> Si IR1 cambia: Publica "presence/entry"
   └─> Si IR2 cambia: Publica "presence/full"

2. cabina-firmware: Lee sensor de distancia cada 100ms
   ├─> Si distancia cambia significativamente: Publica "distance/event"
   └─> Si detecta llegada al piso: Publica "floor/reached" (una vez)

3. kiosko: Recibe todos los eventos y actualiza estado interno
   └─> kiosko: Expone estado vía API REST y actualiza UI en tiempo real
```

---

## 4. Características del Sistema de Eventos

### 4.1. Asincronía
- Los eventos se publican y consumen de forma asíncrona
- No hay bloqueo entre módulos
- Los módulos pueden funcionar independientemente

### 4.2. Desacoplamiento
- Los módulos no conocen la implementación de otros módulos
- Solo conocen los eventos que publican/consumen
- Fácil agregar nuevos módulos o modificar existentes

### 4.3. Mensajes Retenidos
- Los eventos de estado (presence/entry, presence/full) son retenidos
- Permite recuperar el estado actual al reconectar
- Los eventos de transición (floor/reached) no son retenidos

### 4.4. Calidad de Servicio (QoS)
- **QoS 0:** Eventos de distancia (no críticos, pueden perderse)
- **QoS 1:** Eventos de presencia, comandos, eventos de piso (garantía de entrega al menos una vez)

### 4.5. Callbacks y Reacciones
- kiosko registra callbacks para eventos específicos
- Los callbacks ejecutan acciones automáticas (detener motor, actualizar estado)
- Permite lógica reactiva sin polling

---

## 5. Estados y Transiciones

### 5.1. Estado de Cabina (basado en sensores IR)

```
[FREE] ──IR1 ON──> [TRANSITIONING] ──IR2 ON──> [ENTERED]
  ↑                                        │
  └─────────────── IR1 OFF ───────────────┘
  └─────────────── IR2 OFF ───────────────┘
```

### 5.2. Estado del Motor

```
[OFF] ──MQTT "ON"──> [ON] ──MQTT "OFF"──> [OFF]
                      │
                      └─── Evento "floor/reached" ──> [OFF]
```

### 5.3. Estado de Calibración

```
[INACTIVE] ──Comando "start"──> [ACTIVE] ──Evento "complete"──> [INACTIVE]
                                    │
                                    └───Comando "stop"──> [INACTIVE]
```

---

## 6. Eventos por Módulo

### 6.1. cabina-firmware (Publicador)
- ✅ `presence/entry` (IR1)
- ✅ `presence/full` (IR2)
- ✅ `distance/event`
- ✅ `floor/reached`
- ✅ `calibration/complete`
- ✅ `status` (estado del dispositivo)

### 6.2. cabina-firmware (Consumidor)
- ✅ `cmd` (comandos de calibración)

### 6.3. kiosko (Publicador)
- ✅ `motor` (ON/OFF)
- ✅ `cmd` (comandos de calibración)

### 6.4. kiosko (Consumidor)
- ✅ `presence/entry` (todas las cabinas)
- ✅ `presence/full` (todas las cabinas)
- ✅ `distance/event` (todas las cabinas)
- ✅ `floor/reached` (todas las cabinas)
- ✅ `calibration/complete` (todas las cabinas)

### 6.5. motor-control (Consumidor)
- ✅ `motor` (ON/OFF)

---

## 7. Ventajas de la Arquitectura Basada en Eventos

1. **Escalabilidad**: Fácil agregar más cabinas sin modificar código existente
2. **Resiliencia**: Si un módulo falla, los otros continúan funcionando
3. **Mantenibilidad**: Cambios en un módulo no afectan a otros
4. **Testabilidad**: Cada módulo puede probarse independientemente
5. **Observabilidad**: Todos los eventos están centralizados en MQTT, fácil monitorear
6. **Flexibilidad**: Nuevas funcionalidades se agregan como nuevos eventos

---

## 8. Consideraciones de Diseño

### 8.1. Idempotencia
- Los eventos deben ser idempotentes cuando sea posible
- Los comandos pueden duplicarse sin causar efectos secundarios indeseados

### 8.2. Orden de Eventos
- Los eventos de sensores pueden llegar fuera de orden
- El sistema debe manejar estados basados en el último evento recibido
- Los eventos de transición (floor/reached) son únicos y no se repiten

### 8.3. Timeouts y Reconexión
- Los módulos deben manejar desconexiones de MQTT
- Reconexión automática con suscripciones restauradas
- Mensajes retenidos permiten recuperar estado al reconectar

### 8.4. Seguridad
- Autenticación MQTT (usuario/contraseña)
- Topics específicos por sitio y dispositivo
- Comandos críticos (motor) requieren autenticación
