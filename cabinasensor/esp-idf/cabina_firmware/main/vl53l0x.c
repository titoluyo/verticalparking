#include "vl53l0x.h"
#include "driver/i2c.h"
#include "esp_log.h"
#include "esp_timer.h"
#include <string.h>

static const char *TAG = "vl53l0x";
static const int VL53L0X_MAX_STABLE_DISTANCE_MM = 1200;
static int g_last_valid_distance_mm = -1;

// Minimum time between measurements (timing budget 33ms + overhead)
static const int MIN_MEASUREMENT_INTERVAL_MS = 50;
static int64_t g_last_measurement_time_us = 0;

// VL53L0X register addresses (from datasheet)
#define VL53L0X_REG_IDENTIFICATION_MODEL_ID         0xC0
#define VL53L0X_REG_IDENTIFICATION_REVISION_ID      0xC2
#define VL53L0X_REG_PRE_RANGE_CONFIG_VCSEL_PERIOD   0x50
#define VL53L0X_REG_FINAL_RANGE_CONFIG_VCSEL_PERIOD 0x70
#define VL53L0X_REG_SYSRANGE_START                  0x00
#define VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG          0x01
#define VL53L0X_REG_SYSTEM_INTERRUPT_CONFIG_GPIO    0x0A
#define VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR          0x0B
#define VL53L0X_REG_SYSTEM_MODE_START               0x01
#define VL53L0X_REG_RESULT_INTERRUPT_STATUS         0x13
#define VL53L0X_REG_RESULT_RANGE_STATUS             0x14
#define VL53L0X_REG_SOFT_RESET                      0x00
#define VL53L0X_SOFT_RESET_VALUE                    0x00
#define VL53L0X_REG_RESULT_CORE_AMBIENT_WINDOW_EVENTS_RTN 0xBC
#define VL53L0X_REG_RESULT_CORE_RANGING_TOTAL_EVENTS_RTN  0xC0
#define VL53L0X_REG_RESULT_CORE_AMBIENT_WINDOW_EVENTS_REF 0xD0
#define VL53L0X_REG_RESULT_CORE_RANGING_TOTAL_EVENTS_REF  0xD4
#define VL53L0X_REG_RESULT_PEAK_SIGNAL_RATE_REF           0xB6
#define VL53L0X_REG_RESULT_PEAK_SIGNAL_RATE_RTN           0xC4
#define VL53L0X_REG_RESULT_OSC_CALIBRATE_VAL              0xF8
#define VL53L0X_REG_MEASUREMENT_TIMING_BUDGET_MS          0x0C
#define VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG                0x01
#define VL53L0X_REG_DYNAMIC_SPAD_REF_EN_START_OFFSET      0x4D
#define VL53L0X_REG_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD   0x4E
#define VL53L0X_REG_GLOBAL_CONFIG_REF_EN_START_SELECT     0xB1
#define VL53L0X_REG_SYSTEM_INTERRUPT_CONFIG_GPIO          0x0A
#define VL53L0X_REG_GPIO_HV_MUX_ACTIVE_HIGH               0x84
#define VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR                0x0B
#define VL53L0X_REG_RESULT_INTERRUPT_STATUS               0x13
#define VL53L0X_REG_SYSTEM_INTERRUPT_CONFIG_GPIO          0x0A
#define VL53L0X_REG_RESULT_RANGE_STATUS                   0x14
#define VL53L0X_REG_SYSRANGE_START                        0x00
#define VL53L0X_REG_RESULT_FINAL_RANGE_VALUE              0x1E

// Magic values
#define VL53L0X_IDENTIFICATION_MODEL_ID 0xEEAA
#define VL53L0X_SYSRANGE_MODE_START_STOP 0x01
#define VL53L0X_SYSRANGE_MODE_SINGLESHOT 0x00

static esp_err_t i2c_write_reg(int i2c_port, uint8_t reg, uint8_t value) {
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (VL53L0X_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_write_byte(cmd, value, true);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);
    return ret;
}

static esp_err_t i2c_read_reg(int i2c_port, uint8_t reg, uint8_t *value) {
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (VL53L0X_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (VL53L0X_ADDR << 1) | I2C_MASTER_READ, true);
    i2c_master_read_byte(cmd, value, I2C_MASTER_NACK);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);
    return ret;
}

