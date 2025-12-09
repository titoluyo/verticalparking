#include "sdkconfig.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "wifi_client.h"
#include "i2c_bus.h"
#include "ir_sensors.h"
#include "mqtt_wrapper.h"
#include "vl53l0x.h"
#include "edge_detect.h"
#include "telemetry.h"
#include "calibration.h"
#include "ota_update.h"
#include <cstdio>
#include <cstring>

static const char *TAG = "cabina_firmware";

// Global calibration state
static calibration_state_t g_calibration_state;
static bool g_floor_detected_last = false;  // Track floor detection state for edge detection
static i2c_port_t g_i2c_port = I2C_NUM_0;  // Store I2C port for callback

// OTA topics (static for callback access)
static char g_topic_ota_update[160];
static char g_topic_ota_status[160];
static char g_topic_ota_version[160];

// OTA progress callback - publishes status to MQTT
static void ota_progress_callback(ota_status_t status, int progress, const char *message) {
    // Check that topic is initialized (not empty) and MQTT is connected
    if (g_topic_ota_status[0] != '\0' && mqtt_client_is_connected()) {
        char json_buf[256];
        if (ota_update_json_status(json_buf, sizeof(json_buf)) > 0) {
            mqtt_client_publish_json(g_topic_ota_status, json_buf, 1, false);
        }
    }
}

