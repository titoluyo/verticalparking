#include "edge_detect.h"

void edge_init(edge_state_t *st) {
    st->last_ir1_valid = false;
    st->last_ir2_valid = false;
    st->last_dist_valid = false;
}

int edge_process(edge_state_t *st, const sensor_snapshot_t *snap, int dist_threshold, edge_event_t *out_events, int max_events) {
    int count = 0;
    if (!st->last_ir1_valid || snap->ir1_present != st->last_ir1) {
        if (count < max_events) {
            out_events[count].type = EV_IR1;
            out_events[count].present = snap->ir1_present;
            count++;
        }
        st->last_ir1 = snap->ir1_present;
        st->last_ir1_valid = true;
    }
    if (!st->last_ir2_valid || snap->ir2_present != st->last_ir2) {
        if (count < max_events) {
            out_events[count].type = EV_IR2;
            out_events[count].present = snap->ir2_present;
            count++;
        }
        st->last_ir2 = snap->ir2_present;
        st->last_ir2_valid = true;
    }
    if (snap->distance_mm >= 0) {
        if (!st->last_dist_valid) {
            st->last_dist = snap->distance_mm;
            st->last_dist_valid = true;
        } else {
            int delta = snap->distance_mm - st->last_dist;
            if (delta < 0) delta = -delta;
            if (delta >= dist_threshold) {
                if (count < max_events) {
                    out_events[count].type = EV_DISTANCE;
                    out_events[count].dist.from_mm = st->last_dist;
                    out_events[count].dist.to_mm = snap->distance_mm;
                    count++;
                }
                st->last_dist = snap->distance_mm;
            }
        }
    }
    return count;
}


