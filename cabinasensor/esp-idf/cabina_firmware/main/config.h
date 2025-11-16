#pragma once
#include <stdbool.h>
#include <stdint.h>

// Populated from Kconfig in config.c
typedef struct {
    const char *wifi_ssid;
    const char *wifi_password;
    const char *mqtt_broker;
    uint16_t    mqtt_port;
    const char *mqtt_user;
    const char *mqtt_password;
    const char *topic_base;
    const char *site_id;
    char        device_id[32]; // may be derived from MAC
    bool        presence_retain;
    uint32_t    pub_interval_sec;
    uint32_t    sample_period_ms;
    bool        ir_pullups;

    int         gpio_ir1;
    int         gpio_ir2;
    int         i2c_scl;
    int         i2c_sda;
} cabina_config_t;

void cabina_load_config(cabina_config_t *out);


