#include "config.h"
#include "edge_detect.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_sntp.h"
#include "esp_wifi.h"
#include "hw_sensors.h"
#include "cabina_mqtt.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "telemetry.h"
#include "lwip/inet.h"
#include "lwip/netdb.h"
#include "lwip/sockets.h"
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

static const char *TAG = "app";
static cabina_config_t g_cfg;
static cabina_mqtt_t g_mqtt;
static edge_state_t g_edge;
static volatile int g_pub_interval_sec = 10;

static void time_sync_notify_cb(struct timeval *tv) {
    (void)tv;
    ESP_LOGI(TAG, "Time synchronized");
}

static void start_sntp(void) {
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_set_time_sync_notification_cb(time_sync_notify_cb);
    esp_sntp_init();
}

static void wifi_init_sta(const cabina_config_t *cfg) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfgw = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfgw));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));

    wifi_config_t wifi_config = {0};
    snprintf((char *)wifi_config.sta.ssid, sizeof(wifi_config.sta.ssid), "%s", cfg->wifi_ssid);
    snprintf((char *)wifi_config.sta.password, sizeof(wifi_config.sta.password), "%s", cfg->wifi_password);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());

    // Wait briefly for IP and log it
    esp_netif_ip_info_t ip;
    for (int i = 0; i < 80; ++i) {  // ~8s
        if (esp_netif_get_ip_info(esp_netif_get_handle_from_ifkey("WIFI_STA_DEF"), &ip) == ESP_OK &&
            ip.ip.addr != 0) {
            char ipstr[16];
            ip4addr_ntoa_r((const ip4_addr_t *)&ip.ip, ipstr, sizeof ipstr);
            ESP_LOGI(TAG, "Wi-Fi got IP: %s", ipstr);
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

static void handle_cmd(const char *msg, void *user) {
    (void)user;
    if (strcmp(msg, "ping") == 0) {
        char topic_stat[160];
        topics_build(&g_cfg, NULL, 0, NULL, 0, NULL, 0, topic_stat, sizeof(topic_stat));
        char *js = json_status_online(&g_cfg, NULL);
        if (js) {
            cabina_mqtt_publish_json(&g_mqtt, topic_stat, js, 1, true);
            free(js);
        } else {
            ESP_LOGE(TAG, "OOM building status JSON for ping");
        }
        return;
    }
    // Very small JSON: {"pub_interval": 10}
    int interval = 0;
    if (sscanf(msg, "{\"pub_interval\": %d}", &interval) == 1 && interval >= 1) {
        g_pub_interval_sec = interval;
        ESP_LOGI(TAG, "pub_interval set to %d", g_pub_interval_sec);
    }
}

void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    cabina_load_config(&g_cfg);
    g_pub_interval_sec = g_cfg.pub_interval_sec;

    wifi_init_sta(&g_cfg);
    start_sntp();

    // Connectivity diagnostics before MQTT
    // 1) Check broker (Raspberry Pi) reachability on configured MQTT TCP port
    {
        const char *rasp_host = g_cfg.mqtt_broker;
        uint16_t rasp_port = g_cfg.mqtt_port;
        struct addrinfo hints = {0}, *res = NULL;
        char portstr[8];
        snprintf(portstr, sizeof portstr, "%u", (unsigned)rasp_port);
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_STREAM;
        int err = getaddrinfo(rasp_host, portstr, &hints, &res);
        if (err == 0 && res) {
            int s = socket(res->ai_family, res->ai_socktype, 0);
            if (s >= 0) {
                int flags = fcntl(s, F_GETFL, 0);
                fcntl(s, F_SETFL, flags | O_NONBLOCK);
                connect(s, res->ai_addr, res->ai_addrlen);
                fd_set wfds;
                FD_ZERO(&wfds);
                FD_SET(s, &wfds);
                struct timeval tv = { .tv_sec = 3, .tv_usec = 0 };
                int sel = select(s + 1, NULL, &wfds, NULL, &tv);
                bool ok = false;
                if (sel > 0 && FD_ISSET(s, &wfds)) {
                    int so_error = 0; socklen_t sl = sizeof so_error;
                    getsockopt(s, SOL_SOCKET, SO_ERROR, &so_error, &sl);
                    ok = (so_error == 0);
                }
                close(s);
                ESP_LOGI(TAG, "Diagnostic: Broker %s:%u TCP %s",
                         rasp_host, (unsigned)rasp_port, ok ? "reachable" : "UNREACHABLE");
            } else {
                ESP_LOGE(TAG, "Diagnostic: socket() failed for broker");
            }
            freeaddrinfo(res);
        } else {
            ESP_LOGE(TAG, "Diagnostic: DNS resolve failed for broker %s", rasp_host);
        }
    }

    sensors_init(&g_cfg);
    edge_init(&g_edge);
    cabina_mqtt_init(&g_mqtt, &g_cfg, handle_cmd, NULL);

    char topic_ir1[160], topic_ir2[160], topic_dist[160], topic_stat[160];
    topics_build(&g_cfg, topic_ir1, sizeof(topic_ir1), topic_ir2, sizeof(topic_ir2),
                 topic_dist, sizeof(topic_dist), topic_stat, sizeof(topic_stat));

    int64_t last_sample_ms = 0;
    int64_t last_pub_ms = 0;

    while (true) {
        cabina_mqtt_loop(&g_mqtt);
        int64_t now = esp_timer_get_time() / 1000;

        if (now - last_sample_ms >= (int64_t)g_cfg.sample_period_ms) {
            sensor_snapshot_t snap;
            sensors_read(&snap);
            edge_event_t events[4];
            int n = edge_process(&g_edge, &snap, 20, events, 4);
            for (int i = 0; i < n; ++i) {
                if (events[i].type == EV_IR1) {
                    char *js = json_presence(&g_cfg, "ir1", events[i].present, NULL);
                    if (js) {
                        cabina_mqtt_publish_json(&g_mqtt, topic_ir1, js, 1, g_cfg.presence_retain);
                        free(js);
                    } else {
                        ESP_LOGE(TAG, "OOM building ir1 JSON");
                    }
                } else if (events[i].type == EV_IR2) {
                    char *js = json_presence(&g_cfg, "ir2", events[i].present, NULL);
                    if (js) {
                        cabina_mqtt_publish_json(&g_mqtt, topic_ir2, js, 1, g_cfg.presence_retain);
                        free(js);
                    } else {
                        ESP_LOGE(TAG, "OOM building ir2 JSON");
                    }
                } else if (events[i].type == EV_DISTANCE) {
                    char *js = json_distance(&g_cfg, events[i].dist.from_mm, events[i].dist.to_mm, NULL);
                    if (js) {
                        cabina_mqtt_publish_json(&g_mqtt, topic_dist, js, 0, false);
                        free(js);
                    } else {
                        ESP_LOGE(TAG, "OOM building distance JSON");
                    }
                }
            }
            last_sample_ms = now;
        }

        if (now - last_pub_ms >= (int64_t)g_pub_interval_sec * 1000) {
            // Status online heartbeat
            char *js = json_status_online(&g_cfg, NULL);
            if (js) {
                cabina_mqtt_publish_json(&g_mqtt, topic_stat, js, 1, true);
                free(js);
            } else {
                ESP_LOGE(TAG, "OOM building heartbeat JSON");
            }
            last_pub_ms = now;
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}


