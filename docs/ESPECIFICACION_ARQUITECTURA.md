# Especificación de Arquitectura - Sistema de Estacionamiento Vertical

## 1. Visión General

Este documento describe la arquitectura a alto nivel del sistema de estacionamiento vertical, explicando cómo los tres módulos principales trabajan juntos para proporcionar una solución completa de gestión de estacionamiento automatizado.

El sistema está diseñado para gestionar múltiples cabinas de estacionamiento vertical, donde cada cabina puede almacenar un vehículo. El sistema detecta automáticamente cuando un vehículo entra, gestiona el movimiento de las cabinas para posicionarlas en el nivel del piso, y proporciona una interfaz de usuario para el almacenamiento y recuperación de vehículos.

---

## 2. Componentes del Sistema

El sistema está compuesto por tres módulos principales que se comunican a través de MQTT (Message Queuing Telemetry Transport):

### 2.1. Kiosko (Interfaz de Usuario y Control)

**Tecnología:** Flask (Python) - Aplicación Web

**Función Principal:**
Kiosko es el cerebro del sistema. Actúa como:
- **Interfaz de usuario**: Proporciona una aplicación web para que los operadores gestionen el estacionamiento
- **Coordinador central**: Toma decisiones sobre qué cabina usar y cuándo mover el sistema
- **Gestor de datos**: Almacena información de tickets, vehículos y estado de las cabinas
- **Controlador del motor**: Envía comandos para iniciar y detener el motor que mueve las cabinas

**Características principales:**
- Interfaz web responsive para operadores
- Monitoreo en tiempo real del estado de los sensores de cada cabina
- Gestión de tickets de entrada y salida con códigos QR
- Impresión automática de tickets térmicos
- Base de datos SQLite para persistencia de información
- API REST para integración con otros sistemas

**Comunicación:**
- **Recibe datos de:** cabina-firmware (estado de sensores, distancia, eventos)
- **Envía comandos a:** motor-control (iniciar/detener motor)
- **Envía comandos a:** cabina-firmware (iniciar calibración)

---

### 2.2. Cabina-Firmware (Sensores y Monitoreo)

**Tecnología:** ESP-IDF (C/C++) - Firmware embebido para ESP32

**Función Principal:**
Cada cabina tiene su propio módulo ESP32 que actúa como el "sistema nervioso" de la cabina. Su función es:
- **Detectar vehículos**: Usa sensores infrarrojos (IR) para detectar cuando un vehículo entra o sale
- **Medir distancia**: Usa un sensor láser (VL53L0X) para determinar la posición vertical de la cabina
- **Reportar estado**: Publica constantemente el estado de los sensores y la distancia vía MQTT
- **Detectar llegada al piso**: Notifica cuando la cabina ha llegado al nivel del piso

**Sensores:**
- **Sensor IR1 (Entrada)**: Detecta cuando un vehículo comienza a entrar en la cabina
- **Sensor IR2 (Completo)**: Detecta cuando un vehículo está completamente dentro de la cabina
- **Sensor de Distancia VL53L0X**: Mide la distancia desde la cabina hasta un punto de referencia, permitiendo determinar si está en el nivel del piso

**Comunicación:**
- **Publica datos a:** kiosko (estado de sensores, distancia, eventos de piso)
- **Recibe comandos de:** kiosko (iniciar calibración, configurar nivel de piso)

**Características especiales:**
- Calibración automática para determinar el nivel del piso
- Detección de eventos (cuando la cabina llega al piso)
- Funcionamiento autónomo: continúa funcionando incluso si hay problemas de comunicación

---

### 2.3. Motor-Control (Control del Motor)

**Tecnología:** ESP-IDF (C/C++) - Firmware embebido para ESP32-S3

**Función Principal:**
Controla el motor que mueve las cabinas verticalmente. Es un módulo simple pero crítico:
- **Control del relé**: Activa o desactiva un relé que controla el motor
- **Respuesta a comandos**: Escucha comandos MQTT para iniciar o detener el motor
- **Sistema global**: Un solo módulo controla el motor para todas las cabinas (el motor mueve todo el sistema)

