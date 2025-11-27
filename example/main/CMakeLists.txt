idf_component_register(SRCS "vl53l0x_example.cpp"
                              "vl53l0x.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer)
