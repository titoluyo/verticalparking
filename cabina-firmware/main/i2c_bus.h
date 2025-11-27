#ifndef I2C_BUS_H
#define I2C_BUS_H

#ifdef __cplusplus
extern "C" {
#endif

#include "driver/i2c.h"
#include "esp_err.h"

/**
 * @brief Initialize I2C bus
 * 
 * @param port I2C port number (I2C_NUM_0 or I2C_NUM_1)
 * @param sda_gpio SDA GPIO pin number
 * @param scl_gpio SCL GPIO pin number
 * @param freq_hz I2C clock frequency in Hz
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t i2c_bus_init(i2c_port_t port, int sda_gpio, int scl_gpio, uint32_t freq_hz);

/**
 * @brief Deinitialize I2C bus
 * 
 * @param port I2C port number
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t i2c_bus_deinit(i2c_port_t port);

#ifdef __cplusplus
}
#endif

#endif // I2C_BUS_H

