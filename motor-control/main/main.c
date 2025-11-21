#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mqtt_client.h"
#include "nvs_flash.h"

static const char *TAG = "motor_control";

static esp_mqtt_client_handle_t s_mqtt_client;
static bool s_mqtt_started;
static bool s_relay_state;
static bool s_relay_initialized;

static void relay_apply(bool on)
{
    const int gpio_level = CONFIG_MOTOR_CONTROL_RELAY_ACTIVE_HIGH ? (on ? 1 : 0) : (on ? 0 : 1);
    gpio_set_level(CONFIG_MOTOR_CONTROL_RELAY_GPIO, gpio_level);
}

static void relay_set(bool on)
{
    if (s_relay_state == on && s_relay_initialized) {
        return;
    }

    s_relay_state = on;
    relay_apply(on);
    s_relay_initialized = true;
    ESP_LOGI(TAG, "Relay -> %s", on ? "ON" : "OFF");
}

static void process_mqtt_command(const char *data, int len)
{
    if (len <= 0) {
        return;
    }

    char command[8] = {0};
    size_t copy_len = len < (int)(sizeof(command) - 1) ? (size_t)len : sizeof(command) - 1;
    memcpy(command, data, copy_len);

    size_t cmd_len = strlen(command);
    for (size_t i = 0; i < cmd_len; ++i) {
        command[i] = (char)toupper((unsigned char)command[i]);
    }

    if (strcmp(command, "ON") == 0) {
        relay_set(true);
    } else if (strcmp(command, "OFF") == 0) {
        relay_set(false);
    } else {
        ESP_LOGW(TAG, "Unsupported command: %s", command);
    }
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "MQTT connected, subscribing to '%s'", CONFIG_MOTOR_CONTROL_MQTT_TOPIC);
        esp_mqtt_client_subscribe(event->client, CONFIG_MOTOR_CONTROL_MQTT_TOPIC, CONFIG_MOTOR_CONTROL_MQTT_QOS);
        break;
    case MQTT_EVENT_DATA:
        process_mqtt_command(event->data, event->data_len);
        break;
    default:
        break;
    }
}

static void start_mqtt_client(void)
{
    if (s_mqtt_started) {
        return;
    }

    const esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = CONFIG_MOTOR_CONTROL_MQTT_URI,
        .credentials.username = CONFIG_MOTOR_CONTROL_MQTT_USERNAME,
        .credentials.authentication.password = CONFIG_MOTOR_CONTROL_MQTT_PASSWORD,
        .credentials.client_id = CONFIG_MOTOR_CONTROL_MQTT_CLIENT_ID,
    };

    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(s_mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt_client));
    s_mqtt_started = true;
}

static void ip_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ESP_LOGI(TAG, "Network ready, starting MQTT client");
        start_mqtt_client();
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    switch (event_id) {
    case WIFI_EVENT_STA_START:
        esp_wifi_connect();
        break;
    case WIFI_EVENT_STA_DISCONNECTED:
        ESP_LOGW(TAG, "Disconnected from AP, retrying...");
        esp_wifi_connect();
        break;
    default:
        break;
    }
}

static void wifi_start(void)
{
    if (strlen(CONFIG_MOTOR_CONTROL_WIFI_SSID) == 0) {
        ESP_LOGW(TAG, "Wi-Fi SSID is empty; set CONFIG_MOTOR_CONTROL_WIFI_SSID before building.");
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, ip_event_handler, NULL,
                                                        &instance_got_ip));
    (void)instance_any_id;
    (void)instance_got_ip;

    wifi_config_t wifi_config = { 0 };
    strlcpy((char *)wifi_config.sta.ssid, CONFIG_MOTOR_CONTROL_WIFI_SSID, sizeof(wifi_config.sta.ssid));
    strlcpy((char *)wifi_config.sta.password, CONFIG_MOTOR_CONTROL_WIFI_PASSWORD, sizeof(wifi_config.sta.password));
    wifi_config.sta.threshold.authmode = strlen(CONFIG_MOTOR_CONTROL_WIFI_PASSWORD) == 0 ? WIFI_AUTH_OPEN : WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Wi-Fi STA initialized, connecting to '%s'", CONFIG_MOTOR_CONTROL_WIFI_SSID);
}

static void relay_init(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = 1ULL << CONFIG_MOTOR_CONTROL_RELAY_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&io_conf));
    s_relay_initialized = false;
    relay_set(false);
    ESP_LOGI(TAG, "Relay ready on GPIO %d (%s-active)", CONFIG_MOTOR_CONTROL_RELAY_GPIO,
             CONFIG_MOTOR_CONTROL_RELAY_ACTIVE_HIGH ? "high" : "low");
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    relay_init();
    wifi_start();
}
