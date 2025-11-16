idf_component_register(
    SRCS
        "app_main.c"
        "config.c"
        "hw_sensors.c"
        "cabina_mqtt.c"
        "edge_detect.c"
        "telemetry.c"
    INCLUDE_DIRS "."
    REQUIRES
        esp_wifi
        esp_event
        esp_netif
        nvs_flash
        mqtt
        json
        driver
)


