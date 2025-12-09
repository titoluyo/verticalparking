#ifndef OTA_UPDATE_H
#define OTA_UPDATE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"

/**
 * @brief OTA update status codes
 */
typedef enum {
    OTA_STATUS_IDLE = 0,        /**< No OTA in progress */
    OTA_STATUS_CHECKING,        /**< Checking for updates */
    OTA_STATUS_DOWNLOADING,     /**< Downloading firmware */
    OTA_STATUS_VERIFYING,       /**< Verifying firmware */
    OTA_STATUS_APPLYING,        /**< Applying update (rebooting) */
    OTA_STATUS_SUCCESS,         /**< Update successful */
    OTA_STATUS_FAILED,          /**< Update failed */
    OTA_STATUS_NO_UPDATE,       /**< No update available */
    OTA_STATUS_ROLLBACK         /**< Rollback in progress */
} ota_status_t;

/**
 * @brief OTA update progress callback type
 * 
 * @param status Current OTA status
 * @param progress Progress percentage (0-100) during download, or error code if failed
 * @param message Human-readable status message
 */
typedef void (*ota_progress_callback_t)(ota_status_t status, int progress, const char *message);

/**
 * @brief Initialize OTA update subsystem
 * 
 * Must be called before any other OTA functions.
 * Performs rollback validation if device just booted after OTA.
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t ota_update_init(void);

/**
 * @brief Set progress callback for OTA updates
 * 
 * @param callback Progress callback function (NULL to disable)
 */
void ota_update_set_callback(ota_progress_callback_t callback);

/**
 * @brief Start OTA update from a URL
 * 
 * Downloads firmware from the specified URL and applies it.
 * This function runs asynchronously - use the progress callback
 * to monitor status.
 * 
 * @param firmware_url HTTP or HTTPS URL to firmware binary
 * @return ESP_OK if update started, error code otherwise
 */
esp_err_t ota_update_start(const char *firmware_url);

/**
 * @brief Get current firmware version
 * 
 * @return Firmware version string (from esp_app_desc)
 */
const char* ota_update_get_current_version(void);

/**
 * @brief Get current OTA status
 * 
 * @return Current OTA status
 */
ota_status_t ota_update_get_status(void);

/**
 * @brief Check if OTA update is in progress
 * 
 * @return true if update is in progress, false otherwise
 */
bool ota_update_is_busy(void);

/**
 * @brief Check if device is pending rollback validation
 * 
 * After OTA update, the new firmware must validate itself.
 * If validation fails, the device will rollback to the previous version.
 * 
 * @return true if device is pending validation, false otherwise
 */
bool ota_update_is_pending_validation(void);

/**
 * @brief Mark current firmware as valid (cancel rollback)
 * 
 * Call this after successful initialization to confirm the new
 * firmware is working correctly.
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t ota_update_mark_valid(void);

/**
 * @brief Mark current firmware as invalid and rollback
 * 
 * Call this if the new firmware is not working correctly.
 * Device will reboot to the previous firmware version.
 * 
 * @return Does not return on success (device reboots)
 */
esp_err_t ota_update_rollback(void);

/**
 * @brief Get current firmware partition info
 * 
 * @param partition_label Buffer to store partition label (at least 16 bytes)
 * @param partition_label_sz Size of partition_label buffer
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t ota_update_get_partition_info(char *partition_label, size_t partition_label_sz);

/**
 * @brief Handle OTA MQTT command
 * 
 * Parses JSON command and triggers OTA update if valid.
 * Expected format: {"url": "http://...", "force": false}
 * 
 * @param data JSON command data
 * @param data_len Length of command data
 * @return ESP_OK if command handled, error code otherwise
 */
esp_err_t ota_update_handle_mqtt_command(const char *data, int data_len);

/**
 * @brief Build JSON message for OTA status
 * 
 * @param json_buf Buffer to store JSON string
 * @param json_buf_sz Size of JSON buffer
 * @return Number of characters written (excluding null terminator), or -1 on error
 */
int ota_update_json_status(char *json_buf, size_t json_buf_sz);

/**
 * @brief Build JSON message for OTA version info
 * 
 * @param json_buf Buffer to store JSON string
 * @param json_buf_sz Size of JSON buffer
 * @return Number of characters written (excluding null terminator), or -1 on error
 */
int ota_update_json_version(char *json_buf, size_t json_buf_sz);

#ifdef __cplusplus
}
#endif

#endif // OTA_UPDATE_H
