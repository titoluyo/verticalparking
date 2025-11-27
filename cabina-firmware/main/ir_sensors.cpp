#include "ir_sensors.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "ir_sensors";

static int s_ir1_pin = -1;
static int s_ir2_pin = -1;
static bool s_use_pullups = true;

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

static bool read_ir_level(int pin, bool pullups) {
    int level = gpio_get_level((gpio_num_t)pin);
    // If using pull-ups: high level means presence detected
    // If using pull-downs: low level means presence detected
    if (pullups) {
        return level ? true : false;
    } else {
        return level ? false : true;
    }
}

esp_err_t ir_sensors_init(int ir1_pin, int ir2_pin, bool use_pullups) {
    s_ir1_pin = ir1_pin;
    s_ir2_pin = ir2_pin;
    s_use_pullups = use_pullups;

    ESP_LOGI(TAG, "Initializing IR sensors: IR1=%d, IR2=%d, pullups=%s", 
             ir1_pin, ir2_pin, use_pullups ? "enabled" : "disabled");

    gpio_init_ir(ir1_pin, use_pullups);
    gpio_init_ir(ir2_pin, use_pullups);

    ESP_LOGI(TAG, "IR sensors initialized successfully");
    return ESP_OK;
}

esp_err_t ir_sensors_read(ir_sensors_state_t *state) {
    if (state == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (s_ir1_pin < 0 || s_ir2_pin < 0) {
        ESP_LOGE(TAG, "IR sensors not initialized");
        return ESP_ERR_INVALID_STATE;
    }

    state->ir1_present = read_ir_level(s_ir1_pin, s_use_pullups);
    state->ir2_present = read_ir_level(s_ir2_pin, s_use_pullups);

    return ESP_OK;
}

bool ir_sensors_read_ir1(void) {
    if (s_ir1_pin < 0) {
        return false;
    }
    return read_ir_level(s_ir1_pin, s_use_pullups);
}

bool ir_sensors_read_ir2(void) {
    if (s_ir2_pin < 0) {
        return false;
    }
    return read_ir_level(s_ir2_pin, s_use_pullups);
}

