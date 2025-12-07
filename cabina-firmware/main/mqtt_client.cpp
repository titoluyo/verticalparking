#include "sdkconfig.h"
#include "esp_log.h"
#include "esp_event.h"
#include <mqtt_client.h>  // ESP-IDF MQTT API
#include "mqtt_wrapper.h"
#include <string.h>
#include <stdlib.h>
#include <errno.h>

static const char *TAG = "mqtt_client";

static esp_mqtt_client_handle_t s_mqtt_client = NULL;
static bool s_connected = false;
static char *s_will_topic = NULL;
static char *s_will_payload = NULL;

// Message callback function type
typedef void (*mqtt_message_callback_t)(const char *topic, const char *data, int data_len);
static mqtt_message_callback_t s_message_callback = NULL;

static void mqtt_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT connected to broker");
            s_connected = true;
            break;

        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGI(TAG, "MQTT disconnected from broker");
            s_connected = false;
            break;

        case MQTT_EVENT_SUBSCRIBED:
            ESP_LOGI(TAG, "MQTT subscribed, msg_id=%d", event->msg_id);
            break;

        case MQTT_EVENT_UNSUBSCRIBED:
            ESP_LOGI(TAG, "MQTT unsubscribed, msg_id=%d", event->msg_id);
            break;

        case MQTT_EVENT_PUBLISHED:
            ESP_LOGD(TAG, "MQTT published, msg_id=%d", event->msg_id);
            break;

        case MQTT_EVENT_DATA: {
            // Extract topic and data as null-terminated strings
            char topic[256] = {0};
            char data[512] = {0};
            int topic_len = event->topic_len < sizeof(topic) - 1 ? event->topic_len : sizeof(topic) - 1;
            int data_len = event->data_len < sizeof(data) - 1 ? event->data_len : sizeof(data) - 1;
            
            memcpy(topic, event->topic, topic_len);
            topic[topic_len] = '\0';
            memcpy(data, event->data, data_len);
            data[data_len] = '\0';
            
            ESP_LOGI(TAG, "MQTT data received, topic=%s, data=%.*s", topic, data_len, data);
            
            // Call registered callback if available
            if (s_message_callback) {
                s_message_callback(topic, data, data_len);
            }
            break;
        }

        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT error");
            if (event->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT) {
                ESP_LOGE(TAG, "Transport error: %s", strerror(event->error_handle->esp_transport_sock_errno));
            }
            break;

        default:
            ESP_LOGD(TAG, "MQTT event: %ld", event_id);
            break;
    }
}

