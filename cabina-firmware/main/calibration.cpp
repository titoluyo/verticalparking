#include "calibration.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "sdkconfig.h"
#include <string.h>
#include <limits.h>

static const char *TAG = "calibration";
static const char *NVS_NAMESPACE = "cabina_cal";
static const char *NVS_KEY_FLOOR = "floor_level";

void calibration_init(calibration_state_t *state) {
    if (!state) return;
    
    memset(state, 0, sizeof(calibration_state_t));
    state->rotation_state = ROT_STATE_INIT;
    state->min_distance_tracked = INT_MAX;
    state->max_distance_tracked = 0;
    state->floor_level = 0;
    state->floor_level_valid = false;
    
    // Load floor level from NVS
    calibration_load_floor_level(state);
}

void calibration_start(calibration_state_t *state, int initial_distance) {
    if (!state) return;
    
    ESP_LOGI(TAG, "Starting calibration with initial distance: %d mm", initial_distance);
    
    state->active = true;
    state->round = 0;
    state->sample_count = 0;
    state->min_distance_tracked = initial_distance;
    state->max_distance_tracked = initial_distance;
    state->start_distance = initial_distance;
    state->rotation_count = 0;
    state->rotation_state = ROT_STATE_SEEKING_MIN;
    state->last_min_distance = initial_distance;
    state->last_max_distance = initial_distance;
    state->samples_since_min = 0;
    state->samples_since_max = 0;
    
    // Store first sample
    if (state->sample_count < CALIBRATION_MAX_SAMPLES) {
        state->distance_samples[state->sample_count++] = initial_distance;
    }
}

void calibration_stop(calibration_state_t *state) {
    if (!state) return;
    
    ESP_LOGI(TAG, "Stopping calibration");
    state->active = false;
    state->round = 0;
    state->sample_count = 0;
    state->rotation_count = 0;
    state->rotation_state = ROT_STATE_INIT;
}

bool calibration_process_sample(calibration_state_t *state, int distance_mm) {
    if (!state || !state->active || distance_mm < 0) {
        return false;
    }
    
    // Store sample
    if (state->sample_count < CALIBRATION_MAX_SAMPLES) {
        state->distance_samples[state->sample_count++] = distance_mm;
    }
    
    // Update absolute min/max
    if (distance_mm < state->min_distance_tracked) {
        state->min_distance_tracked = distance_mm;
    }
    if (distance_mm > state->max_distance_tracked) {
        state->max_distance_tracked = distance_mm;
    }
    
    // Rotation detection algorithm
    // Pattern: min → max → min (one complete rotation)
    switch (state->rotation_state) {
        case ROT_STATE_INIT:
            // Should not happen, but handle gracefully
            state->rotation_state = ROT_STATE_SEEKING_MIN;
            state->last_min_distance = distance_mm;
            break;
            
        case ROT_STATE_SEEKING_MIN:
            // Looking for minimum (floor level)
            if (distance_mm <= state->last_min_distance + CALIBRATION_ROTATION_TOLERANCE_MM) {
                // Found a new minimum or still at minimum
                if (distance_mm < state->last_min_distance) {
                    state->last_min_distance = distance_mm;
                    state->samples_since_min = 0;
                } else {
                    state->samples_since_min++;
                }
            } else {
                // Distance increased significantly, transition to seeking max
                if (state->samples_since_min >= 3) {  // Require a few samples at min to confirm
                    state->rotation_state = ROT_STATE_SEEKING_MAX;
                    state->last_max_distance = distance_mm;
                    state->samples_since_max = 0;
                    ESP_LOGI(TAG, "Rotation: Found minimum %d mm, now seeking maximum", state->last_min_distance);
                }
            }
            break;
            
        case ROT_STATE_SEEKING_MAX:
            // Looking for maximum (top level)
            if (distance_mm >= state->last_max_distance - CALIBRATION_ROTATION_TOLERANCE_MM) {
                // Found a new maximum or still at maximum
                if (distance_mm > state->last_max_distance) {
                    state->last_max_distance = distance_mm;
                    state->samples_since_max = 0;
                } else {
                    state->samples_since_max++;
                }
            } else {
                // Distance decreased significantly, transition to completing
                if (state->samples_since_max >= 3) {  // Require a few samples at max to confirm
                    state->rotation_state = ROT_STATE_COMPLETING;
                    ESP_LOGI(TAG, "Rotation: Found maximum %d mm, now completing rotation", state->last_max_distance);
                }
            }
            break;
            
        case ROT_STATE_COMPLETING:
            // Returning to minimum (completing rotation)
            if (distance_mm <= state->last_min_distance + CALIBRATION_ROTATION_TOLERANCE_MM) {
                // Back at minimum - rotation complete!
                state->rotation_count++;
                state->round = state->rotation_count;
                ESP_LOGI(TAG, "Rotation %d complete! (min=%d, max=%d)", 
                        state->rotation_count, state->last_min_distance, state->last_max_distance);
                
                // Reset for next rotation
                state->rotation_state = ROT_STATE_SEEKING_MIN;
                state->last_min_distance = distance_mm;
                state->samples_since_min = 0;
                
                // Check if we've completed 2 rotations
                if (state->rotation_count >= 2) {
                    // Calculate final floor level (minimum of all samples)
                    int final_floor = state->min_distance_tracked;
                    for (int i = 0; i < state->sample_count; i++) {
                        if (state->distance_samples[i] < final_floor) {
                            final_floor = state->distance_samples[i];
                        }
                    }
                    
                    state->floor_level = final_floor;
                    state->floor_level_valid = true;
                    
                    // Save to NVS
                    calibration_save_floor_level(state, final_floor);
                    
                    ESP_LOGI(TAG, "Calibration complete! Floor level: %d mm (from %d samples, range: %d-%d mm)",
                            final_floor, state->sample_count, state->min_distance_tracked, state->max_distance_tracked);
                    
                    // Stop calibration
                    state->active = false;
                    return true;
                }
            }
            break;
    }
    
    return false;  // Calibration not complete yet
}

