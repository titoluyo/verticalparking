#ifndef WIFI_CLIENT_H
#define WIFI_CLIENT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"

/**
 * @brief Initialize WiFi in station (client) mode
 * 
 * This function initializes the WiFi stack, configures it as a station,
 * and attempts to connect to the configured access point. It will block
 * until either a connection is established or the maximum retry count is reached.
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t wifi_client_init(void);

/**
 * @brief Get the current WiFi connection status
 * 
 * @return true if connected, false otherwise
 */
bool wifi_client_is_connected(void);

/**
 * @brief Get the assigned IP address
 * 
 * @param ip_str Buffer to store IP address string (must be at least 16 bytes)
 * @param len Length of the buffer
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t wifi_client_get_ip(char *ip_str, size_t len);

#ifdef __cplusplus
}
#endif

#endif // WIFI_CLIENT_H

