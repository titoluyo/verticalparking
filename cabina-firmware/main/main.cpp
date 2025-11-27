#include "sdkconfig.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "wifi_client.h"
#include "i2c_bus.h"
#include "vl53l0x.h"
#include <cstdio>

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
    ESP_LOGI(TAG, "Starting distance measurements...");
    printf("time (s), distance (mm)\n");

    // Main measurement loop
    int64_t start_time = esp_timer_get_time();
    
    while (true) {
        int distance_mm = vl53l0x_read_range_mm(i2c_port);
        
        if (distance_mm >= 0) {
            int64_t now = esp_timer_get_time();
            float elapsed = (float)(now - start_time) / 1e6f;
            printf("%.3f, %d\n", elapsed, distance_mm);
        } else {
            ESP_LOGW(TAG, "Failed to read distance");
        }

        vTaskDelay(pdMS_TO_TICKS(50)); // 50ms between readings
    }
}

