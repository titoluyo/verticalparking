# Diagrama de Eventos - Sistema de Estacionamiento Vertical

Este documento contiene diagramas Mermaid que visualizan el flujo de eventos en el sistema basado en eventos.

---

## 1. Diagrama General de Arquitectura de Eventos

```mermaid
graph TB
    subgraph "MQTT Broker"
        MQTT[MQTT Topics]
    end
    
    subgraph "kiosko"
        K1[PresenceService<br/>Consumidor]
        K2[MotorControlService<br/>Publicador]
        K3[Routes/API<br/>Orquestador]
    end
    
    subgraph "cabina-firmware"
        C1[Sensores IR<br/>IR1, IR2]
        C2[Sensor Distancia<br/>VL53L0X]
        C3[MQTT Publisher<br/>Publicador]
        C4[MQTT Subscriber<br/>Consumidor]
    end
    
    subgraph "motor-control"
        M1[MQTT Subscriber<br/>Consumidor]
        M2[Relé GPIO<br/>Control Físico]
    end
    
    C1 -->|Lee estado| C3
    C2 -->|Lee distancia| C3
    C3 -->|Publica eventos| MQTT
    MQTT -->|Eventos sensores| K1
    K1 -->|Estado actualizado| K3
    K3 -->|Comandos motor| K2
    K2 -->|Publica ON/OFF| MQTT
    MQTT -->|Comandos motor| M1
    M1 -->|Controla| M2
    
    MQTT -->|Comandos calibración| C4
    C4 -->|Inicia calibración| C2
    C3 -->|Evento calibración| MQTT
    MQTT -->|Calibración completa| K1
```

---

## 2. Flujo: Almacenamiento de Vehículo

```mermaid
sequenceDiagram
    participant U as Usuario
    participant K as kiosko
    participant MQTT as MQTT Broker
    participant CF as cabina-firmware
    participant MC as motor-control
    participant DB as Base de Datos
    
    Note over U,DB: Fase 1: Confirmación y Asignación
    U->>K: POST /guardar (confirmar)
    K->>DB: Crear ticket, asignar cabina actual
    K->>DB: Marcar cabina como 'busy'
    K->>K: Encuentra siguiente cabina libre
    
    Note over U,DB: Fase 2: Iniciar Movimiento
    K->>K: Registra callback para "floor/reached"
    K->>MQTT: Publica "ON" → parking/garage-01/motor
    MQTT->>MC: Comando "ON"
    MC->>MC: Activa relé GPIO
    Note over MC: Motor inicia movimiento
    
    Note over U,DB: Fase 3: Monitoreo y Detección
    loop Cada 100ms
        CF->>CF: Lee sensor distancia
        CF->>CF: Compara con nivel_piso
        alt Distancia <= nivel_piso
            CF->>MQTT: Publica "floor/reached"
            MQTT->>K: Evento "floor/reached"
            K->>K: Ejecuta callback
            K->>MQTT: Publica "OFF" → parking/garage-01/motor
            MQTT->>MC: Comando "OFF"
            MC->>MC: Desactiva relé
            Note over MC: Motor se detiene
            K->>K: Establece nueva cabina como activa
        end
    end
    
    Note over U,DB: Fase 4: Detección de Vehículo
    CF->>CF: Sensor IR1 detecta entrada
    CF->>MQTT: Publica "presence/entry" (present=true)
    MQTT->>K: Evento "presence/entry"
    K->>K: Actualiza estado UI: "transitioning"
    
    CF->>CF: Sensor IR2 detecta completo
    CF->>MQTT: Publica "presence/full" (present=true)
    MQTT->>K: Evento "presence/full"
    K->>K: Actualiza estado UI: "entered"
    K->>U: Muestra confirmación
```

---

## 3. Flujo: Recuperación de Vehículo

