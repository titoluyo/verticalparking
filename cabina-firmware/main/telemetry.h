#ifndef TELEMETRY_H
#define TELEMETRY_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>

/**
 * @brief Build MQTT topic strings
 * 
 * @param topic_ir1 Buffer for IR1 topic (presence/entry)
 * @param topic_ir1_sz Size of IR1 topic buffer
 * @param topic_ir2 Buffer for IR2 topic (presence/full)
 * @param topic_ir2_sz Size of IR2 topic buffer
 * @param topic_dist Buffer for distance topic (distance/event)
 * @param topic_dist_sz Size of distance topic buffer
 * @param topic_stat Buffer for status topic (status)
 * @param topic_stat_sz Size of status topic buffer
 */
void telemetry_build_topics(char *topic_ir1, size_t topic_ir1_sz,
                            char *topic_ir2, size_t topic_ir2_sz,
                            char *topic_dist, size_t topic_dist_sz,
                            char *topic_stat, size_t topic_stat_sz);

/**
 * @brief Build JSON message for IR presence event
 * 
 * @param sensor Sensor name ("ir1" or "ir2")
 * @param present Presence state
 * @param json_buf Buffer to store JSON string
 * @param json_buf_sz Size of JSON buffer
 * @return Number of characters written (excluding null terminator), or -1 on error
 */
int telemetry_json_presence(const char *sensor, bool present, 
                            char *json_buf, size_t json_buf_sz);

/**
 * @brief Build JSON message for distance event
 * 
 * @param from_mm Previous distance in mm
 * @param to_mm New distance in mm
 * @param json_buf Buffer to store JSON string
 * @param json_buf_sz Size of JSON buffer
 * @return Number of characters written (excluding null terminator), or -1 on error
 */
int telemetry_json_distance(int from_mm, int to_mm, 
                           char *json_buf, size_t json_buf_sz);

/**
 * @brief Build JSON message for status heartbeat
 * 
 * @param json_buf Buffer to store JSON string
 * @param json_buf_sz Size of JSON buffer
 * @return Number of characters written (excluding null terminator), or -1 on error
 */
int telemetry_json_status(char *json_buf, size_t json_buf_sz);

#ifdef __cplusplus
}
#endif

#endif // TELEMETRY_H

