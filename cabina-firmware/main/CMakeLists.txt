idf_component_register(SRCS "main.cpp"
                              "vl53l0x.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer)
