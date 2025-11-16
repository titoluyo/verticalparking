#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "config.h"

typedef struct {
    bool ir1_present;
    bool ir2_present;
    int  distance_mm; // -1 if unknown
} sensor_snapshot_t;

void sensors_init(const cabina_config_t *cfg);
void sensors_read(sensor_snapshot_t *out);
void sensors_deinit(void);


