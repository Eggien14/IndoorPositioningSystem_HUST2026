#ifndef READ_ESP32_H
#define READ_ESP32_H

#include "devices/uart.h"
#include "config.h"


void init_uart_esp32(HardwareSerial &uart_esp_wifi, HardwareSerial &uart_esp_ble);
void read_esp32(HardwareSerial &uart_esp_wifi, HardwareSerial &uart_esp_ble,
     RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data);

#endif
