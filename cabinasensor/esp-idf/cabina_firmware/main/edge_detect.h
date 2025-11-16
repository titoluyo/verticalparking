#pragma once
#include <stdbool.h>
#include "hw_sensors.h"

typedef struct {
    bool last_ir1_valid;
    bool last_ir2_valid;
    bool last_ir1;
    bool last_ir2;
    bool last_dist_valid;
    int  last_dist;
} edge_state_t;

typedef enum {
    EV_NONE = 0,
    EV_IR1,
    EV_IR2,
    EV_DISTANCE
} event_type_t;

typedef struct {
    event_type_t type;
    union {
        bool present;
        struct { int from_mm; int to_mm; } dist;
    };
} edge_event_t;

void edge_init(edge_state_t *st);
int edge_process(edge_state_t *st, const sensor_snapshot_t *snap, int dist_threshold, edge_event_t *out_events, int max_events);


