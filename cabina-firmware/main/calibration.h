#ifndef CALIBRATION_H
#define CALIBRATION_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

/**
 * @brief Maximum number of distance samples to store during calibration
 */
#define CALIBRATION_MAX_SAMPLES 2000

/**
 * @brief Tolerance for rotation detection (mm)
 */
#define CALIBRATION_ROTATION_TOLERANCE_MM 20

/**
 * @brief Tolerance for floor detection (mm)
 */
#define CALIBRATION_FLOOR_TOLERANCE_MM 10

/**
 * @brief Rotation detection state enumeration
 */
typedef enum {
    ROT_STATE_INIT,          ///< Initial state, waiting for first reading
    ROT_STATE_SEEKING_MIN,   ///< Looking for minimum (floor)
    ROT_STATE_SEEKING_MAX,   ///< Looking for maximum (top)
    ROT_STATE_COMPLETING     ///< Returning to minimum (completing rotation)
} calibration_rotation_state_t;

/**
 * @brief Calibration state structure
 */
typedef struct {
    bool active;                    ///< Is calibration in progress
    int round;                      ///< Current round (0, 1, or 2)
    int distance_samples[CALIBRATION_MAX_SAMPLES];  ///< Array of distance samples
    int sample_count;                ///< Number of samples collected
    int min_distance_tracked;         ///< Absolute minimum distance seen
    int max_distance_tracked;        ///< Absolute maximum distance seen
    int start_distance;              ///< Initial distance when calibration started
    int rotation_count;               ///< Number of complete rotations detected
    int floor_level;                 ///< Calculated floor level (stored in NVS)
    bool floor_level_valid;          ///< Whether floor level is valid (calibrated)
    
    // Rotation detection state
    calibration_rotation_state_t rotation_state;
    int last_min_distance;           ///< Last detected minimum
    int last_max_distance;            ///< Last detected maximum
    int samples_since_min;            ///< Samples since last minimum
    int samples_since_max;            ///< Samples since last maximum
} calibration_state_t;

/**
 * @brief Initialize calibration state
 * 
 * @param state Pointer to calibration state structure
 */
void calibration_init(calibration_state_t *state);

/**
 * @brief Start calibration process
 * 
 * @param state Pointer to calibration state structure
 * @param initial_distance Initial distance reading in mm
 */
void calibration_start(calibration_state_t *state, int initial_distance);

/**
 * @brief Stop calibration process (cancel)
 * 
 * @param state Pointer to calibration state structure
 */
void calibration_stop(calibration_state_t *state);

/**
 * @brief Process a distance reading during calibration
 * 
 * @param state Pointer to calibration state structure
 * @param distance_mm Current distance reading in mm
 * @return true if calibration is complete (2 rotations finished)
 */
bool calibration_process_sample(calibration_state_t *state, int distance_mm);

/**
 * @brief Get the calculated floor level
 * 
 * @param state Pointer to calibration state structure
 * @return Floor level in mm, or 0 if not calibrated
 */
int calibration_get_floor_level(calibration_state_t *state);

/**
 * @brief Check if cabin is at floor level during normal operation
 * 
 * @param state Pointer to calibration state structure
 * @param current_distance Current distance reading in mm
 * @return true if at floor level (within tolerance)
 */
bool calibration_is_at_floor(calibration_state_t *state, int current_distance);

/**
 * @brief Load floor level from NVS
 * 
 * @param state Pointer to calibration state structure
 * @return true if floor level was loaded successfully
 */
bool calibration_load_floor_level(calibration_state_t *state);

/**
 * @brief Save floor level to NVS
 * 
 * @param state Pointer to calibration state structure
 * @param floor_level_mm Floor level in mm
 * @return true if saved successfully
 */
bool calibration_save_floor_level(calibration_state_t *state, int floor_level_mm);

#ifdef __cplusplus
}
#endif

#endif // CALIBRATION_H
