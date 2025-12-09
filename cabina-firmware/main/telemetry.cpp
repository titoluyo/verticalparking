#include "telemetry.h"
#include "sdkconfig.h"
#include "esp_timer.h"
#include <stdio.h>
#include <string.h>

void telemetry_build_topics(char *topic_ir1, size_t topic_ir1_sz,
                            char *topic_ir2, size_t topic_ir2_sz,
                            char *topic_dist, size_t topic_dist_sz,
                            char *topic_stat, size_t topic_stat_sz) {
    if (topic_ir1 && topic_ir1_sz > 0) {
        snprintf(topic_ir1, topic_ir1_sz, "%s/%s/%s/presence/entry",
                 CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
                 CONFIG_EXAMPLE_MQTT_SITE_ID,
                 CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    }
    
    if (topic_ir2 && topic_ir2_sz > 0) {
        snprintf(topic_ir2, topic_ir2_sz, "%s/%s/%s/presence/full",
                 CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
                 CONFIG_EXAMPLE_MQTT_SITE_ID,
                 CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    }
    
    if (topic_dist && topic_dist_sz > 0) {
        snprintf(topic_dist, topic_dist_sz, "%s/%s/%s/distance/event",
                 CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
                 CONFIG_EXAMPLE_MQTT_SITE_ID,
                 CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    }
    
    if (topic_stat && topic_stat_sz > 0) {
        snprintf(topic_stat, topic_stat_sz, "%s/%s/%s/status",
                 CONFIG_EXAMPLE_MQTT_TOPIC_BASE,
                 CONFIG_EXAMPLE_MQTT_SITE_ID,
                 CONFIG_EXAMPLE_MQTT_DEVICE_ID);
    }
}

int telemetry_json_presence(const char *sensor, bool present, 
                            char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }
    
    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"sensor\":\"%s\",\"present\":%s}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                    sensor ? sensor : "unknown",
                    present ? "true" : "false");
}

int telemetry_json_distance(int from_mm, int to_mm, 
                           char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }
    
    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"from_mm\":%d,\"to_mm\":%d}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                    from_mm,
                    to_mm);
}

int telemetry_json_status(char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }
    
    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"status\":\"online\"}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID);
}

int telemetry_json_status_extended(const char *version, const char *partition,
                                   char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }
    
    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"status\":\"online\","
                    "\"version\":\"%s\",\"partition\":\"%s\"}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                    version ? version : "unknown",
                    partition ? partition : "unknown");
}

int telemetry_json_calibration_complete(int floor_level_mm, int calibration_rounds,
                                        int min_distance_mm, int max_distance_mm,
                                        char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }
    
    // Get current timestamp
    int64_t ts_us = esp_timer_get_time();
    double ts = (double)ts_us / 1e6;
    
    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"floor_level_mm\":%d,"
                    "\"calibration_rounds\":%d,\"min_distance_mm\":%d,"
                    "\"max_distance_mm\":%d,\"ts\":%.3f}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                    floor_level_mm,
                    calibration_rounds,
                    min_distance_mm,
                    max_distance_mm,
                    ts);
}

int telemetry_json_floor_reached(int distance_mm, int floor_level_mm,
                                char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }
    
    // Get current timestamp
    int64_t ts_us = esp_timer_get_time();
    double ts = (double)ts_us / 1e6;
    
    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"distance_mm\":%d,"
                    "\"floor_level_mm\":%d,\"ts\":%.3f}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                    distance_mm,
                    floor_level_mm,
                    ts);
}

