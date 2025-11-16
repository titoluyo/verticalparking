#include "hw_sensors.h"
#include "driver/gpio.h"
#include "driver/i2c.h"
#include "esp_check.h"
#include "esp_log.h"

static const char *TAG = "sensors";
static cabina_config_t g_cfg;
static bool g_inited = false;

// I2C config
#define I2C_PORT I2C_NUM_0
#define I2C_FREQ_HZ 100000

static esp_err_t i2c_bus_init(int sda, int scl) {
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = sda,
        .scl_io_num = scl,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_FREQ_HZ,
    };
    ESP_RETURN_ON_ERROR(i2c_param_config(I2C_PORT, &conf), TAG, "i2c_param_config");
    ESP_RETURN_ON_ERROR(i2c_driver_install(I2C_PORT, I2C_MODE_MASTER, 0, 0, 0), TAG, "i2c_driver_install");
    return ESP_OK;
}

static void gpio_init_ir(int pin, bool pullup) {
    gpio_config_t io_conf = {
        .pin_bit_mask = 1ULL << pin,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = pullup ? GPIO_PULLUP_ENABLE : GPIO_PULLUP_DISABLE,
        .pull_down_en = pullup ? GPIO_PULLDOWN_DISABLE : GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
}

void sensors_init(const cabina_config_t *cfg) {
    g_cfg = *cfg;
    gpio_init_ir(g_cfg.gpio_ir1, g_cfg.ir_pullups);
    gpio_init_ir(g_cfg.gpio_ir2, g_cfg.ir_pullups);
    if (i2c_bus_init(g_cfg.i2c_sda, g_cfg.i2c_scl) == ESP_OK) {
        ESP_LOGI(TAG, "I2C initialized on SDA=%d SCL=%d", g_cfg.i2c_sda, g_cfg.i2c_scl);
    } else {
        ESP_LOGW(TAG, "I2C init failed");
    }
    g_inited = true;
}

static bool read_ir_level(int pin, bool pullups) {
    int level = gpio_get_level(pin);
    // CircuitPython version: true when detecting something. If using pull-ups, raw high means present.
    if (pullups) {
        return level ? true : false;
    } else {
        return level ? false : true;
    }
}

// Placeholder VL53L0X read: returns -1 until driver integrated
static int vl53l0x_read_mm(void) {
    return -1;
}

void sensors_read(sensor_snapshot_t *out) {
    if (!g_inited) {
        out->ir1_present = false;
        out->ir2_present = false;
        out->distance_mm = -1;
        return;
    }
    out->ir1_present = read_ir_level(g_cfg.gpio_ir1, g_cfg.ir_pullups);
    out->ir2_present = read_ir_level(g_cfg.gpio_ir2, g_cfg.ir_pullups);
    out->distance_mm = vl53l0x_read_mm();
}

void sensors_deinit(void) {
    i2c_driver_delete(I2C_PORT);
    g_inited = false;
}


