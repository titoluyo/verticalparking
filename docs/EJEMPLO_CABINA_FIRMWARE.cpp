// cabina-firmware/main/main.cpp - Extracto relevante
// Muestra: Loop principal que lee sensores, publica datos MQTT, y detecta eventos

void app_main(void) {
    // ... inicialización de WiFi, MQTT, sensores ...
    
    // Loop principal de medición
    while (true) {
        // Lee sensores físicos
        int distance_mm = vl53l0x_read_range_mm(g_i2c_port);  // Sensor de distancia
        ir_sensors_state_t ir_state;
        ir_sensors_read(&ir_state);  // Sensores IR (entrada y completo)
        
        // Procesa calibración si está activa
        if (g_calibration_state.active && distance_mm >= 0) {
            bool calib_complete = calibration_process_sample(&g_calibration_state, distance_mm);
            
            if (calib_complete) {
                // Calibración completada - publica evento
                if (mqtt_client_is_connected()) {
                    char calib_json[512];
                    telemetry_json_calibration_complete(
                        g_calibration_state.floor_level,
                        2,  // calibration_rounds
                        g_calibration_state.min_distance_tracked,
                        g_calibration_state.max_distance_tracked,
                        calib_json, sizeof(calib_json));
                    
                    mqtt_client_publish_json(topic_calib, calib_json, 1, false);
                    ESP_LOGI(TAG, "Published calibration_complete: floor_level=%d mm",
                            g_calibration_state.floor_level);
                }
            }
        }
        
        // Detecta cuando la cabina llega al nivel del piso
        bool is_at_floor = false;
        if (!g_calibration_state.active && distance_mm >= 0 && g_calibration_state.floor_level_valid) {
            is_at_floor = calibration_is_at_floor(&g_calibration_state, distance_mm);
            
            // Detecta transición: llegada AL piso
            if (is_at_floor && !g_floor_detected_last) {
                // Acaba de llegar al piso - publica evento
                if (mqtt_client_is_connected()) {
                    char floor_json[256];
                    telemetry_json_floor_reached(
                        distance_mm,
                        g_calibration_state.floor_level,
                        floor_json, sizeof(floor_json));
                    
                    mqtt_client_publish_json(topic_floor, floor_json, 1, false);
                    ESP_LOGI(TAG, "Published floor/reached event: distance=%d mm, floor_level=%d mm",
                            distance_mm, g_calibration_state.floor_level);
                }
            }
            g_floor_detected_last = is_at_floor;
        }
        
        // Crea snapshot de sensores y detecta eventos (entrada/salida de vehículo)
        sensor_snapshot_t snap;
        snap.ir1_present = ir_state.ir1_present;
        snap.ir2_present = ir_state.ir2_present;
        snap.distance_mm = distance_mm;
        
        // Procesa detección de eventos (cuando un vehículo entra o sale)
        edge_event_t events[4];
        int event_count = edge_detect_process(&edge_state, &snap, 
                                             CONFIG_EXAMPLE_DISTANCE_THRESHOLD_MM,
                                             events, 4);
        
        // Publica eventos detectados a MQTT
        if (mqtt_client_is_connected() && event_count > 0) {
            for (int i = 0; i < event_count; i++) {
                char json_buf[256];
                int json_len = 0;
                
                switch (events[i].type) {
                    case EV_IR1:  // Sensor de entrada
                        json_len = telemetry_json_presence("ir1", events[i].present, 
                                                          json_buf, sizeof(json_buf));
                        if (json_len > 0) {
                            mqtt_client_publish_json(topic_ir1, json_buf, 1, true);
                        }
                        break;
                    case EV_IR2:  // Sensor completo
                        json_len = telemetry_json_presence("ir2", events[i].present, 
                                                          json_buf, sizeof(json_buf));
                        if (json_len > 0) {
                            mqtt_client_publish_json(topic_ir2, json_buf, 1, true);
                        }
                        break;
                    // ... otros eventos ...
                }
            }
        }
        
        vTaskDelay(pdMS_TO_TICKS(100));  // Delay de 100ms entre lecturas
    }
}
