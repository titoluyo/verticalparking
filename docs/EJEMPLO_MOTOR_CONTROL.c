// motor-control/main/main.c - Archivo completo
// Muestra: Recepción de comandos MQTT y control del relé del motor

#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
#include "nvs_flash.h"

static const char *TAG = "motor_control";

static esp_mqtt_client_handle_t s_mqtt_client;
static bool s_mqtt_started;
static bool s_relay_state;
static bool s_relay_initialized;

// Aplica el estado al relé (control físico del motor)
static void relay_apply(bool on)
{
    const int gpio_level = CONFIG_MOTOR_CONTROL_RELAY_ACTIVE_HIGH ? (on ? 1 : 0) : (on ? 0 : 1);
    gpio_set_level(CONFIG_MOTOR_CONTROL_RELAY_GPIO, gpio_level);
}

// Establece el estado del relé
static void relay_set(bool on)
{
    if (s_relay_state == on && s_relay_initialized) {
        return;  // Ya está en el estado deseado
    }
    
    s_relay_state = on;
    relay_apply(on);
    s_relay_initialized = true;
    ESP_LOGI(TAG, "Relay -> %s", on ? "ON" : "OFF");
}

// Procesa comandos MQTT recibidos
static void process_mqtt_command(const char *data, int len)
{
    if (len <= 0) {
        return;
    }
    
    char command[8] = {0};
    size_t copy_len = len < (int)(sizeof(command) - 1) ? (size_t)len : sizeof(command) - 1;
    memcpy(command, data, copy_len);
    
    // Convierte a mayúsculas
    size_t cmd_len = strlen(command);
    for (size_t i = 0; i < cmd_len; ++i) {
        command[i] = (char)toupper((unsigned char)command[i]);
    }
    
    // Procesa comandos: "ON" para iniciar motor, "OFF" para detener
    if (strcmp(command, "ON") == 0) {
        relay_set(true);   // Activa el relé -> motor inicia
    } else if (strcmp(command, "OFF") == 0) {
        relay_set(false);  // Desactiva el relé -> motor se detiene
    } else {
        ESP_LOGW(TAG, "Unsupported command: %s", command);
    }
}

// Manejador de eventos MQTT
static void mqtt_event_handler(void *handler_args, esp_event_base_t base, 
                                int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;
    
    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        // Se conectó a MQTT - se suscribe al topic de comandos
        ESP_LOGI(TAG, "MQTT connected, subscribing to '%s'", CONFIG_MOTOR_CONTROL_MQTT_TOPIC);
        esp_mqtt_client_subscribe(event->client, CONFIG_MOTOR_CONTROL_MQTT_TOPIC, 
                                  CONFIG_MOTOR_CONTROL_MQTT_QOS);
        break;
    case MQTT_EVENT_DATA:
        // Recibió un mensaje - procesa el comando
        process_mqtt_command(event->data, event->data_len);
        break;
    default:
        break;
    }
}

// Inicializa el cliente MQTT
static void start_mqtt_client(void)
{
    if (s_mqtt_started) {
        return;
    }
    
    const esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = CONFIG_MOTOR_CONTROL_MQTT_URI,
        .credentials.username = CONFIG_MOTOR_CONTROL_MQTT_USERNAME,
        .credentials.authentication.password = CONFIG_MOTOR_CONTROL_MQTT_PASSWORD,
        .credentials.client_id = CONFIG_MOTOR_CONTROL_MQTT_CLIENT_ID,
    };
    
    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(s_mqtt_client, ESP_EVENT_ANY_ID, 
                                   mqtt_event_handler, NULL);
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt_client));
    s_mqtt_started = true;
}

// Inicializa el relé (GPIO)
static void relay_init(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = 1ULL << CONFIG_MOTOR_CONTROL_RELAY_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&io_conf));
    s_relay_initialized = false;
    relay_set(false);  // Estado inicial: motor apagado (seguridad)
    ESP_LOGI(TAG, "Relay ready on GPIO %d", CONFIG_MOTOR_CONTROL_RELAY_GPIO);
}

// Función principal
void app_main(void)
{
    // Inicialización del sistema
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    
    relay_init();      // Inicializa el relé
    wifi_start();      // Inicializa WiFi (luego inicia MQTT cuando obtiene IP)
}
