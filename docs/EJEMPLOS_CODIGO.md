# Ejemplos de Código - Módulos del Sistema

Este documento contiene extractos de código relevantes de cada uno de los tres módulos principales del sistema, mostrando cómo trabajan juntos.

---

## 📁 Archivos de Ejemplo

- **`EJEMPLO_KIOSKO.py`** - Coordinación y control del sistema
- **`EJEMPLO_CABINA_FIRMWARE.cpp`** - Lectura de sensores y publicación de eventos
- **`EJEMPLO_MOTOR_CONTROL.c`** - Control del motor vía MQTT

---

## 1. Kiosko - Coordinación del Sistema

**Archivo:** `EJEMPLO_KIOSKO.py`  
**Módulo:** `kiosko/app/routes.py`

### ¿Qué muestra?

Este extracto muestra cómo **kiosko** coordina el proceso completo de almacenamiento de un vehículo:

1. **Toma de decisiones**: Encuentra la siguiente cabina libre
2. **Control del motor**: Inicia el motor para mover la cabina al nivel del piso
3. **Manejo de eventos MQTT**: Registra un callback que se ejecuta cuando la cabina llega al piso
4. **Coordinación**: Detiene automáticamente el motor cuando detecta que la cabina llegó al piso

### Puntos clave:

- ✅ **Coordinación centralizada**: kiosko toma todas las decisiones de negocio
- ✅ **Comunicación asíncrona**: Usa callbacks para responder a eventos MQTT
- ✅ **Seguridad**: Siempre intenta detener el motor, incluso si hay errores
- ✅ **Integración**: Conecta el servicio de presencia (sensores) con el control del motor

---

## 2. Cabina-Firmware - Sensores y Eventos

**Archivo:** `EJEMPLO_CABINA_FIRMWARE.cpp`  
**Módulo:** `cabina-firmware/main/main.cpp`

### ¿Qué muestra?

Este extracto muestra el **loop principal** del firmware de cada cabina:

1. **Lectura de sensores**: Lee continuamente los sensores físicos (IR y distancia)
2. **Procesamiento de calibración**: Si está calibrando, procesa las muestras y publica cuando termina
3. **Detección de llegada al piso**: Detecta cuando la cabina llega al nivel del piso y publica un evento
4. **Detección de vehículos**: Detecta cuando un vehículo entra o sale usando los sensores IR
5. **Publicación MQTT**: Publica todos los eventos y estados vía MQTT

### Puntos clave:

- ✅ **Autonomía**: Funciona independientemente, publicando datos constantemente
- ✅ **Detección de eventos**: No solo reporta estado, sino que detecta transiciones (llegada al piso, entrada de vehículo)
- ✅ **Múltiples tipos de datos**: Sensores IR, distancia, eventos de calibración, eventos de piso
- ✅ **Tiempo real**: Publica datos inmediatamente cuando detecta cambios

---

## 3. Motor-Control - Control del Motor

**Archivo:** `EJEMPLO_MOTOR_CONTROL.c`  
**Módulo:** `motor-control/main/main.c` (archivo completo)

### ¿Qué muestra?

Este archivo muestra cómo el módulo **motor-control** funciona:

1. **Inicialización**: Configura el GPIO del relé y WiFi
2. **Conexión MQTT**: Se conecta al broker y se suscribe al topic de comandos
3. **Recepción de comandos**: Procesa comandos "ON" y "OFF" recibidos vía MQTT
4. **Control físico**: Activa o desactiva el relé que controla el motor

### Puntos clave:

- ✅ **Simplicidad**: Código simple y directo - solo controla el relé
- ✅ **Reactivo**: Responde a comandos, no toma decisiones
- ✅ **Seguridad**: Estado inicial es "OFF" (motor apagado)
- ✅ **Robustez**: Reconexión automática si se pierde la conexión

---

## 🔄 Flujo de Comunicación entre Módulos

### Ejemplo: Mover una cabina al piso

```
1. KIOSKO (routes.py)
   └─> Encuentra cabina libre: "cabina-02"
   └─> Registra callback para evento "floor/reached"
   └─> Envía comando MQTT: "ON" → topic: "parking/garage-01/motor"

2. MOTOR-CONTROL (main.c)
   └─> Recibe comando "ON" vía MQTT
   └─> Activa relé (GPIO)
   └─> Motor comienza a mover las cabinas

3. CABINA-FIRMWARE (main.cpp)
   └─> Lee sensor de distancia continuamente
   └─> Detecta: distancia <= nivel_piso
   └─> Publica evento MQTT: "floor/reached" → topic: "parking/garage-01/cabina-02/floor/reached"

4. KIOSKO (callback en routes.py)
   └─> Recibe evento "floor/reached" de cabina-02
   └─> Ejecuta callback: detiene el motor
   └─> Envía comando MQTT: "OFF" → topic: "parking/garage-01/motor"

5. MOTOR-CONTROL (main.c)
   └─> Recibe comando "OFF" vía MQTT
   └─> Desactiva relé
   └─> Motor se detiene
```

---

## 💡 Conceptos Clave Mostrados

### 1. Arquitectura Distribuida
Cada módulo tiene responsabilidades claras y se comunica vía MQTT.

### 2. Eventos Asíncronos
Los módulos no esperan respuestas directas, sino que reaccionan a eventos.

### 3. Separación de Responsabilidades
- **kiosko**: Lógica de negocio y coordinación
- **cabina-firmware**: Sensores y detección
- **motor-control**: Control físico simple

### 4. Robustez
- Los sensores siguen funcionando aunque kiosko esté desconectado
- El motor se puede detener manualmente si es necesario
- Reconexión automática en caso de fallos de red

---

## 📝 Notas para la Presentación

Estos ejemplos muestran:

1. **kiosko**: Cómo el sistema central coordina y toma decisiones
2. **cabina-firmware**: Cómo los sensores detectan eventos y publican datos
3. **motor-control**: Cómo se ejecutan las acciones físicas

Juntos, demuestran una arquitectura modular donde cada componente tiene un rol específico y se comunican de forma asíncrona vía MQTT.