```mermaid
sequenceDiagram
    participant U as Usuario
    participant K as kiosko
    participant MQTT as MQTT Broker
    participant CF as cabina-firmware
    participant MC as motor-control
    participant DB as Base de Datos
    
    Note over U,DB: Fase 1: Identificación
    U->>K: POST /recoger (escanea QR)
    K->>DB: Busca ticket por token
    K->>DB: Obtiene cabina_id del vehículo
    
    Note over U,DB: Fase 2: Iniciar Movimiento
    K->>K: Registra callback para "floor/reached" de cabina objetivo
    K->>MQTT: Publica "ON" → parking/garage-01/motor
    MQTT->>MC: Comando "ON"
    MC->>MC: Activa relé GPIO
    Note over MC: Motor inicia movimiento
    
    Note over U,DB: Fase 3: Detección de Llegada
    loop Cada 100ms
        CF->>CF: Lee sensor distancia
        alt Distancia <= nivel_piso
            CF->>MQTT: Publica "floor/reached"
            MQTT->>K: Evento "floor/reached"
            K->>K: Ejecuta callback
            K->>MQTT: Publica "OFF" → parking/garage-01/motor
            MQTT->>MC: Comando "OFF"
            MC->>MC: Desactiva relé
            Note over MC: Motor se detiene
            K->>DB: Marca cabina como 'free'
        end
    end
    
    Note over U,DB: Fase 4: Detección de Salida
    CF->>CF: Sensor IR2 detecta salida
    CF->>MQTT: Publica "presence/full" (present=false)
    MQTT->>K: Evento "presence/full"
    K->>K: Actualiza estado UI: "transitioning"
    
    CF->>CF: Sensor IR1 detecta completamente fuera
    CF->>MQTT: Publica "presence/entry" (present=false)
    MQTT->>K: Evento "presence/entry"
    K->>K: Actualiza estado UI: "free"
    K->>DB: Actualiza ticket como 'completed'
    K->>U: Muestra confirmación
```

---

## 4. Flujo: Calibración del Sistema

```mermaid
sequenceDiagram
    participant U as Usuario
    participant K as kiosko
    participant MQTT as MQTT Broker
    participant CF as cabina-firmware
    participant MC as motor-control
    participant DB as Base de Datos
    
    Note over U,DB: Fase 1: Iniciar Calibración
    U->>K: POST /api/calibration/start (cabin_id)
    K->>MQTT: Publica {"start_calibration": true} → parking/garage-01/cabina-01/cmd
    MQTT->>CF: Comando calibración
    CF->>CF: Inicia proceso de calibración
    CF->>CF: Lee distancia inicial
    
    Note over U,DB: Fase 2: Iniciar Motor
    K->>MQTT: Publica "ON" → parking/garage-01/motor
    MQTT->>MC: Comando "ON"
    MC->>MC: Activa relé
    Note over MC: Motor inicia (2 rotaciones)
    
    Note over U,DB: Fase 3: Proceso de Calibración
    loop Durante 2 rotaciones completas
        CF->>CF: Lee distancia cada 100ms
        CF->>CF: Registra distancia mínima
        CF->>CF: Cuenta rotaciones
    end
    
    Note over U,DB: Fase 4: Completar Calibración
    CF->>CF: Detecta 2 rotaciones completas
    CF->>CF: Calcula nivel_piso = distancia_mínima
    CF->>MQTT: Publica "calibration/complete" con nivel_piso
    MQTT->>K: Evento "calibration/complete"
    K->>K: Ejecuta callback
    K->>MQTT: Publica "OFF" → parking/garage-01/motor
    MQTT->>MC: Comando "OFF"
    MC->>MC: Desactiva relé
    Note over MC: Motor se detiene
    K->>DB: Guarda nivel_piso en base de datos
    K->>U: Muestra confirmación de calibración
```

---

## 5. Flujo: Detección Continua de Sensores

```mermaid
sequenceDiagram
    participant CF as cabina-firmware
    participant MQTT as MQTT Broker
    participant K as kiosko
    participant UI as Interfaz Web
    
    Note over CF,UI: Loop continuo (cada 100ms)
    
    loop Lectura continua de sensores
        CF->>CF: Lee sensor IR1 (entrada)
        CF->>CF: Lee sensor IR2 (completo)
        CF->>CF: Lee sensor distancia VL53L0X
        
        alt IR1 cambió de estado
            CF->>MQTT: Publica "presence/entry" (retained)
            MQTT->>K: Evento "presence/entry"
            K->>K: Actualiza estado interno
            K->>UI: Actualiza UI en tiempo real
        end
        
        alt IR2 cambió de estado
            CF->>MQTT: Publica "presence/full" (retained)
            MQTT->>K: Evento "presence/full"
            K->>K: Actualiza estado interno
            K->>UI: Actualiza UI en tiempo real
        end
        
        alt Distancia cambió significativamente
            CF->>MQTT: Publica "distance/event" (no retained)
            MQTT->>K: Evento "distance/event"
            K->>K: Actualiza distancia en estado
        end
        
        alt Detecta llegada al piso (transición)
            CF->>MQTT: Publica "floor/reached" (no retained)
            MQTT->>K: Evento "floor/reached"
            K->>K: Ejecuta callbacks registrados
        end
    end
```

