#include "i2c_bus.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "i2c_bus";

esp_err_t i2c_bus_init(i2c_port_t port, int sda_gpio, int scl_gpio, uint32_t freq_hz)
{
    ESP_LOGI(TAG, "Initializing I2C bus: port=%d, SDA=%d, SCL=%d, freq=%lu Hz", 
             port, sda_gpio, scl_gpio, (unsigned long)freq_hz);

    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = (gpio_num_t)sda_gpio,
        .scl_io_num = (gpio_num_t)scl_gpio,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master = {
            .clk_speed = freq_hz,
        },
        .clk_flags = 0,
    };

    esp_err_t err = i2c_param_config(port, &conf);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_param_config failed: %s", esp_err_to_name(err));
        return err;
    }

    err = i2c_driver_install(port, I2C_MODE_MASTER, 0, 0, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_driver_install failed: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "I2C bus initialized successfully");
    return ESP_OK;
}

esp_err_t i2c_bus_deinit(i2c_port_t port)
{
    esp_err_t err = i2c_driver_delete(port);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_driver_delete failed: %s", esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "I2C bus deinitialized");
    return ESP_OK;
}

