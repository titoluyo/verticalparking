#include "ota_update.h"
#include "sdkconfig.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_https_ota.h"
#include "esp_http_client.h"
#include "esp_app_desc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <cstring>
#include <cstdio>

static const char *TAG = "ota_update";

// OTA state
static ota_status_t s_ota_status = OTA_STATUS_IDLE;
static int s_ota_progress = 0;
static char s_ota_message[128] = "Idle";
static ota_progress_callback_t s_progress_callback = NULL;
static SemaphoreHandle_t s_ota_mutex = NULL;
static bool s_pending_validation = false;

// OTA task parameters
#define OTA_TASK_STACK_SIZE 8192
#define OTA_TASK_PRIORITY 5
#define OTA_URL_MAX_LEN 256

static char s_ota_url[OTA_URL_MAX_LEN] = {0};

// Forward declarations
static void ota_task(void *pvParameter);
static void update_status(ota_status_t status, int progress, const char *message);

esp_err_t ota_update_init(void) {
    // Create mutex for OTA state access
    if (s_ota_mutex == NULL) {
        s_ota_mutex = xSemaphoreCreateMutex();
        if (s_ota_mutex == NULL) {
            ESP_LOGE(TAG, "Failed to create OTA mutex");
            return ESP_ERR_NO_MEM;
        }
    }

    // Check if we need to validate after OTA
    const esp_partition_t *running = esp_ota_get_running_partition();
    esp_ota_img_states_t ota_state;
    
    if (esp_ota_get_state_partition(running, &ota_state) == ESP_OK) {
        if (ota_state == ESP_OTA_IMG_PENDING_VERIFY) {
            s_pending_validation = true;
            ESP_LOGI(TAG, "OTA update detected - firmware pending validation");
            ESP_LOGI(TAG, "Running from partition: %s", running->label);
        }
    }

    // Log current version and partition info
    const esp_app_desc_t *app_desc = esp_app_get_description();
    ESP_LOGI(TAG, "Current firmware version: %s", app_desc->version);
    ESP_LOGI(TAG, "Running from partition: %s at 0x%lx", 
             running->label, running->address);

    return ESP_OK;
}

void ota_update_set_callback(ota_progress_callback_t callback) {
    s_progress_callback = callback;
}

static void update_status(ota_status_t status, int progress, const char *message) {
    if (xSemaphoreTake(s_ota_mutex, pdMS_TO_TICKS(1000)) == pdTRUE) {
        s_ota_status = status;
        s_ota_progress = progress;
        if (message) {
            strncpy(s_ota_message, message, sizeof(s_ota_message) - 1);
            s_ota_message[sizeof(s_ota_message) - 1] = '\0';
        }
        xSemaphoreGive(s_ota_mutex);
    }

    // Invoke callback if set
    if (s_progress_callback) {
        s_progress_callback(status, progress, message);
    }

    ESP_LOGI(TAG, "OTA Status: %d, Progress: %d%%, Message: %s", 
             status, progress, message ? message : "");
}

static esp_err_t http_event_handler(esp_http_client_event_t *evt) {
    switch (evt->event_id) {
        case HTTP_EVENT_ERROR:
            ESP_LOGD(TAG, "HTTP_EVENT_ERROR");
            break;
        case HTTP_EVENT_ON_CONNECTED:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_CONNECTED");
            break;
        case HTTP_EVENT_HEADER_SENT:
            ESP_LOGD(TAG, "HTTP_EVENT_HEADER_SENT");
            break;
        case HTTP_EVENT_ON_HEADER:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_HEADER, key=%s, value=%s", 
                    evt->header_key, evt->header_value);
            break;
        case HTTP_EVENT_ON_DATA:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_DATA, len=%d", evt->data_len);
            break;
        case HTTP_EVENT_ON_FINISH:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_FINISH");
            break;
        case HTTP_EVENT_DISCONNECTED:
            ESP_LOGD(TAG, "HTTP_EVENT_DISCONNECTED");
            break;
        case HTTP_EVENT_REDIRECT:
            ESP_LOGD(TAG, "HTTP_EVENT_REDIRECT");
            break;
    }
    return ESP_OK;
}