static esp_err_t i2c_read_reg16(int i2c_port, uint8_t reg, uint16_t *value) {
    uint8_t buf[2];
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (VL53L0X_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (VL53L0X_ADDR << 1) | I2C_MASTER_READ, true);
    i2c_master_read_byte(cmd, &buf[0], I2C_MASTER_ACK);
    i2c_master_read_byte(cmd, &buf[1], I2C_MASTER_NACK);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);
    if (ret == ESP_OK) {
        *value = (uint16_t)buf[0] | ((uint16_t)buf[1] << 8);
    }
    return ret;
}

static esp_err_t i2c_write_reg16(int i2c_port, uint8_t reg, uint16_t value) {
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (VL53L0X_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_write_byte(cmd, value & 0xFF, true);
    i2c_master_write_byte(cmd, (value >> 8) & 0xFF, true);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);
    return ret;
}

// Scan I2C bus and log found devices
static void i2c_scan(int i2c_port) {
    ESP_LOGI(TAG, "Scanning I2C bus...");
    int found = 0;
    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (addr << 1) | I2C_MASTER_WRITE, true);
        i2c_master_stop(cmd);
        esp_err_t ret = i2c_master_cmd_begin(i2c_port, cmd, pdMS_TO_TICKS(50));
        i2c_cmd_link_delete(cmd);
        if (ret == ESP_OK) {
            ESP_LOGI(TAG, "  Found device at address 0x%02X", addr);
            found++;
        }
    }
    if (found == 0) {
        ESP_LOGW(TAG, "  No I2C devices found!");
    } else {
        ESP_LOGI(TAG, "  Found %d device(s)", found);
    }
}

bool vl53l0x_is_present(int i2c_port) {
    // First, scan the bus to see what's there
    i2c_scan(i2c_port);
    
    // Try to read model ID from VL53L0X
    uint8_t model_id = 0;
    esp_err_t err = i2c_read_reg(i2c_port, VL53L0X_REG_IDENTIFICATION_MODEL_ID, &model_id);
    if (err != ESP_OK) {
        ESP_LOGD(TAG, "Failed to read VL53L0X model ID: %s", esp_err_to_name(err));
        return false;
    }
    ESP_LOGI(TAG, "VL53L0X model ID read: 0x%02X", model_id);
    // Model ID should be 0xEE (or part of 0xEEAA)
    bool present = (model_id == 0xEE || model_id == 0xAA);
    if (!present) {
        ESP_LOGW(TAG, "VL53L0X model ID mismatch: expected 0xEE or 0xAA, got 0x%02X", model_id);
    }
    return present;
}

int vl53l0x_init(int i2c_port) {
    // Check if sensor is present
    if (!vl53l0x_is_present(i2c_port)) {
        ESP_LOGW(TAG, "VL53L0X not detected at I2C address 0x%02X", VL53L0X_ADDR);
        return VL53L0X_ERROR;
    }

    // Soft reset: write 0x00 to register 0x00
    if (i2c_write_reg(i2c_port, VL53L0X_REG_SOFT_RESET, VL53L0X_SOFT_RESET_VALUE) != ESP_OK) {
        ESP_LOGW(TAG, "Soft reset write failed, continuing anyway");
    }
    vTaskDelay(pdMS_TO_TICKS(2));

    // Wait for sensor to boot (poll until it responds)
    int boot_timeout = 50; // 50ms timeout
    int64_t start = esp_timer_get_time() / 1000;
    uint8_t boot_status = 0;
    while ((esp_timer_get_time() / 1000 - start) < boot_timeout) {
        if (i2c_read_reg(i2c_port, VL53L0X_REG_SYSTEM_MODE_START, &boot_status) == ESP_OK) {
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }

    // Set interrupt config (active low, new sample ready)
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CONFIG_GPIO, 0x04);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Clear any pending interrupts
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Set system sequence config to enable reference SPAD calibration
    // 0xFF enables all calibration steps (TCC, DSS, MSRC, pre-range, final range)
    // This is needed for accurate measurements
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, 0xFF);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Set measurement timing budget (33ms is a good default for single-shot)
    // Register 0x0C (MSB) and 0x0D (LSB) - timing budget in microseconds
    // 33000 microseconds = 33ms
    uint16_t timing_budget_us = 33000;
    i2c_write_reg16(i2c_port, VL53L0X_REG_MEASUREMENT_TIMING_BUDGET_MS, timing_budget_us);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Perform a dummy measurement to trigger calibration
    // This allows the sensor to perform reference SPAD calibration
    ESP_LOGI(TAG, "VL53L0X performing initial calibration measurement...");
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSRANGE_START, 0x01);
    vTaskDelay(pdMS_TO_TICKS(100)); // Wait for calibration measurement to complete
    
    // Clear interrupt after calibration
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
    vTaskDelay(pdMS_TO_TICKS(10));

    ESP_LOGI(TAG, "VL53L0X initialized (timing budget=%d us)", timing_budget_us);
    return VL53L0X_OK;
}

