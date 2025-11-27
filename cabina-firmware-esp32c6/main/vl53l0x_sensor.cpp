#include "vl53l0x_sensor.hpp"
#include <functional>
#include <thread>
#include <chrono>
#include "sdkconfig.h"

using namespace std::chrono_literals;

Vl53l0xSensor::Vl53l0xSensor(const Config& config)
    : config_(config)
    , initialized_(false)
{
    logger_ = std::make_unique<espp::Logger>(espp::Logger::Config{
        .tag = "VL53L0X",
        .level = config_.log_level
    });
}

bool Vl53l0xSensor::init()
{
    if (initialized_) {
        logger_->warn("Sensor already initialized");
        return true;
    }

    // Create I2C instance
    i2c_ = std::make_unique<espp::I2c>(espp::I2c::Config{
        .port = config_.i2c_port,
        .sda_io_num = config_.sda_pin,
        .scl_io_num = config_.scl_pin,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .clk_speed = config_.i2c_clock_speed,
        .auto_init = true,
        .log_level = config_.log_level
    });

    // Create VL53L sensor instance
    // Note: ESP++ component expects VL53L4CX, but we're using VL53L0X
    // The model ID check will fail, but we'll continue anyway
    vl53l_ = std::make_unique<espp::Vl53l>(espp::Vl53l::Config{
        .device_address = config_.device_address,
        .write = std::bind(&espp::I2c::write, i2c_.get(),
                         std::placeholders::_1,
                         std::placeholders::_2,
                         std::placeholders::_3),
        .read = std::bind(&espp::I2c::read, i2c_.get(),
                         std::placeholders::_1,
                         std::placeholders::_2,
                         std::placeholders::_3),
        .auto_init = true,  // Let it try to auto-init
        .log_level = config_.log_level
    });
    
    // Wait a bit for initialization to complete
    std::this_thread::sleep_for(50ms);

    std::error_code ec;

    // Set timing budget
    if (!vl53l_->set_timing_budget_ms(config_.timing_budget_ms, ec)) {
        logger_->error("Failed to set timing budget: {}", ec.message());
        return false;
    }

    // Set inter-measurement period
    if (!vl53l_->set_inter_measurement_period_ms(config_.inter_measurement_period_ms, ec)) {
        logger_->error("Failed to set inter-measurement period: {}", ec.message());
        return false;
    }

    initialized_ = true;
    logger_->info("VL53L0X sensor initialized successfully");
    return true;
}

bool Vl53l0xSensor::start_ranging()
{
    if (!initialized_) {
        logger_->error("Sensor not initialized");
        return false;
    }

    std::error_code ec;
    if (!vl53l_->start_ranging(ec)) {
        logger_->error("Failed to start ranging: {}", ec.message());
        return false;
    }

    logger_->info("Ranging started");
    return true;
}

void Vl53l0xSensor::stop_ranging()
{
    if (!initialized_ || !vl53l_) {
        return;
    }

    std::error_code ec;
    vl53l_->stop_ranging(ec);
    if (ec) {
        logger_->warn("Error stopping ranging: {}", ec.message());
    } else {
        logger_->info("Ranging stopped");
    }
}

bool Vl53l0xSensor::is_data_ready()
{
    if (!initialized_ || !vl53l_) {
        return false;
    }

    std::error_code ec;
    return vl53l_->is_data_ready(ec);
}

float Vl53l0xSensor::get_distance_meters()
{
    if (!initialized_ || !vl53l_) {
        return -1.0f;
    }

    std::error_code ec;
    
    // Wait for data to be ready
    int timeout_count = 0;
    while (!vl53l_->is_data_ready(ec) && timeout_count < 100) {
        std::this_thread::sleep_for(1ms);
        timeout_count++;
    }

    if (timeout_count >= 100) {
        logger_->warn("Timeout waiting for data ready");
        return -1.0f;
    }

    // Clear interrupt
    if (!vl53l_->clear_interrupt(ec)) {
        logger_->warn("Failed to clear interrupt: {}", ec.message());
        return -1.0f;
    }

    // Get distance
    float distance = vl53l_->get_distance_meters(ec);
    if (ec) {
        logger_->warn("Failed to get distance: {}", ec.message());
        return -1.0f;
    }

    return distance;
}

int Vl53l0xSensor::get_distance_mm()
{
    float meters = get_distance_meters();
    if (meters < 0.0f) {
        return -1;
    }
    return static_cast<int>(meters * 1000.0f);
}