---

## 6. Diagrama de Estados de una Cabina

```mermaid
stateDiagram-v2
    [*] --> FREE: Inicialización
    
    FREE --> TRANSITIONING: IR1 ON<br/>(Vehículo entrando)
    TRANSITIONING --> ENTERED: IR2 ON<br/>(Vehículo completo)
    ENTERED --> TRANSITIONING: IR2 OFF<br/>(Vehículo saliendo)
    TRANSITIONING --> FREE: IR1 OFF<br/>(Vehículo fuera)
    
    FREE --> MOVING: Comando motor ON<br/>(Moviendo al piso)
    MOVING --> AT_FLOOR: Evento floor/reached<br/>(Llegó al piso)
    AT_FLOOR --> FREE: Cabina lista
    
    note right of FREE
        Estado: Libre
        Sensores: IR1=OFF, IR2=OFF
    end note
    
    note right of TRANSITIONING
        Estado: Transición
        Sensores: IR1=ON, IR2=OFF
        o IR1=OFF, IR2=ON
    end note
    
    note right of ENTERED
        Estado: Ocupada
        Sensores: IR1=ON, IR2=ON
    end note
    
    note right of MOVING
        Estado: Moviéndose
        Motor: ON
        Esperando: floor/reached
    end note
    
    note right of AT_FLOOR
        Estado: En piso
        Motor: OFF
        Lista para recibir vehículo
    end note
```

---

## 7. Diagrama de Topics MQTT

```mermaid
graph TD
    ROOT[parking/]
    
    ROOT --> SITE[garage-01/]
    
    SITE --> MOTOR[motor<br/>Comando: ON/OFF]
    
    SITE --> CAB1[cabina-01/]
    SITE --> CAB2[cabina-02/]
    SITE --> CAB3[cabina-XX/]
    
    CAB1 --> PRES1[presence/]
    CAB1 --> DIST1[distance/]
    CAB1 --> CMD1[cmd/]
    CAB1 --> FLOOR1[floor/reached]
    CAB1 --> CALIB1[calibration/complete]
    
    PRES1 --> ENTRY1[entry<br/>Sensor IR1]
    PRES1 --> FULL1[full<br/>Sensor IR2]
    
    DIST1 --> EVENT1[event<br/>Cambios de distancia]
    
    CMD1 --> CMD_MSG1[Comandos JSON<br/>start_calibration<br/>stop_calibration]
    
    style MOTOR fill:#ff9999
    style ENTRY1 fill:#99ccff
    style FULL1 fill:#99ccff
    style FLOOR1 fill:#99ff99
    style CALIB1 fill:#ffcc99
```

---

## 8. Flujo de Eventos: Vista de Alto Nivel

```mermaid
flowchart LR
    subgraph "Eventos de Entrada"
        E1[Sensor IR1]
        E2[Sensor IR2]
        E3[Sensor Distancia]
        E4[Comando Usuario]
    end
    
    subgraph "Procesamiento"
        P1[cabina-firmware<br/>Detecta eventos]
        P2[kiosko<br/>Orquesta acciones]
        P3[motor-control<br/>Ejecuta comandos]
    end
    
    subgraph "Eventos de Salida"
        S1[MQTT Events]
        S2[Control Motor]
        S3[Actualización UI]
    end
    
    E1 --> P1
    E2 --> P1
    E3 --> P1
    E4 --> P2
    
    P1 -->|Publica eventos| S1
    P2 -->|Envía comandos| P3
    P2 -->|Actualiza| S3
    P3 -->|Controla| S2
    
    S1 -->|Consume| P2
    S2 -->|Afecta| E3
```

---

## Notas sobre los Diagramas

1. **Asincronía**: Todos los eventos son asíncronos - no hay bloqueo entre módulos
2. **MQTT como intermediario**: Todos los eventos pasan por el broker MQTT
3. **Callbacks**: kiosko usa callbacks para reaccionar a eventos específicos
4. **Retención**: Algunos eventos son retenidos (presence), otros no (floor/reached)
5. **Loop continuo**: cabina-firmware lee sensores continuamente y publica eventos

Estos diagramas muestran cómo el sistema funciona completamente basado en eventos, sin comunicación directa entre módulos.