int vl53l0x_read_range_mm(int i2c_port) {
    // Ensure minimum time between measurements to avoid reading stale/partial data
    int64_t now_us = esp_timer_get_time();
    int64_t elapsed_ms = (now_us - g_last_measurement_time_us) / 1000;
    if (elapsed_ms < MIN_MEASUREMENT_INTERVAL_MS) {
        int delay_ms = MIN_MEASUREMENT_INTERVAL_MS - elapsed_ms;
        vTaskDelay(pdMS_TO_TICKS(delay_ms));
    }
    g_last_measurement_time_us = esp_timer_get_time();
    
    // Clear any pending interrupts first
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Stop any ongoing measurement first (write 0x00 to stop)
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSRANGE_START, 0x00);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Start single-shot ranging (0x01 = start)
    if (i2c_write_reg(i2c_port, VL53L0X_REG_SYSRANGE_START, 0x01) != ESP_OK) {
        ESP_LOGD(TAG, "Failed to start ranging");
        return VL53L0X_ERROR;
    }

    // Small delay to allow measurement to start
    vTaskDelay(pdMS_TO_TICKS(1));

    // Wait for measurement to complete (poll interrupt status)
    int timeout_ms = 500;  // Increased timeout for first measurement
    int64_t start = esp_timer_get_time() / 1000;
    uint8_t int_status = 0;
    uint8_t range_status = 0;
    bool measurement_ready = false;
    
    while ((esp_timer_get_time() / 1000 - start) < timeout_ms) {
        // Check interrupt status first
        if (i2c_read_reg(i2c_port, VL53L0X_REG_RESULT_INTERRUPT_STATUS, &int_status) != ESP_OK) {
            ESP_LOGD(TAG, "Failed to read interrupt status");
            return VL53L0X_ERROR;
        }
        
        // Bit 0 = new sample ready (check bits 0-2 for various interrupt types)
        if (int_status & 0x07) {
            // Small delay to ensure measurement data is fully written to registers
            vTaskDelay(pdMS_TO_TICKS(1));
            
            // Read range status to check if valid
            if (i2c_read_reg(i2c_port, VL53L0X_REG_RESULT_RANGE_STATUS, &range_status) != ESP_OK) {
                ESP_LOGE(TAG, "Failed to read range status");
                return VL53L0X_ERROR;
            }
            measurement_ready = true;
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    // Check if we timed out
    if (!measurement_ready) {
        ESP_LOGW(TAG, "VL53L0X read timeout, int_status=0x%02X", int_status);
        // Clear interrupt and return timeout
        i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
        return VL53L0X_TIMEOUT;
    }

    // Check range status (lower 4 bits)
    // Valid statuses with valid range data:
    // 0x00: Range valid, no wrap
    // 0x01: Range valid, sigma fail (warning: less accurate)
    // 0x02: Range valid, signal fail (warning: weak signal)
    // 0x09: Range valid, no wrap (with phase)
    // 0x0D: Range valid, no wrap, signal rate check failed (warning)
    // 0x0E: Range valid, no wrap, sigma check failed (warning)
    // 0x0F: Range valid, no wrap, signal rate and sigma check failed (warning)
    // Invalid/error statuses: 0x03-0x06, 0x07 (wrap fail), 0x08, 0x0A-0x0C
    uint8_t status_low = range_status & 0x0F;
    ESP_LOGD(TAG, "VL53L0X range status: 0x%02X (low=0x%01X), int_status=0x%02X", range_status, status_low, int_status);
    
    // Accept all valid status codes (even with warnings)
    bool is_valid = (status_low == 0x00 || status_low == 0x01 || status_low == 0x02 || 
                     status_low == 0x09 || status_low == 0x0D || status_low == 0x0E || status_low == 0x0F);
    
    if (!is_valid) {
        // Range invalid or error
        ESP_LOGW(TAG, "VL53L0X range invalid, status=0x%02X (low nibble=0x%01X)", range_status, status_low);
        // Clear interrupt
        i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
        return VL53L0X_ERROR;
    }
    
    // Log warning for statuses that indicate reduced accuracy
    if (status_low == 0x01 || status_low == 0x02 || status_low == 0x0D || status_low == 0x0E || status_low == 0x0F) {
        ESP_LOGD(TAG, "VL53L0X range valid but with warning (status=0x%01X)", status_low);
    }

    // Read distance from register 0x1E (LSB) and 0x1F (MSB)
    // According to VL53L0X datasheet, distance is at offset 10 from result base (0x14)
    // So 0x14 + 10 = 0x1E (LSB) and 0x1F (MSB)
    // NOTE: The VL53L0X returns MSB first, then LSB (big-endian), but i2c_read_reg16
    // reads LSB first, then MSB (little-endian), so we need to swap bytes
    uint16_t distance_raw = 0;
    if (i2c_read_reg16(i2c_port, VL53L0X_REG_RESULT_FINAL_RANGE_VALUE, &distance_raw) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read distance register 0x%02X", VL53L0X_REG_RESULT_FINAL_RANGE_VALUE);
        i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
        return VL53L0X_ERROR;
    }
    
    // Swap bytes: VL53L0X returns MSB:LSB, but we read it as LSB:MSB
    // If we read 0x3400, it means LSB=0x00, MSB=0x34, so actual value is 0x0034 = 52mm
    uint16_t distance = ((distance_raw & 0xFF) << 8) | ((distance_raw >> 8) & 0xFF);
    
    // Debug: log raw and swapped values to help diagnose issues
    ESP_LOGD(TAG, "VL53L0X distance: raw=0x%04X, swapped=0x%04X (%d mm)", distance_raw, distance, distance);
    
    // NOTE: The byte swapping fixed the main issue - values are now in reasonable range.
    // The VL53L0X should return distance directly in millimeters without any scaling factor.
    
    // Debug: log suspicious patterns (check low byte of distance value)
    // Values ending in 0x06/0x07 at longer ranges (>23cm) may indicate measurement issues
    // but they're still valid readings, just less accurate
    uint8_t distance_low_byte = distance & 0xFF;
    if ((distance_low_byte == 0x06 || distance_low_byte == 0x07) && distance > 200) {
        ESP_LOGD(TAG, "VL53L0X low byte 0x%02X at distance %d mm (status=0x%02X) - may indicate reduced accuracy at longer range", 
                 distance_low_byte, distance, range_status);
    }

    // Clear interrupt after reading
    i2c_write_reg(i2c_port, VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01);

    // Validate distance (VL53L0X max range is ~2000mm)
    // Values > 8191 are likely errors or invalid measurements
    if (distance > 8191) {
        ESP_LOGW(TAG, "VL53L0X distance out of range: %d mm (raw=0x%04X), status=0x%02X", 
                 distance, distance, range_status);
        return VL53L0X_ERROR;
    }
    
    // Additional check: if status indicates signal issues (0x0D, 0x0E, 0x0F) and distance is suspiciously high,
    // reject it as the measurement is likely unreliable despite status saying "valid"
    if (distance > 2000 && (status_low == 0x0D || status_low == 0x0E || status_low == 0x0F)) {
        ESP_LOGD(TAG, "VL53L0X rejecting high distance %d mm with warning status 0x%01X (unreliable)", distance, status_low);
        return VL53L0X_ERROR;
    }

    bool suspicious_short_glitch = (distance == 20 && status_low != 0x00);

    if (distance > VL53L0X_MAX_STABLE_DISTANCE_MM) {
        distance = VL53L0X_MAX_STABLE_DISTANCE_MM;
    }

    if (suspicious_short_glitch) {
        if (g_last_valid_distance_mm >= 0) {
            ESP_LOGD(TAG, "VL53L0X ignoring suspicious 20mm reading with status=0x%02X, keeping last %d mm",
                     range_status, g_last_valid_distance_mm);
            distance = g_last_valid_distance_mm;
        } else {
            ESP_LOGW(TAG, "VL53L0X ignoring initial suspicious 20mm reading (status=0x%02X)", range_status);
            return VL53L0X_ERROR;
        }
    } else {
        g_last_valid_distance_mm = distance;
    }

    ESP_LOGD(TAG, "VL53L0X read: %d mm (status=0x%02X, int=0x%02X)", distance, range_status, int_status);
    return (int)distance;
}

