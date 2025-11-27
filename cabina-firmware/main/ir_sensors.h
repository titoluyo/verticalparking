#ifndef IR_SENSORS_H
#define IR_SENSORS_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include "esp_err.h"

/**
 * @brief IR sensor reading structure
 */
typedef struct {
    bool ir1_present;  ///< IR sensor 1 presence detected
    bool ir2_present;  ///< IR sensor 2 presence detected
} ir_sensors_state_t;

/**
 * @brief Initialize IR sensors
 * 
 * @param ir1_pin GPIO pin for IR sensor 1
 * @param ir2_pin GPIO pin for IR sensor 2
 * @param use_pullups Enable internal pull-ups (true) or pull-downs (false)
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t ir_sensors_init(int ir1_pin, int ir2_pin, bool use_pullups);

/**
 * @brief Read current state of IR sensors
 * 
 * @param state Pointer to structure to store sensor states
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t ir_sensors_read(ir_sensors_state_t *state);

/**
 * @brief Read IR sensor 1 state
 * 
 * @return true if presence detected, false otherwise
 */
bool ir_sensors_read_ir1(void);

/**
 * @brief Read IR sensor 2 state
 * 
 * @return true if presence detected, false otherwise
 */
bool ir_sensors_read_ir2(void);

#ifdef __cplusplus
}
#endif

#endif // IR_SENSORS_H

