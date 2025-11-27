#include "sdkconfig.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "vl53l0x.h"
#include <cstdio>

static const char *TAG = "cabina_firmware";

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "Cabina Firmware Starting");

    // I2C configuration
    const i2c_port_t i2c_port = I2C_NUM_0;
    const int i2c_freq_hz = CONFIG_EXAMPLE_I2C_CLOCK_SPEED_HZ;
    const gpio_num_t i2c_sda = (gpio_num_t)CONFIG_EXAMPLE_I2C_SDA_GPIO;
    const gpio_num_t i2c_scl = (gpio_num_t)CONFIG_EXAMPLE_I2C_SCL_GPIO;

    ESP_LOGI(TAG, "I2C Config: SDA=%d, SCL=%d, Speed=%d Hz", i2c_sda, i2c_scl, i2c_freq_hz);

    // Configure I2C
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = i2c_sda,
        .scl_io_num = i2c_scl,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master = {
            .clk_speed = i2c_freq_hz,
        },
        .clk_flags = 0,
    };

    esp_err_t err = i2c_param_config(i2c_port, &conf);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_param_config failed: %s", esp_err_to_name(err));
        return;
    }

    err = i2c_driver_install(i2c_port, I2C_MODE_MASTER, 0, 0, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_driver_install failed: %s", esp_err_to_name(err));
        return;
    }

    ESP_LOGI(TAG, "I2C initialized successfully");

    // Initialize VL53L0X
    if (vl53l0x_init(i2c_port) != VL53L0X_OK) {
        ESP_LOGE(TAG, "VL53L0X initialization failed");
        i2c_driver_delete(i2c_port);
        return;
    }

    ESP_LOGI(TAG, "VL53L0X initialized successfully");
    ESP_LOGI(TAG, "Starting distance measurements...");
    printf("time (s), distance (mm)\n");

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

