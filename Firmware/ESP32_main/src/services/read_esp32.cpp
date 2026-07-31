#include "services/read_esp32.h"

void init_uart_esp32(HardwareSerial &uart_esp_wifi, HardwareSerial &uart_esp_ble){
    uart_esp_wifi.begin(BAUD_RATE_ESP_WIFI, SERIAL_8N1, UART_RX_PIN_ESP_WIFI, UART_TX_PIN_ESP_WIFI);
    uart_esp_ble.begin(BAUD_RATE_ESP_BLE, SERIAL_8N1, UART_RX_PIN_ESP_BLE, UART_TX_PIN_ESP_BLE);
}

void read_esp32(HardwareSerial &uart_esp_wifi, HardwareSerial &uart_esp_ble,
     RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data){
    if (uart_esp_wifi.available() > 0)
    {
        read_uart(uart_esp_wifi, wifi_rssi_data);
    }
    check_last_receive_time(wifi_rssi_data);

    if (uart_esp_ble.available() > 0)
    {
        read_uart(uart_esp_ble, ble_rssi_data);
    }
    check_last_receive_time(ble_rssi_data);
}