int calibration_get_floor_level(calibration_state_t *state) {
    if (!state || !state->floor_level_valid) {
        return 0;
    }
    return state->floor_level;
}

bool calibration_is_at_floor(calibration_state_t *state, int current_distance) {
    if (!state || !state->floor_level_valid || current_distance < 0) {
        return false;
    }
    
    int diff = current_distance - state->floor_level;
    if (diff < 0) diff = -diff;  // abs
    
    return diff <= CALIBRATION_FLOOR_TOLERANCE_MM;
}

bool calibration_load_floor_level(calibration_state_t *state) {
    if (!state) return false;
    
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Failed to open NVS namespace: %s", esp_err_to_name(err));
        return false;
    }
    
    int32_t floor_level = 0;
    size_t required_size = sizeof(floor_level);
    err = nvs_get_blob(nvs_handle, NVS_KEY_FLOOR, &floor_level, &required_size);
    nvs_close(nvs_handle);
    
    if (err == ESP_OK && floor_level > 0) {
        state->floor_level = (int)floor_level;
        state->floor_level_valid = true;
        ESP_LOGI(TAG, "Loaded floor level from NVS: %d mm", state->floor_level);
        return true;
    } else {
        ESP_LOGI(TAG, "No floor level found in NVS (not calibrated yet)");
        state->floor_level = 0;
        state->floor_level_valid = false;
        return false;
    }
}

bool calibration_save_floor_level(calibration_state_t *state, int floor_level_mm) {
    if (!state || floor_level_mm <= 0) {
        return false;
    }
    
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS namespace for writing: %s", esp_err_to_name(err));
        return false;
    }
    
    int32_t floor_level = (int32_t)floor_level_mm;
    err = nvs_set_blob(nvs_handle, NVS_KEY_FLOOR, &floor_level, sizeof(floor_level));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to save floor level to NVS: %s", esp_err_to_name(err));
        nvs_close(nvs_handle);
        return false;
    }
    
    err = nvs_commit(nvs_handle);
    nvs_close(nvs_handle);
    
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to commit NVS: %s", esp_err_to_name(err));
        return false;
    }
    
    state->floor_level = floor_level_mm;
    state->floor_level_valid = true;
    ESP_LOGI(TAG, "Saved floor level to NVS: %d mm", floor_level_mm);
    return true;
}
