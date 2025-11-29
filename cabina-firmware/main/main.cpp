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
#include <cstdio>
#include <cstring>

static const char *TAG = "cabina_firmware";

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "Cabina Firmware Starting");

    // Initialize NVS (required for WiFi)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize WiFi
    if (wifi_client_init() != ESP_OK) {
        ESP_LOGE(TAG, "WiFi initialization failed");
        return;
    }

    char ip_str[16];
    if (wifi_client_get_ip(ip_str, sizeof(ip_str)) == ESP_OK) {
        ESP_LOGI(TAG, "WiFi connected with IP: %s", ip_str);
    }

    // Initialize MQTT client
    if (mqtt_client_init() != ESP_OK) {
        ESP_LOGE(TAG, "MQTT client initialization failed");
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
    const i2c_port_t i2c_port = I2C_NUM_0;
    if (i2c_bus_init(i2c_port, 
                     CONFIG_EXAMPLE_I2C_SDA_GPIO, 
                     CONFIG_EXAMPLE_I2C_SCL_GPIO, 
                     CONFIG_EXAMPLE_I2C_CLOCK_SPEED_HZ) != ESP_OK) {
        ESP_LOGE(TAG, "I2C bus initialization failed");
        return;
    }

    // Initialize VL53L0X sensor
    if (vl53l0x_init(i2c_port) != VL53L0X_OK) {
        ESP_LOGE(TAG, "VL53L0X initialization failed");
        i2c_bus_deinit(i2c_port);
        return;
    }

    ESP_LOGI(TAG, "VL53L0X initialized successfully");
    ESP_LOGI(TAG, "Starting sensor measurements...");
    printf("time (s), distance (mm), ir1, ir2\n");

    // Initialize edge detection
    edge_state_t edge_state;
    edge_detect_init(&edge_state);

    // Build MQTT topics
    char topic_ir1[160], topic_ir2[160], topic_dist[160], topic_stat[160];
    telemetry_build_topics(topic_ir1, sizeof(topic_ir1),
                          topic_ir2, sizeof(topic_ir2),
                          topic_dist, sizeof(topic_dist),
                          topic_stat, sizeof(topic_stat));

    // Publish online status if MQTT is connected
    if (mqtt_client_is_connected()) {
        char status_json[192];
        if (telemetry_json_status(status_json, sizeof(status_json)) > 0) {
            mqtt_client_publish_json(topic_stat, status_json, 1, true);
        }
    }

    // Main measurement loop
    int64_t start_time = esp_timer_get_time();
    int64_t last_status_publish_ms = 0;
    const int64_t status_interval_ms = (int64_t)CONFIG_EXAMPLE_STATUS_INTERVAL_SEC * 1000;
    
    while (true) {
        int distance_mm = vl53l0x_read_range_mm(i2c_port);
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

