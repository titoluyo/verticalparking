#include "edge_detect.h"

void edge_detect_init(edge_state_t *state) {
    if (!state) return;
    
    state->last_ir1_valid = false;
    state->last_ir2_valid = false;
    state->last_dist_valid = false;
    state->last_ir1 = false;
    state->last_ir2 = false;
    state->last_dist = 0;
}

int edge_detect_process(edge_state_t *state, const sensor_snapshot_t *snap, 
                        int dist_threshold_mm, edge_event_t *out_events, int max_events) {
    if (!state || !snap || !out_events || max_events <= 0) {
        return 0;
    }
    
    int count = 0;
    
    // Check IR1 state change
    if (!state->last_ir1_valid || snap->ir1_present != state->last_ir1) {
        if (count < max_events) {
            out_events[count].type = EV_IR1;
            out_events[count].present = snap->ir1_present;
            count++;
        }
        state->last_ir1 = snap->ir1_present;
        state->last_ir1_valid = true;
    }
    
    // Check IR2 state change
    if (!state->last_ir2_valid || snap->ir2_present != state->last_ir2) {
        if (count < max_events) {
            out_events[count].type = EV_IR2;
            out_events[count].present = snap->ir2_present;
            count++;
        }
        state->last_ir2 = snap->ir2_present;
        state->last_ir2_valid = true;
    }
    
    // Check distance change (only if valid reading)
    if (snap->distance_mm >= 0) {
        if (!state->last_dist_valid) {
            // First valid reading - store it but don't generate event
            state->last_dist = snap->distance_mm;
            state->last_dist_valid = true;
        } else {
            // Calculate absolute change
            int delta = snap->distance_mm - state->last_dist;
            if (delta < 0) {
                delta = -delta;
            }
            
            // Only generate event if change exceeds threshold
            if (delta >= dist_threshold_mm) {
                if (count < max_events) {
                    out_events[count].type = EV_DISTANCE;
                    out_events[count].dist.from_mm = state->last_dist;
                    out_events[count].dist.to_mm = snap->distance_mm;
                    count++;
                }
                state->last_dist = snap->distance_mm;
            }
        }
    }
    
    return count;
}