static void ota_task(void *pvParameter) {
    ESP_LOGI(TAG, "Starting OTA update from: %s", s_ota_url);
    
    update_status(OTA_STATUS_CHECKING, 0, "Connecting to server");

    // Configure HTTP client
    esp_http_client_config_t http_config = {};
    http_config.url = s_ota_url;
    http_config.event_handler = http_event_handler;
    http_config.timeout_ms = 30000;
    http_config.keep_alive_enable = true;
    
    // For HTTPS, we'd need to configure certificates
    // For now, support HTTP (skip cert verification for development)
    #ifdef CONFIG_EXAMPLE_OTA_SKIP_CERT_VERIFY
    http_config.skip_cert_common_name_check = true;
    #endif

    // Configure OTA
    esp_https_ota_config_t ota_config = {};
    ota_config.http_config = &http_config;

    esp_https_ota_handle_t ota_handle = NULL;
    esp_err_t err = esp_https_ota_begin(&ota_config, &ota_handle);
    
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "OTA begin failed: %s", esp_err_to_name(err));
        update_status(OTA_STATUS_FAILED, err, "Failed to connect");
        vTaskDelete(NULL);
        return;
    }

    // Get image size for progress calculation
    int image_size = esp_https_ota_get_image_size(ota_handle);
    ESP_LOGI(TAG, "Firmware image size: %d bytes", image_size);
    
    update_status(OTA_STATUS_DOWNLOADING, 0, "Downloading firmware");

    int bytes_read = 0;
    int last_progress = -1;

    while (true) {
        err = esp_https_ota_perform(ota_handle);
        
        if (err == ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
            bytes_read = esp_https_ota_get_image_len_read(ota_handle);
            
            if (image_size > 0) {
                int progress = (bytes_read * 100) / image_size;
                if (progress != last_progress) {
                    last_progress = progress;
                    char msg[64];
                    snprintf(msg, sizeof(msg), "Downloaded %d%%", progress);
                    update_status(OTA_STATUS_DOWNLOADING, progress, msg);
                }
            }
            continue;
        }
        
        if (err == ESP_OK) {
            // Download complete
            break;
        }
        
        // Error occurred
        ESP_LOGE(TAG, "OTA perform failed: %s", esp_err_to_name(err));
        esp_https_ota_abort(ota_handle);
        update_status(OTA_STATUS_FAILED, err, "Download failed");
        vTaskDelete(NULL);
        return;
    }

    // Verify firmware
    update_status(OTA_STATUS_VERIFYING, 100, "Verifying firmware");
    
    if (!esp_https_ota_is_complete_data_received(ota_handle)) {
        ESP_LOGE(TAG, "Complete data was not received");
        esp_https_ota_abort(ota_handle);
        update_status(OTA_STATUS_FAILED, ESP_ERR_INVALID_SIZE, "Incomplete data");
        vTaskDelete(NULL);
        return;
    }

    // Finish OTA and set boot partition
    err = esp_https_ota_finish(ota_handle);
    
    if (err == ESP_OK) {
        update_status(OTA_STATUS_APPLYING, 100, "Update successful, rebooting...");
        ESP_LOGI(TAG, "OTA update successful! Rebooting in 3 seconds...");
        vTaskDelay(pdMS_TO_TICKS(3000));
        esp_restart();
    } else if (err == ESP_ERR_OTA_VALIDATE_FAILED) {
        ESP_LOGE(TAG, "Firmware validation failed");
        update_status(OTA_STATUS_FAILED, err, "Validation failed");
    } else {
        ESP_LOGE(TAG, "OTA finish failed: %s", esp_err_to_name(err));
        update_status(OTA_STATUS_FAILED, err, "Update failed");
    }

    vTaskDelete(NULL);
}

