#pragma once

#include <memory>
#include "i2c.hpp"
#include "vl53l.hpp"
#include "logger.hpp"

/**
 * @brief VL53L0X sensor wrapper using espp library
 */
class Vl53l0xSensor {
public:
    /**
     * @brief Configuration for VL53L0X sensor
     */
    struct Config {
        gpio_num_t sda_pin = GPIO_NUM_14;      ///< I2C SDA pin
        gpio_num_t scl_pin = GPIO_NUM_15;      ///< I2C SCL pin
        uint32_t i2c_clock_speed = 400000;     ///< I2C clock speed in Hz
        i2c_port_t i2c_port = I2C_NUM_0;        ///< I2C port number
        uint8_t device_address = 0x29;          ///< VL53L0X I2C address
        uint32_t timing_budget_ms = 33;        ///< Measurement timing budget in ms
        uint32_t inter_measurement_period_ms = 50; ///< Inter-measurement period in ms
        espp::Logger::Verbosity log_level = espp::Logger::Verbosity::INFO;
    };

    /**
     * @brief Constructor
     * @param config Configuration for the sensor
     */
    explicit Vl53l0xSensor(const Config& config);

    /**
     * @brief Initialize the sensor
     * @return true on success, false on failure
     */
    bool init();

    /**
     * @brief Start continuous ranging
     * @return true on success, false on failure
     */
    bool start_ranging();

    /**
     * @brief Stop ranging
     */
    void stop_ranging();

    /**
     * @brief Check if data is ready
     * @return true if data is ready, false otherwise
     */
    bool is_data_ready();

    /**
     * @brief Get distance in meters
     * @return Distance in meters, or -1.0 on error
     */
    float get_distance_meters();

    /**
     * @brief Get distance in millimeters
     * @return Distance in millimeters, or -1 on error
     */
    int get_distance_mm();

    /**
     * @brief Check if sensor is initialized
     * @return true if initialized, false otherwise
     */
    bool is_initialized() const { return initialized_; }

private:
    Config config_;
    std::unique_ptr<espp::I2c> i2c_;
    std::unique_ptr<espp::Vl53l> vl53l_;
    std::unique_ptr<espp::Logger> logger_;
    bool initialized_;
};