**Comunicación:**
- **Recibe comandos de:** kiosko (ON para iniciar, OFF para detener)

**Características:**
- Control simple y confiable
- Estado por defecto: motor apagado (seguridad)
- Reconexión automática si se pierde la conexión

---

## 3. Arquitectura de Comunicación

### 3.1. Protocolo MQTT

Todos los módulos se comunican a través de un broker MQTT central. MQTT es un protocolo ligero diseñado para dispositivos IoT, ideal para este tipo de sistemas distribuidos.

**Ventajas:**
- Comunicación asíncrona (los módulos no necesitan estar activos simultáneamente)
- Bajo consumo de recursos
- Mensajes retenidos (el último estado se mantiene disponible)
- Calidad de servicio configurable

### 3.2. Estructura de Topics MQTT

Los topics siguen una estructura jerárquica:

```
parking/
  └── garage-01/                    # Identificador del sitio
      ├── cabina-01/                # Identificador de cada cabina
      │   ├── presence/entry        # Sensor de entrada (IR1)
      │   ├── presence/full         # Sensor completo (IR2)
      │   ├── distance/event        # Eventos de distancia
      │   ├── floor/reached         # Evento: cabina llegó al piso
      │   ├── calibration/complete  # Evento: calibración completada
      │   └── cmd                   # Comandos para la cabina
      ├── cabina-02/
      │   └── ...
      └── motor                     # Comando global del motor (ON/OFF)
```

---

## 4. Flujo de Operación

### 4.1. Almacenamiento de un Vehículo

1. **Detección inicial**: 
   - El sensor IR1 de la cabina activa detecta que un vehículo está entrando
   - cabina-firmware publica el evento vía MQTT
   - kiosko recibe la notificación y actualiza la interfaz

2. **Confirmación de entrada completa**:
   - El sensor IR2 detecta que el vehículo está completamente dentro
   - cabina-firmware publica el evento
   - kiosko muestra que el vehículo está listo para ser guardado

3. **Procesamiento del ticket**:
   - El operador confirma el almacenamiento en kiosko
   - kiosko genera un ticket único con código QR
   - Se asigna la cabina actual al vehículo
   - Se imprime el ticket de entrada

4. **Preparación de la siguiente cabina**:
   - kiosko identifica la siguiente cabina libre
   - kiosko envía comando "ON" al topic del motor
   - motor-control activa el relé y el motor comienza a mover las cabinas
   - kiosko monitorea la distancia de la cabina objetivo

5. **Llegada al piso**:
   - cabina-firmware detecta que la cabina objetivo llegó al nivel del piso
   - Publica evento "floor/reached" vía MQTT
   - kiosko recibe el evento y envía comando "OFF" al motor
   - motor-control desactiva el relé y el motor se detiene
   - La nueva cabina está lista para recibir el siguiente vehículo

### 4.2. Recuperación de un Vehículo

1. **Lectura del ticket**:
   - El operador escanea el código QR del ticket en kiosko
   - kiosko identifica la cabina donde está el vehículo

2. **Movimiento de la cabina**:
   - kiosko envía comando "ON" al motor
   - El motor mueve las cabinas hasta que la cabina objetivo llega al piso
   - cabina-firmware detecta la llegada y publica el evento
   - kiosko detiene el motor

3. **Salida del vehículo**:
   - El operador confirma la salida
   - kiosko actualiza el estado del ticket
   - Se imprime el ticket de salida (opcional)
   - La cabina queda disponible para el siguiente vehículo

### 4.3. Calibración del Sistema

1. **Inicio de calibración**:
   - El operador inicia la calibración desde kiosko
   - kiosko envía comando de calibración a la cabina específica
   - cabina-firmware inicia el proceso de calibración

2. **Proceso de calibración**:
   - El motor se activa y la cabina realiza 2 rotaciones completas
   - cabina-firmware mide la distancia mínima durante el proceso
   - Esta distancia mínima se guarda como el "nivel del piso"

3. **Finalización**:
   - cabina-firmware publica evento "calibration/complete" con el nivel del piso
   - kiosko recibe el evento y actualiza la configuración
   - El sistema está listo para operar con la nueva calibración

---