esp_err_t ota_update_start(const char *firmware_url) {
    if (firmware_url == NULL || strlen(firmware_url) == 0) {
        ESP_LOGE(TAG, "Invalid firmware URL");
        return ESP_ERR_INVALID_ARG;
    }

    if (strlen(firmware_url) >= OTA_URL_MAX_LEN) {
        ESP_LOGE(TAG, "Firmware URL too long");
        return ESP_ERR_INVALID_SIZE;
    }

    // Check if OTA is already in progress
    if (ota_update_is_busy()) {
        ESP_LOGW(TAG, "OTA update already in progress");
        return ESP_ERR_INVALID_STATE;
    }

    // Store URL and start task
    strncpy(s_ota_url, firmware_url, OTA_URL_MAX_LEN - 1);
    s_ota_url[OTA_URL_MAX_LEN - 1] = '\0';

    BaseType_t ret = xTaskCreate(ota_task, "ota_task", 
                                  OTA_TASK_STACK_SIZE, NULL, 
                                  OTA_TASK_PRIORITY, NULL);
    
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create OTA task");
        return ESP_ERR_NO_MEM;
    }

    return ESP_OK;
}

const char* ota_update_get_current_version(void) {
    const esp_app_desc_t *app_desc = esp_app_get_description();
    return app_desc->version;
}