// Command handler function
static void handle_mqtt_command(const char *topic, const char *data, int data_len) {
    // Check if this is a command topic
    char expected_cmd_topic[160];
    snprintf(expected_cmd_topic, sizeof(expected_cmd_topic), "%s/%s/%s/cmd",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    
    // Check for OTA update command topic
    if (strcmp(topic, g_topic_ota_update) == 0) {
        ESP_LOGI(TAG, "Received OTA update command");
        esp_err_t err = ota_update_handle_mqtt_command(data, data_len);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to handle OTA command: %s", esp_err_to_name(err));
        }
        return;
    }
    
    if (strcmp(topic, expected_cmd_topic) != 0) {
        return;
    }
    
    // Simple JSON parsing for commands
    // Look for "start_calibration": true or "stop_calibration": true or "set_floor_level": <value>
    // or OTA commands: "ota_update": {"url": "..."} 
    if (strstr(data, "\"start_calibration\"") != NULL && strstr(data, "true") != NULL) {
        // Get current distance to start calibration
        int current_dist = vl53l0x_read_range_mm(g_i2c_port);
        if (current_dist >= 0) {
            calibration_start(&g_calibration_state, current_dist);
            ESP_LOGI(TAG, "Calibration started via MQTT command (initial distance: %d mm)", current_dist);
        } else {
            ESP_LOGW(TAG, "Cannot start calibration: invalid distance reading");
        }
    } else if (strstr(data, "\"stop_calibration\"") != NULL && strstr(data, "true") != NULL) {
        calibration_stop(&g_calibration_state);
        ESP_LOGI(TAG, "Calibration stopped via MQTT command");
    } else if (strstr(data, "\"set_floor_level\"") != NULL) {
        // Parse: {"set_floor_level": 450}
        int floor_level = 0;
        if (sscanf(data, "{\"set_floor_level\": %d}", &floor_level) == 1 && floor_level > 0) {
            calibration_save_floor_level(&g_calibration_state, floor_level);
            ESP_LOGI(TAG, "Floor level set via MQTT command: %d mm", floor_level);
        } else {
            ESP_LOGW(TAG, "Invalid set_floor_level command format or value");
        }
    } else if (strstr(data, "\"ota_update\"") != NULL || strstr(data, "\"url\"") != NULL) {
        // OTA update command via general cmd topic (alternative format)
        ESP_LOGI(TAG, "Received OTA update command via cmd topic");
        esp_err_t err = ota_update_handle_mqtt_command(data, data_len);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to handle OTA command: %s", esp_err_to_name(err));
        }
    }
}

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "Cabina Firmware Starting");
    ESP_LOGI(TAG, "Firmware version: %s", ota_update_get_current_version());

    // Initialize NVS (required for WiFi)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Build OTA topics FIRST, before any OTA initialization.
    // This ensures g_topic_ota_status is valid before ota_update_init() runs,
    // which may trigger rollback handling that invokes the progress callback.
    // The callback publishes to g_topic_ota_status, so it must be initialized first.
    snprintf(g_topic_ota_update, sizeof(g_topic_ota_update), "%s/%s/%s/ota/update",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    snprintf(g_topic_ota_status, sizeof(g_topic_ota_status), "%s/%s/%s/ota/status",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    snprintf(g_topic_ota_version, sizeof(g_topic_ota_version), "%s/%s/%s/ota/version",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);

    // Set OTA progress callback BEFORE ota_update_init() so any status
    // updates during initialization (e.g., rollback detection) are captured.
    // Topics are already initialized above, so the callback can safely publish.
    ota_update_set_callback(ota_progress_callback);

    // Initialize OTA subsystem (checks for pending validation, may trigger rollback)
    if (ota_update_init() != ESP_OK) {
        ESP_LOGW(TAG, "OTA subsystem initialization failed - continuing without OTA support");
    }

    // Initialize WiFi
    if (wifi_client_init() != ESP_OK) {
        ESP_LOGE(TAG, "WiFi initialization failed");
        // If we're pending OTA validation and WiFi fails, rollback
        if (ota_update_is_pending_validation()) {
            ESP_LOGE(TAG, "WiFi failed after OTA - initiating rollback");
            ota_update_rollback();
        }
        return;
    }

    char ip_str[16];
    if (wifi_client_get_ip(ip_str, sizeof(ip_str)) == ESP_OK) {
        ESP_LOGI(TAG, "WiFi connected with IP: %s", ip_str);
    }

    // Initialize MQTT client
    if (mqtt_client_init() != ESP_OK) {
        ESP_LOGE(TAG, "MQTT client initialization failed");
        // If we're pending OTA validation and MQTT fails, rollback
        if (ota_update_is_pending_validation()) {
            ESP_LOGE(TAG, "MQTT failed after OTA - initiating rollback");
            ota_update_rollback();
        }
        // Continue anyway - sensors can still work without MQTT
    } else {
        ESP_LOGI(TAG, "MQTT client initialized, waiting for connection...");
        // Wait a bit for MQTT to connect
        vTaskDelay(pdMS_TO_TICKS(2000));
    }

    // Initialize IR sensors
    if (ir_sensors_init(CONFIG_EXAMPLE_IR1_GPIO, 
                        CONFIG_EXAMPLE_IR2_GPIO, 
                        CONFIG_EXAMPLE_IR_PULLUPS) != ESP_OK) {
        ESP_LOGE(TAG, "IR sensors initialization failed");
        return;
    }

    // Initialize I2C bus
    g_i2c_port = I2C_NUM_0;
    if (i2c_bus_init(g_i2c_port, 
                     CONFIG_EXAMPLE_I2C_SDA_GPIO, 
                     CONFIG_EXAMPLE_I2C_SCL_GPIO, 
                     CONFIG_EXAMPLE_I2C_CLOCK_SPEED_HZ) != ESP_OK) {
        ESP_LOGE(TAG, "I2C bus initialization failed");
        return;
    }

    // Initialize VL53L0X sensor
    if (vl53l0x_init(g_i2c_port) != VL53L0X_OK) {
        ESP_LOGE(TAG, "VL53L0X initialization failed");
        i2c_bus_deinit(g_i2c_port);
        return;
    }

    ESP_LOGI(TAG, "VL53L0X initialized successfully");
    ESP_LOGI(TAG, "Starting sensor measurements...");
    printf("time (s), distance (mm), ir1, ir2\n");

    // Initialize edge detection
    edge_state_t edge_state;
    edge_detect_init(&edge_state);

    // Initialize calibration
    calibration_init(&g_calibration_state);

    // Build MQTT topics
    char topic_ir1[160], topic_ir2[160], topic_dist[160], topic_stat[160];
    char topic_cmd[160], topic_calib[160], topic_floor[160];
    telemetry_build_topics(topic_ir1, sizeof(topic_ir1),
                          topic_ir2, sizeof(topic_ir2),
                          topic_dist, sizeof(topic_dist),
                          topic_stat, sizeof(topic_stat));
    
    // Build calibration and floor topics
    snprintf(topic_cmd, sizeof(topic_cmd), "%s/%s/%s/cmd",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    snprintf(topic_calib, sizeof(topic_calib), "%s/%s/%s/calibration/complete",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    snprintf(topic_floor, sizeof(topic_floor), "%s/%s/%s/floor/reached",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    
    // Set up MQTT message callback for commands
    mqtt_client_set_message_callback(handle_mqtt_command);
    
    // Subscribe to command topic when MQTT connects (retry if not connected yet)
    int retry_count = 0;
    while (!mqtt_client_is_connected() && retry_count < 10) {
        vTaskDelay(pdMS_TO_TICKS(500));
        retry_count++;
    }
    
    if (mqtt_client_is_connected()) {
        mqtt_client_subscribe(topic_cmd, 1);
        ESP_LOGI(TAG, "Subscribed to command topic: %s", topic_cmd);
        
        // Subscribe to OTA update topic
        mqtt_client_subscribe(g_topic_ota_update, 1);
        ESP_LOGI(TAG, "Subscribed to OTA topic: %s", g_topic_ota_update);
    } else {
        ESP_LOGW(TAG, "MQTT not connected, will subscribe when connected");
    }

    // Publish online status if MQTT is connected
    if (mqtt_client_is_connected()) {
        char status_json[192];
        if (telemetry_json_status(status_json, sizeof(status_json)) > 0) {
            mqtt_client_publish_json(topic_stat, status_json, 1, true);
        }
        
        // Publish firmware version on boot
        #ifdef CONFIG_EXAMPLE_OTA_VERSION_PUBLISH_ON_BOOT
        char version_json[256];
        if (ota_update_json_version(version_json, sizeof(version_json)) > 0) {
            mqtt_client_publish_json(g_topic_ota_version, version_json, 1, true);
            ESP_LOGI(TAG, "Published firmware version to: %s", g_topic_ota_version);
        }
        #endif
    }
    
    // Mark firmware as valid if auto-validate is enabled and we're pending validation
    #ifdef CONFIG_EXAMPLE_OTA_AUTO_VALIDATE
    if (ota_update_is_pending_validation()) {
        ESP_LOGI(TAG, "Auto-validating firmware after successful initialization");
        if (ota_update_mark_valid() == ESP_OK) {
            ESP_LOGI(TAG, "Firmware validated successfully - rollback cancelled");
        }
    }
    #endif

    // Main measurement loop
    int64_t start_time = esp_timer_get_time();
    int64_t last_status_publish_ms = 0;
    const int64_t status_interval_ms = (int64_t)CONFIG_EXAMPLE_STATUS_INTERVAL_SEC * 1000;
    
    // Subscribe to command topic if MQTT just connected
    bool subscribed_to_cmd = false;
    bool subscribed_to_ota = false;
    
    while (true) {
        // Check if MQTT just connected and subscribe to command topics
        if (mqtt_client_is_connected() && !subscribed_to_cmd) {
            mqtt_client_subscribe(topic_cmd, 1);
            ESP_LOGI(TAG, "Subscribed to command topic: %s", topic_cmd);
            subscribed_to_cmd = true;
        } else if (!mqtt_client_is_connected() && subscribed_to_cmd) {
            subscribed_to_cmd = false;  // Reset if disconnected
        }
        
        // Subscribe to OTA topic on reconnect
        if (mqtt_client_is_connected() && !subscribed_to_ota) {
            mqtt_client_subscribe(g_topic_ota_update, 1);
            ESP_LOGI(TAG, "Subscribed to OTA topic: %s", g_topic_ota_update);
            subscribed_to_ota = true;
            
            // Re-publish version on reconnect
            #ifdef CONFIG_EXAMPLE_OTA_VERSION_PUBLISH_ON_BOOT
            char version_json[256];
            if (ota_update_json_version(version_json, sizeof(version_json)) > 0) {
                mqtt_client_publish_json(g_topic_ota_version, version_json, 1, true);
            }
            #endif
        } else if (!mqtt_client_is_connected() && subscribed_to_ota) {
            subscribed_to_ota = false;  // Reset if disconnected
        }
        
        int distance_mm = vl53l0x_read_range_mm(g_i2c_port);
        ir_sensors_state_t ir_state;
        ir_sensors_read(&ir_state);
        
        int64_t now_ms = esp_timer_get_time() / 1000;
        float elapsed = (float)(esp_timer_get_time() - start_time) / 1e6f;
        
        // Print to console
        if (distance_mm >= 0) {
            printf("%.3f, %d, %d, %d\n", elapsed, distance_mm, 
                   ir_state.ir1_present ? 1 : 0, 
                   ir_state.ir2_present ? 1 : 0);
        } else {
            printf("%.3f, -1, %d, %d\n", elapsed,
                   ir_state.ir1_present ? 1 : 0, 
                   ir_state.ir2_present ? 1 : 0);
            ESP_LOGW(TAG, "Failed to read distance");
        }

        // Process calibration if active
        if (g_calibration_state.active && distance_mm >= 0) {
            bool calib_complete = calibration_process_sample(&g_calibration_state, distance_mm);
            
            if (calib_complete) {
                // Calibration complete - publish event
                if (mqtt_client_is_connected()) {
                    char calib_json[512];
                    int json_len = telemetry_json_calibration_complete(
                        g_calibration_state.floor_level,
                        2,  // calibration_rounds
                        g_calibration_state.min_distance_tracked,
                        g_calibration_state.max_distance_tracked,
                        calib_json, sizeof(calib_json));
                    
                    if (json_len > 0) {
                        mqtt_client_publish_json(topic_calib, calib_json, 1, false);
                        ESP_LOGI(TAG, "Published calibration_complete event: floor_level=%d mm",
                                g_calibration_state.floor_level);
                    }
                }
            }
        }
        
        // Check for floor detection during normal operation (not calibrating)
        bool is_at_floor = false;
        if (!g_calibration_state.active && distance_mm >= 0 && g_calibration_state.floor_level_valid) {
            is_at_floor = calibration_is_at_floor(&g_calibration_state, distance_mm);
            
            // Detect edge: transition TO floor (not already at floor)
            if (is_at_floor && !g_floor_detected_last) {
                // Just reached floor - publish event
                if (mqtt_client_is_connected()) {
                    char floor_json[256];
                    int json_len = telemetry_json_floor_reached(
                        distance_mm,
                        g_calibration_state.floor_level,
                        floor_json, sizeof(floor_json));
                    
                    if (json_len > 0) {
                        mqtt_client_publish_json(topic_floor, floor_json, 1, false);
                        ESP_LOGI(TAG, "Published floor/reached event: distance=%d mm, floor_level=%d mm",
                                distance_mm, g_calibration_state.floor_level);
                    }
                }
            }
            
            g_floor_detected_last = is_at_floor;
        }

        // Create sensor snapshot
        sensor_snapshot_t snap;
        snap.ir1_present = ir_state.ir1_present;
        snap.ir2_present = ir_state.ir2_present;
        snap.distance_mm = distance_mm;

        // Process through edge detection
        edge_event_t events[4];
        int event_count = edge_detect_process(&edge_state, &snap, 
                                             CONFIG_EXAMPLE_DISTANCE_THRESHOLD_MM,
                                             events, 4);

        // Publish detected events to MQTT
        if (mqtt_client_is_connected() && event_count > 0) {
            for (int i = 0; i < event_count; i++) {
                char json_buf[256];
                int json_len = 0;

                switch (events[i].type) {
                    case EV_IR1:
                        json_len = telemetry_json_presence("ir1", events[i].present, 
                                                          json_buf, sizeof(json_buf));
                        if (json_len > 0) {
                            mqtt_client_publish_json(topic_ir1, json_buf, 1, 
                                                    CONFIG_EXAMPLE_PRESENCE_RETAIN);
                            ESP_LOGI(TAG, "Published IR1 event: present=%s", 
                                    events[i].present ? "true" : "false");
                        }
                        break;

                    case EV_IR2:
                        json_len = telemetry_json_presence("ir2", events[i].present, 
                                                          json_buf, sizeof(json_buf));
                        if (json_len > 0) {
                            mqtt_client_publish_json(topic_ir2, json_buf, 1, 
                                                    CONFIG_EXAMPLE_PRESENCE_RETAIN);
                            ESP_LOGI(TAG, "Published IR2 event: present=%s", 
                                    events[i].present ? "true" : "false");
                        }
                        break;

                    case EV_DISTANCE:
                        json_len = telemetry_json_distance(events[i].dist.from_mm, 
                                                          events[i].dist.to_mm,
                                                          json_buf, sizeof(json_buf));
                        if (json_len > 0) {
                            mqtt_client_publish_json(topic_dist, json_buf, 0, false);
                            ESP_LOGI(TAG, "Published distance event: %d mm -> %d mm", 
                                    events[i].dist.from_mm, events[i].dist.to_mm);
                        }
                        break;

                    case EV_NONE:
                    default:
                        break;
                }
            }
        }

        // Publish status heartbeat periodically
        if (mqtt_client_is_connected() && 
            (now_ms - last_status_publish_ms) >= status_interval_ms) {
            char status_json[192];
            if (telemetry_json_status(status_json, sizeof(status_json)) > 0) {
                mqtt_client_publish_json(topic_stat, status_json, 1, true);
                last_status_publish_ms = now_ms;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(50)); // 50ms between readings
    }
}