## 5. Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                        BROKER MQTT                          │
│                  (Comunicación Central)                     │
└─────────────────────────────────────────────────────────────┘
         ▲                ▲                ▲
         │                │                │
         │                │                │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │         │      │         │      │         │
    │ KIOSKO  │      │ CABINA- │      │ MOTOR-  │
    │         │      │ FIRMWARE│      │ CONTROL │
    │         │      │         │      │         │
    └────┬────┘      └────┬────┘      └────┬────┘
         │                │                │
         │                │                │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │         │      │         │      │         │
    │  Web    │      │ Sensores│      │  Relé   │
    │  UI     │      │ IR1/IR2 │      │  Motor  │
    │         │      │         │      │         │
    │  DB     │      │ Sensor  │      │         │
    │ SQLite  │      │Distancia│      │         │
    │         │      │VL53L0X  │      │         │
    │Printer  │      │         │      │         │
    └─────────┘      └─────────┘      └─────────┘
```

---

## 6. Responsabilidades por Módulo

### 6.1. Kiosko
- ✅ Toma decisiones de negocio (qué cabina usar)
- ✅ Gestiona persistencia de datos (tickets, vehículos)
- ✅ Proporciona interfaz de usuario
- ✅ Coordina el movimiento de cabinas
- ✅ Monitorea el estado del sistema completo

### 6.2. Cabina-Firmware
- ✅ Lectura de sensores físicos
- ✅ Publicación de datos en tiempo real
- ✅ Detección de eventos (llegada al piso)
- ✅ Calibración del nivel del piso
- ❌ NO toma decisiones de negocio
- ❌ NO controla el motor directamente

### 6.3. Motor-Control
- ✅ Control físico del motor (relé)
- ✅ Respuesta a comandos simples (ON/OFF)
- ❌ NO toma decisiones
- ❌ NO monitorea sensores

---

## 7. Ventajas de esta Arquitectura

### 7.1. Modularidad
Cada módulo tiene responsabilidades claras y puede desarrollarse, probarse y mantenerse independientemente.

### 7.2. Escalabilidad
- Fácil agregar más cabinas (solo agregar más módulos cabina-firmware)
- El sistema puede crecer sin modificar el código existente

### 7.3. Robustez
- Si un módulo falla, los otros continúan funcionando
- Los sensores siguen reportando datos incluso si kiosko está temporalmente desconectado
- Los mensajes MQTT retenidos permiten recuperar el estado al reconectar

### 7.4. Mantenibilidad
- Código organizado por responsabilidades
- Fácil identificar dónde hacer cambios
- Testing independiente de cada módulo

### 7.5. Flexibilidad
- Fácil cambiar la lógica de negocio en kiosko sin tocar el firmware
- Los sensores pueden mejorarse sin afectar el resto del sistema
- Nuevas funcionalidades se pueden agregar como nuevos módulos

---

## 8. Tecnologías Utilizadas

| Módulo | Lenguaje | Framework/Plataforma | Hardware |
|--------|----------|---------------------|----------|
| **kiosko** | Python 3.10+ | Flask, SQLite, paho-mqtt | Raspberry Pi / PC |
| **cabina-firmware** | C/C++ | ESP-IDF | ESP32 |
| **motor-control** | C/C++ | ESP-IDF | ESP32-S3 |

---

## 9. Consideraciones de Seguridad

- **MQTT**: Soporta autenticación por usuario/contraseña
- **Red local**: Todos los dispositivos están en la misma red local
- **Base de datos**: SQLite local, no expuesta a la red
- **Comandos críticos**: El motor solo se activa con comandos explícitos de kiosko

---

## 10. Resumen

El sistema de estacionamiento vertical utiliza una arquitectura distribuida donde:

- **kiosko** actúa como el coordinador central, tomando decisiones y gestionando la interfaz de usuario
- **cabina-firmware** proporciona los "sentidos" del sistema, detectando vehículos y posición
- **motor-control** ejecuta las acciones físicas, controlando el motor

La comunicación MQTT permite que estos módulos trabajen juntos de forma asíncrona y robusta, creando un sistema escalable y mantenible para la gestión automatizada de estacionamiento vertical.