ota_status_t ota_update_get_status(void) {
    ota_status_t status = OTA_STATUS_IDLE;
    if (s_ota_mutex && xSemaphoreTake(s_ota_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        status = s_ota_status;
        xSemaphoreGive(s_ota_mutex);
    }
    return status;
}

bool ota_update_is_busy(void) {
    ota_status_t status = ota_update_get_status();
    return (status == OTA_STATUS_CHECKING || 
            status == OTA_STATUS_DOWNLOADING || 
            status == OTA_STATUS_VERIFYING ||
            status == OTA_STATUS_APPLYING);
}

bool ota_update_is_pending_validation(void) {
    return s_pending_validation;
}

esp_err_t ota_update_mark_valid(void) {
    if (!s_pending_validation) {
        ESP_LOGD(TAG, "No pending validation");
        return ESP_OK;
    }

    esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
    if (err == ESP_OK) {
        s_pending_validation = false;
        ESP_LOGI(TAG, "Firmware marked as valid - rollback cancelled");
    } else {
        ESP_LOGE(TAG, "Failed to mark firmware valid: %s", esp_err_to_name(err));
    }
    return err;
}

esp_err_t ota_update_rollback(void) {
    ESP_LOGW(TAG, "Initiating firmware rollback...");
    update_status(OTA_STATUS_ROLLBACK, 0, "Rolling back firmware");
    
    esp_err_t err = esp_ota_mark_app_invalid_rollback_and_reboot();
    // This function should not return on success
    ESP_LOGE(TAG, "Rollback failed: %s", esp_err_to_name(err));
    return err;
}

esp_err_t ota_update_get_partition_info(char *partition_label, size_t partition_label_sz) {
    if (partition_label == NULL || partition_label_sz < 16) {
        return ESP_ERR_INVALID_ARG;
    }

    const esp_partition_t *running = esp_ota_get_running_partition();
    if (running == NULL) {
        return ESP_ERR_NOT_FOUND;
    }

    strncpy(partition_label, running->label, partition_label_sz - 1);
    partition_label[partition_label_sz - 1] = '\0';
    return ESP_OK;
}

esp_err_t ota_update_handle_mqtt_command(const char *data, int data_len) {
    if (data == NULL || data_len <= 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Simple JSON parsing for OTA command
    // Expected format: {"url": "http://...", "force": false}
    
    // Look for "url" field
    const char *url_key = strstr(data, "\"url\"");
    if (url_key == NULL) {
        ESP_LOGW(TAG, "OTA command missing 'url' field");
        return ESP_ERR_INVALID_ARG;
    }

    // Find the URL value (after the colon and opening quote)
    const char *url_start = strchr(url_key + 5, '"');
    if (url_start == NULL) {
        ESP_LOGW(TAG, "Invalid URL format in OTA command");
        return ESP_ERR_INVALID_ARG;
    }
    url_start++; // Skip opening quote

    // Find the closing quote
    const char *url_end = strchr(url_start, '"');
    if (url_end == NULL) {
        ESP_LOGW(TAG, "Invalid URL format - missing closing quote");
        return ESP_ERR_INVALID_ARG;
    }

    // Extract URL
    size_t url_len = url_end - url_start;
    if (url_len >= OTA_URL_MAX_LEN) {
        ESP_LOGW(TAG, "URL too long");
        return ESP_ERR_INVALID_SIZE;
    }

    char url[OTA_URL_MAX_LEN];
    strncpy(url, url_start, url_len);
    url[url_len] = '\0';

    // Check for "force" field (optional)
    bool force = (strstr(data, "\"force\"") != NULL && strstr(data, "true") != NULL);

    ESP_LOGI(TAG, "OTA command received: url=%s, force=%s", url, force ? "true" : "false");

    // Check if update is already in progress
    if (ota_update_is_busy() && !force) {
        ESP_LOGW(TAG, "OTA update already in progress");
        return ESP_ERR_INVALID_STATE;
    }

    // Start OTA update
    return ota_update_start(url);
}

int ota_update_json_status(char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }

    ota_status_t status = OTA_STATUS_IDLE;
    int progress = 0;
    char message[128] = "Idle";

    if (s_ota_mutex && xSemaphoreTake(s_ota_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        status = s_ota_status;
        progress = s_ota_progress;
        strncpy(message, s_ota_message, sizeof(message) - 1);
        message[sizeof(message) - 1] = '\0';
        xSemaphoreGive(s_ota_mutex);
    }

    const char *status_str;
    switch (status) {
        case OTA_STATUS_IDLE:       status_str = "idle"; break;
        case OTA_STATUS_CHECKING:   status_str = "checking"; break;
        case OTA_STATUS_DOWNLOADING: status_str = "downloading"; break;
        case OTA_STATUS_VERIFYING:  status_str = "verifying"; break;
        case OTA_STATUS_APPLYING:   status_str = "applying"; break;
        case OTA_STATUS_SUCCESS:    status_str = "success"; break;
        case OTA_STATUS_FAILED:     status_str = "failed"; break;
        case OTA_STATUS_NO_UPDATE:  status_str = "no_update"; break;
        case OTA_STATUS_ROLLBACK:   status_str = "rollback"; break;
        default:                    status_str = "unknown"; break;
    }

    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"ota_status\":\"%s\","
                    "\"progress\":%d,\"message\":\"%s\"}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                    status_str,
                    progress,
                    message);
}

int ota_update_json_version(char *json_buf, size_t json_buf_sz) {
    if (!json_buf || json_buf_sz == 0) {
        return -1;
    }

    const esp_app_desc_t *app_desc = esp_app_get_description();
    const esp_partition_t *running = esp_ota_get_running_partition();
    
    return snprintf(json_buf, json_buf_sz,
                    "{\"site\":\"%s\",\"device\":\"%s\",\"version\":\"%s\","
                    "\"idf_version\":\"%s\",\"partition\":\"%s\","
                    "\"pending_validation\":%s}",
                    CONFIG_EXAMPLE_MQTT_SITE_ID,
                    CONFIG_EXAMPLE_MQTT_DEVICE_ID,
                    app_desc->version,
                    app_desc->idf_ver,
                    running ? running->label : "unknown",
                    s_pending_validation ? "true" : "false");
}
