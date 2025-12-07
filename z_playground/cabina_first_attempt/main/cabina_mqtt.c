#include "cabina_mqtt.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static const char *TAG = "mqtt";

typedef struct {
    cmd_handler_fn on_cmd;
    void *user;
} user_cb_t;

static user_cb_t s_user = {0};
static cabina_mqtt_t *s_ctx = NULL;
static bool s_connected = false;

static void mqtt_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = event_data;
    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT connected");
            s_connected = true;
            if (s_ctx) {
                char cmd_topic[160];
                snprintf(cmd_topic, sizeof(cmd_topic), "%s/%s/%s/cmd",
                         s_ctx->cfg.topic_base, s_ctx->cfg.site_id, s_ctx->cfg.device_id);
                esp_mqtt_client_subscribe(event->client, cmd_topic, 0);
            }
            break;
        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "MQTT disconnected");
            s_connected = false;
            break;
        case MQTT_EVENT_SUBSCRIBED:
            ESP_LOGI(TAG, "Subscribed msg_id=%d", event->msg_id);
            break;
        case MQTT_EVENT_DATA: {
            if (s_ctx && s_user.on_cmd) {
                char topic[128] = {0};
                int len = event->topic_len < 127 ? event->topic_len : 127;
                memcpy(topic, event->topic, len);
                topic[len] = 0;
                char cmd_topic[160];
                snprintf(cmd_topic, sizeof(cmd_topic), "%s/%s/%s/cmd",
                         s_ctx->cfg.topic_base, s_ctx->cfg.site_id, s_ctx->cfg.device_id);
                if (strcmp(topic, cmd_topic) == 0) {
                    char *msg = strndup(event->data, event->data_len);
                    if (msg) {
                        s_user.on_cmd(msg, s_user.user);
                        free(msg);
                    }
                }
            }
            break;
        }
        default:
            break;
    }
}

void cabina_mqtt_init(cabina_mqtt_t *m, const cabina_config_t *cfg, cmd_handler_fn on_cmd, void *user) {
    memset(m, 0, sizeof(*m));
    m->cfg = *cfg;
    s_ctx = m;
    s_user.on_cmd = on_cmd;
    s_user.user = user;

    char tmp_topic[160];
    snprintf(tmp_topic, sizeof(tmp_topic), "%s/%s/%s/status", cfg->topic_base, cfg->site_id, cfg->device_id);
    char tmp_payload[192];
    snprintf(tmp_payload, sizeof(tmp_payload),
             "{\"site\":\"%s\",\"device\":\"%s\",\"status\":\"offline\"}", cfg->site_id, cfg->device_id);
    m->will_topic = strdup(tmp_topic);
    m->will_payload = strdup(tmp_payload);
    if (!m->will_topic || !m->will_payload) {
        ESP_LOGE(TAG, "OOM allocating MQTT LWT strings");
        if (m->will_topic) { free(m->will_topic); m->will_topic = NULL; }
        if (m->will_payload) { free(m->will_payload); m->will_payload = NULL; }
        return;
    }

    esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.hostname = cfg->mqtt_broker,
        .broker.address.port = cfg->mqtt_port,
        .broker.address.transport = MQTT_TRANSPORT_OVER_TCP,
        .credentials.username = cfg->mqtt_user,
        .credentials.authentication.password = cfg->mqtt_password,
        .session.keepalive = 30,
        .network.disable_auto_reconnect = false,
        .session.last_will.topic = m->will_topic,
        .session.last_will.msg = m->will_payload,
        .session.last_will.qos = 1,
        .session.last_will.retain = true,
    };
    m->client = esp_mqtt_client_init(&mqtt_cfg);
    if (!m->client) {
        ESP_LOGE(TAG, "esp_mqtt_client_init failed");
        if (m->will_topic) { free(m->will_topic); m->will_topic = NULL; }
        if (m->will_payload) { free(m->will_payload); m->will_payload = NULL; }
        return;
    }
    esp_mqtt_client_register_event(m->client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(m->client);

    // Subscription is deferred to MQTT_EVENT_CONNECTED
}

void cabina_mqtt_loop(cabina_mqtt_t *m) {
    (void)m;
}

bool cabina_mqtt_connected(cabina_mqtt_t *m) {
    (void)m;
    return s_connected;
}

void cabina_mqtt_publish_json(cabina_mqtt_t *m, const char *topic, const char *json, int qos, bool retain) {
    if (!m || !m->client) {
        ESP_LOGW(TAG, "Cannot publish: MQTT client not initialized");
        return;
    }
    esp_mqtt_client_publish(m->client, topic, json, 0, qos, retain);
}

void cabina_mqtt_deinit(cabina_mqtt_t *m) {
    if (!m) return;
    if (m->client) {
        esp_mqtt_client_stop(m->client);
        esp_mqtt_client_destroy(m->client);
        m->client = NULL;
    }
    if (m->will_topic) {
        free(m->will_topic);
        m->will_topic = NULL;
    }
    if (m->will_payload) {
        free(m->will_payload);
        m->will_payload = NULL;
    }
}


