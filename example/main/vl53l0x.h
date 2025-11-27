#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

// VL53L0X I2C address
#define VL53L0X_ADDR 0x29

// Return codes
#define VL53L0X_OK 0
#define VL53L0X_ERROR -1
#define VL53L0X_TIMEOUT -2

// Initialize VL53L0X sensor
// Returns VL53L0X_OK on success, negative on error
int vl53l0x_init(int i2c_port);

// Read distance in millimeters
// Returns distance in mm (0-8191), or negative on error
int vl53l0x_read_range_mm(int i2c_port);

// Check if sensor is present and responding
bool vl53l0x_is_present(int i2c_port);

#ifdef __cplusplus
}
#endif

