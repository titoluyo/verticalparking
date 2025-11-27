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

    // Publish online status if MQTT is connected
    if (mqtt_client_is_connected()) {
        char status_topic[160];
        mqtt_client_get_topic("status", status_topic, sizeof(status_topic));
        char status_json[192];
        snprintf(status_json, sizeof(status_json),
                 "{\"site\":\"%s\",\"device\":\"%s\",\"status\":\"online\"}",
                 CONFIG_EXAMPLE_MQTT_SITE_ID,
                 CONFIG_EXAMPLE_MQTT_DEVICE_ID);
        mqtt_client_publish_json(status_topic, status_json, 1, true);
    }

    // Main measurement loop
    int64_t start_time = esp_timer_get_time();
    int64_t last_mqtt_publish = 0;
    const int64_t mqtt_publish_interval_us = 10 * 1000000; // 10 seconds
    
    while (true) {
        int distance_mm = vl53l0x_read_range_mm(i2c_port);
        ir_sensors_state_t ir_state;
        ir_sensors_read(&ir_state);
        
        int64_t now = esp_timer_get_time();
        float elapsed = (float)(now - start_time) / 1e6f;
        
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

        // Publish to MQTT periodically (every 10 seconds)
        if (mqtt_client_is_connected() && (now - last_mqtt_publish) >= mqtt_publish_interval_us) {
            char presence_topic[160];
            mqtt_client_get_topic("presence", presence_topic, sizeof(presence_topic));
            
            char presence_json[256];
            snprintf(presence_json, sizeof(presence_json),
                     "{\"site\":\"%s\",\"device\":\"%s\",\"ir1\":%d,\"ir2\":%d,\"distance_mm\":%d}",
                     CONFIG_EXAMPLE_MQTT_SITE_ID,
                     CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                     ir_state.ir1_present ? 1 : 0,
                     ir_state.ir2_present ? 1 : 0,
                     distance_mm);
            
            mqtt_client_publish_json(presence_topic, presence_json, 0, false);
            last_mqtt_publish = now;
        }

        vTaskDelay(pdMS_TO_TICKS(50)); // 50ms between readings
    }
}