esp_err_t mqtt_client_init(void) {
    // Build topic paths
    char status_topic[160];
    snprintf(status_topic, sizeof(status_topic), "%s/%s/%s/status",
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);

    // Create last will and testament payload
    char will_payload[192];
    snprintf(will_payload, sizeof(will_payload),
             "{\"site\":\"%s\",\"device\":\"%s\",\"status\":\"offline\"}",
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);

    // Allocate memory for LWT strings
    s_will_topic = strdup(status_topic);
    s_will_payload = strdup(will_payload);
    if (!s_will_topic || !s_will_payload) {
        ESP_LOGE(TAG, "Failed to allocate memory for LWT");
        if (s_will_topic) { free(s_will_topic); s_will_topic = NULL; }
        if (s_will_payload) { free(s_will_payload); s_will_payload = NULL; }
        return ESP_ERR_NO_MEM;
    }

    // Configure MQTT client
    esp_mqtt_client_config_t mqtt_cfg = {};
    mqtt_cfg.broker.address.hostname = CONFIG_EXAMPLE_MQTT_BROKER;
    mqtt_cfg.broker.address.port = CONFIG_EXAMPLE_MQTT_PORT;
    mqtt_cfg.broker.address.transport = MQTT_TRANSPORT_OVER_TCP;
    
    // Set credentials if provided
    if (strlen(CONFIG_EXAMPLE_MQTT_USER) > 0) {
        mqtt_cfg.credentials.username = CONFIG_EXAMPLE_MQTT_USER;
    }
    if (strlen(CONFIG_EXAMPLE_MQTT_PASSWORD) > 0) {
        mqtt_cfg.credentials.authentication.password = CONFIG_EXAMPLE_MQTT_PASSWORD;
    }

    // Session configuration
    mqtt_cfg.session.keepalive = 30;
    mqtt_cfg.network.disable_auto_reconnect = false;
    mqtt_cfg.network.reconnect_timeout_ms = 10000;
    
    // Last will and testament
    mqtt_cfg.session.last_will.topic = s_will_topic;
    mqtt_cfg.session.last_will.msg = s_will_payload;
    mqtt_cfg.session.last_will.qos = 1;
    mqtt_cfg.session.last_will.retain = true;

    ESP_LOGI(TAG, "Initializing MQTT client: broker=%s:%d, topic_base=%s, site=%s, device=%s",
             CONFIG_EXAMPLE_MQTT_BROKER,
             CONFIG_EXAMPLE_MQTT_PORT,
             CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
             CONFIG_EXAMPLE_MQTT_SITE_ID,
             CONFIG_EXAMPLE_MQTT_DEVICE_ID);

    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    if (s_mqtt_client == NULL) {
        ESP_LOGE(TAG, "Failed to initialize MQTT client");
        free(s_will_topic);
        free(s_will_payload);
        s_will_topic = NULL;
        s_will_payload = NULL;
        return ESP_FAIL;
    }

    esp_mqtt_client_register_event(s_mqtt_client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_err_t ret = esp_mqtt_client_start(s_mqtt_client);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start MQTT client: %s", esp_err_to_name(ret));
        esp_mqtt_client_destroy(s_mqtt_client);
        s_mqtt_client = NULL;
        free(s_will_topic);
        free(s_will_payload);
        s_will_topic = NULL;
        s_will_payload = NULL;
        return ret;
    }

    ESP_LOGI(TAG, "MQTT client started");
    return ESP_OK;
}

bool mqtt_client_is_connected(void) {
    return s_connected;
}

esp_err_t mqtt_client_publish(const char *topic, const char *data, int len, int qos, bool retain) {
    if (s_mqtt_client == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (!s_connected) {
        ESP_LOGW(TAG, "MQTT not connected, cannot publish to %s", topic);
        return ESP_ERR_INVALID_STATE;
    }

    int msg_id = esp_mqtt_client_publish(s_mqtt_client, topic, data, len, qos, retain);
    if (msg_id < 0) {
        ESP_LOGE(TAG, "Failed to publish to %s", topic);
        return ESP_FAIL;
    }

    ESP_LOGD(TAG, "Published to %s (msg_id=%d)", topic, msg_id);
    return ESP_OK;
}

esp_err_t mqtt_client_publish_json(const char *topic, const char *json, int qos, bool retain) {
    return mqtt_client_publish(topic, json, strlen(json), qos, retain);
}

esp_err_t mqtt_client_subscribe(const char *topic, int qos) {
    if (s_mqtt_client == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (!s_connected) {
        ESP_LOGW(TAG, "MQTT not connected, cannot subscribe to %s", topic);
        return ESP_ERR_INVALID_STATE;
    }

    int msg_id = esp_mqtt_client_subscribe(s_mqtt_client, topic, qos);
    if (msg_id < 0) {
        ESP_LOGE(TAG, "Failed to subscribe to %s", topic);
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Subscribed to %s (msg_id=%d)", topic, msg_id);
    return ESP_OK;
}

esp_err_t mqtt_client_get_topic(const char *subtopic, char *topic_buf, size_t buf_len) {
    if (topic_buf == NULL || buf_len < 160) {
        return ESP_ERR_INVALID_ARG;
    }

    int ret = snprintf(topic_buf, buf_len, "%s/%s/%s/%s",
                       CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
                       CONFIG_EXAMPLE_MQTT_SITE_ID,
                       CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                       subtopic);
    
    if (ret < 0 || (size_t)ret >= buf_len) {
        return ESP_ERR_INVALID_ARG;
    }

    return ESP_OK;
}

void mqtt_client_set_message_callback(mqtt_message_callback_t callback) {
    s_message_callback = callback;
}

