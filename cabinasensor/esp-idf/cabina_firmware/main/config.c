#include "config.h"
#include "esp_mac.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "sdkconfig.h"
#include "esp_log.h"
#include <stdio.h>
#include <string.h>

static const char *TAG = "config";
static const char *NVS_NAMESPACE = "cabina";

static void derive_device_id(char out[32]) {
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(out, 32, "esp-%02X%02X%02X", mac[3], mac[4], mac[5]);
}

// Read string from NVS, return true if found
static bool cabina_nvs_get_str(nvs_handle_t nvs, const char *key, char *out, size_t max_len, const char *default_val) {
    size_t required_size = max_len;
    esp_err_t err = nvs_get_str(nvs, key, out, &required_size);
    if (err == ESP_OK) {
        return true;
    }
    if (default_val) {
        strncpy(out, default_val, max_len - 1);
        out[max_len - 1] = '\0';
    }
    return false;
}

// Read uint32 from NVS, return true if found
static bool cabina_nvs_get_u32(nvs_handle_t nvs, const char *key, uint32_t *out, uint32_t default_val) {
    esp_err_t err = nvs_get_u32(nvs, key, out);
    if (err == ESP_OK) {
        return true;
    }
    *out = default_val;
    return false;
}

// Read bool from NVS, return true if found
static bool cabina_nvs_get_u8(nvs_handle_t nvs, const char *key, bool *out, bool default_val) {
    uint8_t val = 0;
    esp_err_t err = nvs_get_u8(nvs, key, &val);
    if (err == ESP_OK) {
        *out = (val != 0);
        return true;
    }
    *out = default_val;
    return false;
}

// Static buffers for NVS-loaded strings (since config struct uses const char*)
static char g_wifi_ssid[64];
static char g_wifi_password[64];
static char g_mqtt_broker[128];
static char g_mqtt_user[64];
static char g_mqtt_password[64];
static char g_topic_base[64];
static char g_site_id[64];

void cabina_load_config(cabina_config_t *out) {
    memset(out, 0, sizeof(*out));
    memset(g_wifi_ssid, 0, sizeof(g_wifi_ssid));
    memset(g_wifi_password, 0, sizeof(g_wifi_password));
    memset(g_mqtt_broker, 0, sizeof(g_mqtt_broker));
    memset(g_mqtt_user, 0, sizeof(g_mqtt_user));
    memset(g_mqtt_password, 0, sizeof(g_mqtt_password));
    memset(g_topic_base, 0, sizeof(g_topic_base));
    memset(g_site_id, 0, sizeof(g_site_id));

    // Open NVS namespace
    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs);
    bool nvs_available = (err == ESP_OK);

    // Load from NVS with Kconfig defaults as fallback
    if (nvs_available) {
        cabina_nvs_get_str(nvs, "wifi_ssid", g_wifi_ssid, sizeof(g_wifi_ssid), CONFIG_CABINA_WIFI_SSID);
        cabina_nvs_get_str(nvs, "wifi_pass", g_wifi_password, sizeof(g_wifi_password), CONFIG_CABINA_WIFI_PASSWORD);
        cabina_nvs_get_str(nvs, "mqtt_broker", g_mqtt_broker, sizeof(g_mqtt_broker), CONFIG_CABINA_MQTT_BROKER);
        cabina_nvs_get_str(nvs, "mqtt_user", g_mqtt_user, sizeof(g_mqtt_user), CONFIG_CABINA_MQTT_USER);
        cabina_nvs_get_str(nvs, "mqtt_pass", g_mqtt_password, sizeof(g_mqtt_password), CONFIG_CABINA_MQTT_PASSWORD);
        cabina_nvs_get_str(nvs, "topic_base", g_topic_base, sizeof(g_topic_base), CONFIG_CABINA_TOPIC_BASE);
        cabina_nvs_get_str(nvs, "site_id", g_site_id, sizeof(g_site_id), CONFIG_CABINA_SITE_ID);
        
        uint32_t port = CONFIG_CABINA_MQTT_PORT;
        cabina_nvs_get_u32(nvs, "mqtt_port", &port, CONFIG_CABINA_MQTT_PORT);
        out->mqtt_port = (uint16_t)port;
        
        cabina_nvs_get_u32(nvs, "pub_interval", &out->pub_interval_sec, CONFIG_CABINA_PUB_INTERVAL_SEC);
        cabina_nvs_get_u32(nvs, "sample_period", &out->sample_period_ms, CONFIG_CABINA_SAMPLE_PERIOD_MS);
        
        cabina_nvs_get_u8(nvs, "presence_retain", &out->presence_retain, CONFIG_CABINA_PRESENCE_RETAIN);
        cabina_nvs_get_u8(nvs, "ir_pullups", &out->ir_pullups, CONFIG_CABINA_IR_PULLUPS);
        
        nvs_close(nvs);
        ESP_LOGI(TAG, "Config loaded from NVS");
    } else {
        // Use Kconfig defaults
        strncpy(g_wifi_ssid, CONFIG_CABINA_WIFI_SSID, sizeof(g_wifi_ssid) - 1);
        strncpy(g_wifi_password, CONFIG_CABINA_WIFI_PASSWORD, sizeof(g_wifi_password) - 1);
        strncpy(g_mqtt_broker, CONFIG_CABINA_MQTT_BROKER, sizeof(g_mqtt_broker) - 1);
        strncpy(g_mqtt_user, CONFIG_CABINA_MQTT_USER, sizeof(g_mqtt_user) - 1);
        strncpy(g_mqtt_password, CONFIG_CABINA_MQTT_PASSWORD, sizeof(g_mqtt_password) - 1);
        strncpy(g_topic_base, CONFIG_CABINA_TOPIC_BASE, sizeof(g_topic_base) - 1);
        strncpy(g_site_id, CONFIG_CABINA_SITE_ID, sizeof(g_site_id) - 1);
        out->mqtt_port = CONFIG_CABINA_MQTT_PORT;
        out->pub_interval_sec = CONFIG_CABINA_PUB_INTERVAL_SEC;
        out->sample_period_ms = CONFIG_CABINA_SAMPLE_PERIOD_MS;
        out->presence_retain = CONFIG_CABINA_PRESENCE_RETAIN;
        out->ir_pullups = CONFIG_CABINA_IR_PULLUPS;
        ESP_LOGI(TAG, "Config loaded from Kconfig defaults");
    }

    out->wifi_ssid      = g_wifi_ssid;
    out->wifi_password  = g_wifi_password;
    out->mqtt_broker    = g_mqtt_broker;
    out->mqtt_user      = g_mqtt_user[0] ? g_mqtt_user : NULL;
    out->mqtt_password  = g_mqtt_password[0] ? g_mqtt_password : NULL;
    out->topic_base     = g_topic_base;
    out->site_id        = g_site_id;

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


