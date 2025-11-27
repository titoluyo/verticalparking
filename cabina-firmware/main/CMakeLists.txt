idf_component_register(SRCS "main.cpp"
                              "vl53l0x.c"
                              "wifi_client.cpp"
                              "i2c_bus.cpp"
                              "ir_sensors.cpp"
                              "mqtt_client.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer esp_wifi esp_netif esp_event nvs_flash freertos mqtt)
