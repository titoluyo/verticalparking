#include "config.h"
#include "esp_mac.h"
#include "esp_system.h"
#include "sdkconfig.h"
#include <stdio.h>
#include <string.h>

static void derive_device_id(char out[32]) {
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(out, 32, "esp-%02X%02X%02X", mac[3], mac[4], mac[5]);
}

void cabina_load_config(cabina_config_t *out) {
    memset(out, 0, sizeof(*out));

    out->wifi_ssid      = CONFIG_CABINA_WIFI_SSID;
    out->wifi_password  = CONFIG_CABINA_WIFI_PASSWORD;
    out->mqtt_broker    = CONFIG_CABINA_MQTT_BROKER;
    out->mqtt_port      = CONFIG_CABINA_MQTT_PORT;
    out->mqtt_user      = CONFIG_CABINA_MQTT_USER[0] ? CONFIG_CABINA_MQTT_USER : NULL;
    out->mqtt_password  = CONFIG_CABINA_MQTT_PASSWORD[0] ? CONFIG_CABINA_MQTT_PASSWORD : NULL;
    out->topic_base     = CONFIG_CABINA_TOPIC_BASE;
    out->site_id        = CONFIG_CABINA_SITE_ID;
    out->presence_retain= CONFIG_CABINA_PRESENCE_RETAIN;
    out->pub_interval_sec = CONFIG_CABINA_PUB_INTERVAL_SEC;
    out->sample_period_ms = CONFIG_CABINA_SAMPLE_PERIOD_MS;
    out->ir_pullups     = CONFIG_CABINA_IR_PULLUPS;

#if CONFIG_IDF_TARGET_ESP32S3
    out->gpio_ir1 = CONFIG_CABINA_S3_IR1_GPIO;
    out->gpio_ir2 = CONFIG_CABINA_S3_IR2_GPIO;
    out->i2c_scl  = CONFIG_CABINA_S3_I2C_SCL;
    out->i2c_sda  = CONFIG_CABINA_S3_I2C_SDA;
#elif CONFIG_IDF_TARGET_ESP32C6
    out->gpio_ir1 = CONFIG_CABINA_C6_IR1_GPIO;
    out->gpio_ir2 = CONFIG_CABINA_C6_IR2_GPIO;
    out->i2c_scl  = CONFIG_CABINA_C6_I2C_SCL;
    out->i2c_sda  = CONFIG_CABINA_C6_I2C_SDA;
#else
#error "Unsupported target"
#endif

    if (CONFIG_CABINA_DEVICE_ID[0]) {
        strncpy(out->device_id, CONFIG_CABINA_DEVICE_ID, sizeof(out->device_id) - 1);
        out->device_id[sizeof(out->device_id) - 1] = '\0';
    } else {
        derive_device_id(out->device_id);
    }
}


