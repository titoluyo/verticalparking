#include <stdio.h>
#include "esp_log.h"
#include "nvs_flash.h"
#include "wifi_client.h"

static const char *TAG = "main";

void app_main(void)
{
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize WiFi client
    ESP_LOGI(TAG, "Initializing WiFi client...");
    ret = wifi_client_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "WiFi initialization failed");
        return;
    }

    // Get and log IP address
    char ip_str[16];
    if (wifi_client_get_ip(ip_str, sizeof(ip_str)) == ESP_OK) {
        ESP_LOGI(TAG, "WiFi connected with IP: %s", ip_str);
    }
}
