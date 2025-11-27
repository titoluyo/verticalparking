#include <chrono>
#include <thread>

#include "logger.hpp"
#include "vl53l0x_sensor.hpp"

using namespace std::chrono_literals;

extern "C" void app_main(void) {
  espp::Logger logger({.tag = "VL53L0X Test", .level = espp::Logger::Verbosity::INFO});

  logger.info("Starting VL53L0X sensor test...");

  // Add delay to allow I2C bus to stabilize
  std::this_thread::sleep_for(100ms);

  // Configure the VL53L0X sensor for ESP32-C6
  // SDA=14, SCL=15 as specified
  Vl53l0xSensor::Config sensor_config{
      .sda_pin = GPIO_NUM_14,
      .scl_pin = GPIO_NUM_15,
      .i2c_clock_speed = 100000,        // Try 100kHz first (slower, more reliable)
      .i2c_port = I2C_NUM_0,
      .device_address = 0x29,            // Default VL53L0X address
      .timing_budget_ms = 33,            // 33ms timing budget
      .inter_measurement_period_ms = 50, // 50ms between measurements
      .log_level = espp::Logger::Verbosity::DEBUG  // Enable debug logs to see what's happening
  };

  // Create and initialize the sensor
  Vl53l0xSensor sensor(sensor_config);
  
  if (!sensor.init()) {
    logger.error("Failed to initialize VL53L0X sensor!");
    while (true) {
      std::this_thread::sleep_for(1s);
    }
  }

  logger.info("VL53L0X sensor initialized successfully");

  // Start ranging
  if (!sensor.start_ranging()) {
    logger.error("Failed to start ranging!");
    while (true) {
      std::this_thread::sleep_for(1s);
    }
  }

  logger.info("Ranging started. Reading distance measurements...");
  logger.info("Time (s), Distance (mm), Status");
  
  // Wait a bit longer for first measurement to complete
  std::this_thread::sleep_for(200ms);

  auto start_time = std::chrono::steady_clock::now();
  int last_distance = -1;
  int stuck_count = 0;

  // Main loop: read and print distance every 200ms
  // Note: Increased delay to allow sensor time to complete measurements
  while (true) {
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();
    float elapsed_seconds = elapsed / 1000.0f;

    // Check if data is ready before reading
    bool ready = sensor.is_data_ready();
    
    // Read distance in millimeters
    int distance_mm = sensor.get_distance_mm();
    
    // Check if distance is stuck (not changing)
    if (distance_mm == last_distance && distance_mm > 0) {
      stuck_count++;
      if (stuck_count > 5) {
        logger.warn("{:.3f}, {}, STUCK (value unchanged for {} reads)", 
                    elapsed_seconds, distance_mm, stuck_count);
        // Try restarting ranging
        sensor.stop_ranging();
        std::this_thread::sleep_for(50ms);
        sensor.start_ranging();
        std::this_thread::sleep_for(100ms);
        stuck_count = 0;
      }
    } else {
      stuck_count = 0;
      last_distance = distance_mm;
    }
    
    if (distance_mm >= 0) {
      std::string status = ready ? "OK" : "NOT_READY";
      logger.info("{:.3f}, {}, {}", elapsed_seconds, distance_mm, status);
    } else {
      logger.warn("{:.3f}, ERROR, Failed to read distance", elapsed_seconds);
    }

    // Wait 200ms before next reading (sensor needs time for measurement)
    std::this_thread::sleep_for(200ms);
  }
}
