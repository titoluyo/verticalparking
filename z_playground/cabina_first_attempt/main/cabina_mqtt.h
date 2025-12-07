#pragma once
#include "config.h"
#include <stdbool.h>
#include <mqtt_client.h>  // ESP-IDF MQTT API

typedef struct {
    cabina_config_t cfg;
    esp_mqtt_client_handle_t client;
    // Heap-owned copies to avoid use-after-free in esp-mqtt last will pointers
    char *will_topic;
    char *will_payload;
} cabina_mqtt_t;

typedef void (*cmd_handler_fn)(const char *msg, void *user);

void cabina_mqtt_init(cabina_mqtt_t *m, const cabina_config_t *cfg, cmd_handler_fn on_cmd, void *user);
void cabina_mqtt_loop(cabina_mqtt_t *m);
bool cabina_mqtt_connected(cabina_mqtt_t *m);
void cabina_mqtt_publish_json(cabina_mqtt_t *m, const char *topic, const char *json, int qos, bool retain);
void cabina_mqtt_deinit(cabina_mqtt_t *m);


