#include "telemetry.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_log.h"
#include <stdio.h>
#include <string.h>

static const char *TAG_TEL = "telemetry";

void topics_build(const cabina_config_t *cfg,
                  char *event_ir1, size_t event_ir1_sz,
                  char *event_ir2, size_t event_ir2_sz,
                  char *event_dist, size_t event_dist_sz,
                  char *topic_stat, size_t topic_stat_sz) {
    if (event_ir1 && event_ir1_sz > 0) {
        snprintf(event_ir1, event_ir1_sz, "%s/%s/%s/presence/entry", cfg->topic_base, cfg->site_id, cfg->device_id);
    }
    if (event_ir2 && event_ir2_sz > 0) {
        snprintf(event_ir2, event_ir2_sz, "%s/%s/%s/presence/full", cfg->topic_base, cfg->site_id, cfg->device_id);
    }
    if (event_dist && event_dist_sz > 0) {
        snprintf(event_dist, event_dist_sz, "%s/%s/%s/distance/event", cfg->topic_base, cfg->site_id, cfg->device_id);
    }
    if (topic_stat && topic_stat_sz > 0) {
        snprintf(topic_stat, topic_stat_sz, "%s/%s/%s/status", cfg->topic_base, cfg->site_id, cfg->device_id);
    }
}

static char *oom_fallback(void) {
    // Minimal JSON to avoid NULL propagation; caller will free
    const char *min = "{\"oom\":true}";
    size_t len = strlen(min) + 1;
    char *buf = (char *)malloc(len);
    if (!buf) return NULL;
    memcpy(buf, min, len);
    return buf;
}

static char *dup_print(cJSON *obj) {
    if (!obj) {
        ESP_LOGE(TAG_TEL, "cJSON object is NULL");
        return oom_fallback();
    }
    char *txt = cJSON_PrintUnformatted(obj);
    cJSON_Delete(obj);
    if (!txt) {
        ESP_LOGE(TAG_TEL, "cJSON_PrintUnformatted failed");
        return oom_fallback();
    }
    return txt;
}

char *json_presence(const cabina_config_t *cfg, const char *sensor, bool present, const char *ip) {
    cJSON *o = cJSON_CreateObject();
    if (!o) return oom_fallback();
    cJSON_AddStringToObject(o, "site", cfg->site_id);
    cJSON_AddStringToObject(o, "device", cfg->device_id);
    cJSON_AddStringToObject(o, "sensor", sensor);
    cJSON_AddBoolToObject(o, "present", present);
    if (ip) cJSON_AddStringToObject(o, "ip", ip);
    return dup_print(o);
}

char *json_distance(const cabina_config_t *cfg, int from_mm, int to_mm, const char *ip) {
    cJSON *o = cJSON_CreateObject();
    if (!o) return oom_fallback();
    cJSON_AddStringToObject(o, "site", cfg->site_id);
    cJSON_AddStringToObject(o, "device", cfg->device_id);
    cJSON_AddNumberToObject(o, "from_mm", from_mm);
    cJSON_AddNumberToObject(o, "to_mm", to_mm);
    if (ip) cJSON_AddStringToObject(o, "ip", ip);
    return dup_print(o);
}

char *json_status_online(const cabina_config_t *cfg, const char *ip) {
    cJSON *o = cJSON_CreateObject();
    if (!o) return oom_fallback();
    cJSON_AddStringToObject(o, "site", cfg->site_id);
    cJSON_AddStringToObject(o, "device", cfg->device_id);
    if (ip) cJSON_AddStringToObject(o, "ip", ip);
    cJSON_AddStringToObject(o, "status", "online");
    return dup_print(o);
}


