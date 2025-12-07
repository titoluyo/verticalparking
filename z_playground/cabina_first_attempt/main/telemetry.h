#pragma once
#include "cJSON.h"
#include "config.h"
#include "edge_detect.h"
#include "hw_sensors.h"

void topics_build(const cabina_config_t *cfg,
                  char *event_ir1, size_t event_ir1_sz,
                  char *event_ir2, size_t event_ir2_sz,
                  char *event_dist, size_t event_dist_sz,
                  char *topic_stat, size_t topic_stat_sz);

char *json_presence(const cabina_config_t *cfg, const char *sensor, bool present, const char *ip);
char *json_distance(const cabina_config_t *cfg, int from_mm, int to_mm, const char *ip);
char *json_status_online(const cabina_config_t *cfg, const char *ip);


