#ifndef MQTT_WRAPPER_H
#define MQTT_WRAPPER_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"

/**
 * @brief Initialize MQTT client
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t mqtt_client_init(void);

/**
 * @brief Check if MQTT client is connected
 * 
 * @return true if connected, false otherwise
 */
bool mqtt_client_is_connected(void);

/**
 * @brief Publish a message to an MQTT topic
 * 
 * @param topic Topic to publish to
 * @param data Message data
 * @param len Message length (0 = null-terminated string)
 * @param qos Quality of Service (0, 1, or 2)
 * @param retain Whether to retain the message
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t mqtt_client_publish(const char *topic, const char *data, int len, int qos, bool retain);

/**
 * @brief Publish a JSON message to an MQTT topic
 * 
 * @param topic Topic to publish to
 * @param json JSON string
 * @param qos Quality of Service (0, 1, or 2)
 * @param retain Whether to retain the message
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t mqtt_client_publish_json(const char *topic, const char *json, int qos, bool retain);

/**
 * @brief Subscribe to an MQTT topic
 * 
 * @param topic Topic to subscribe to
 * @param qos Quality of Service (0, 1, or 2)
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t mqtt_client_subscribe(const char *topic, int qos);

/**
 * @brief Get the full topic path for a subtopic
 * 
 * @param subtopic Subtopic (e.g., "status", "presence", "distance")
 * @param topic_buf Buffer to store the full topic (must be at least 160 bytes)
 * @param buf_len Length of the buffer
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t mqtt_client_get_topic(const char *subtopic, char *topic_buf, size_t buf_len);

/**
 * @brief Message callback function type
 */
typedef void (*mqtt_message_callback_t)(const char *topic, const char *data, int data_len);

/**
 * @brief Set callback function for received MQTT messages
 * 
 * @param callback Callback function (NULL to disable)
 */
void mqtt_client_set_message_callback(mqtt_message_callback_t callback);

#ifdef __cplusplus
}
#endif

#endif // MQTT_WRAPPER_H

