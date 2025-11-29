#ifndef EDGE_DETECT_H
#define EDGE_DETECT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

/**
 * @brief Sensor snapshot structure
 */
typedef struct {
    bool ir1_present;  ///< IR sensor 1 presence detected
    bool ir2_present;  ///< IR sensor 2 presence detected
    int distance_mm;   ///< Distance in mm (-1 if invalid)
} sensor_snapshot_t;

/**
 * @brief Edge detection state structure
 */
typedef struct {
    bool last_ir1_valid;  ///< Whether last IR1 value is valid
    bool last_ir2_valid;  ///< Whether last IR2 value is valid
    bool last_ir1;        ///< Last IR1 state
    bool last_ir2;        ///< Last IR2 state
    bool last_dist_valid; ///< Whether last distance value is valid
    int last_dist;        ///< Last distance value in mm
} edge_state_t;

/**
 * @brief Event type enumeration
 */
typedef enum {
    EV_NONE = 0,    ///< No event
    EV_IR1,         ///< IR1 sensor state changed
    EV_IR2,         ///< IR2 sensor state changed
    EV_DISTANCE     ///< Distance changed significantly
} event_type_t;

/**
 * @brief Edge event structure
 */
typedef struct {
    event_type_t type;  ///< Type of event
    union {
        bool present;  ///< For IR events: new presence state
        struct {
            int from_mm;  ///< For distance events: previous distance
            int to_mm;    ///< For distance events: new distance
        } dist;
    };
} edge_event_t;

/**
 * @brief Initialize edge detection state
 * 
 * @param state Pointer to edge detection state structure
 */
void edge_detect_init(edge_state_t *state);

/**
 * @brief Process sensor snapshot and detect edge events
 * 
 * @param state Pointer to edge detection state (will be updated)
 * @param snap Pointer to current sensor snapshot
 * @param dist_threshold_mm Distance change threshold in mm
 * @param out_events Output array for detected events
 * @param max_events Maximum number of events to return
 * @return Number of events detected (0 to max_events)
 */
int edge_detect_process(edge_state_t *state, const sensor_snapshot_t *snap, 
                        int dist_threshold_mm, edge_event_t *out_events, int max_events);

#ifdef __cplusplus
}
#endif

#endif // EDGE_DETECT_H

